import asyncio
import contextlib
import typing

import evdev
import toml
import urwid

from .linux.rc import RCDevice
from .pkg.evdev import evdev_open_device
from .rc_monitor import rc_monitor

# https://git.linuxtv.org/v4l-utils.git/
# https://git.linuxtv.org/v4l-utils.git/tree/utils/keytable
# https://git.linuxtv.org/v4l-utils.git/tree/utils/keytable/keytable.c
# https://manpages.debian.org/testing/ir-keytable/ir-keytable.1.en.html
# https://manpages.debian.org/testing/ir-keytable/rc_keymap.5.en.html


class RCKeymap():
    def _strtoull(x: str):
        # strtoull is used on keytable.c to parse the scancodes
        # not a perfect emulation but good enough
        if x[:2] in ['0x', '0X']:
            return int(x, 16)
        if x[:1] == '0':
            return int(x, 8)
        return int(x, 10)

    _schema = {
        't': dict,
        'v': {
            'protocols': {
                't': list,
                '*': {
                    't': dict,
                    'v': {
                        'protocol': {
                            't': str
                        },
                        'scancodes': {
                            't': dict,
                            'k>': _strtoull,
                            'k<': lambda x: '0x%02x' % x,
                            '*': {
                                't': str
                            }
                        }
                    }
                }
            }
        }
    }

    @staticmethod
    def _validate(o, f='', s=_schema):
        # a bespoke validator and converter based on a schema
        # to validate the keymap file contents

        k_ = 'k' + f if f else None

        def p(o, s):
            if not isinstance(o, s['t']):
                raise ValueError()
            if s['t'] == dict:
                def kv(kv):
                    k, v = kv
                    if f != '<' and not isinstance(k, str):
                        raise ValueError()
                    if 'v' in s and k in s['v']:
                        v = p(v, s['v'][k])
                    elif '*' in s:
                        v = p(v, s['*'])
                    if k_ and k_ in s:
                        k = s[k_](k)
                    return k, v
                return {k: v for k, v in map(kv, o.items())}
            if s['t'] == list:
                return [p(v, s['*']) for v in o]
            return o
        return p(o, s)

    def __init__(self):
        self._data = {}

    def load(self, file):
        with open(file, 'r') as fp:
            data = toml.load(fp)
        self._data = self.__class__._validate(data, '>')

    def save(self, file, trim=True):
        data = self.__class__._validate(self._data, '<')
        if trim:
            def is_proto(p):
                return 'scancodes' in p and p['scancodes']
            if 'protocols' in data:
                data['protocols'] = list(
                    filter(lambda x: is_proto(x), data['protocols'])
                )
                if not data['protocols']:
                    del data['protocols']
        with open(file, 'w') as fp:
            toml.dump(data, fp)

    def all_scancodes(self):
        if 'protocols' not in self._data:
            return
        for protocol in self._data['protocols']:
            if 'protocol' not in protocol or 'scancodes' not in protocol:
                continue
            proto = protocol['protocol']
            for scancode, key in protocol['scancodes'].items():
                yield proto, scancode, key

    def all_scancodes_by_key(self):
        res = {}
        for proto, scancode, key in self.all_scancodes():
            if key not in res:
                res[key] = []
            res[key].append((proto, scancode))
        return res

    def set_scancode(self, proto: str, scancode: int, key: str):
        if 'protocols' not in self._data:
            self._data['protocols'] = []
        protocol = next(
            (p for p in self._data['protocols'] if 'protocol' in p and p['protocol'] == proto), None)
        if not protocol:
            protocol = {'protocol': proto}
            self._data['protocols'].append(protocol)
        if 'scancodes' not in protocol:
            protocol['scancodes'] = {}
        protocol['scancodes'][scancode] = key

    def clear_key_scancodes(self, key: str):
        if 'protocols' not in self._data:
            return
        for protocol in self._data['protocols']:
            if 'scancodes' in protocol:
                protocol['scancodes'] = {
                    sc: k for sc, k in protocol['scancodes'].items() if k != key
                }

    def clear_all_scancodes(self):
        if 'protocols' not in self._data:
            return
        for protocol in self._data['protocols']:
            if 'scancodes' in protocol:
                protocol['scancodes'] = {}


class _KeyWidget(urwid.Columns):
    @staticmethod
    def _fmr_sc(sc):
        return '%s:0x%02x' % sc

    @staticmethod
    def _fmt_sc_list(sc_list, default=''):
        if not sc_list:
            return default
        return ' '.join(map(__class__._fmr_sc, sc_list))

    def __init__(self, key, scodes, *, cb_add, cb_clear):
        w_btn_add = None
        if cb_add:
            w_btn_add = urwid.Button('Add')
            urwid.connect_signal(w_btn_add, 'click', lambda w: cb_add(key))

        w_btn_clear = urwid.Button('Clear')
        urwid.connect_signal(w_btn_clear, 'click', lambda w: cb_clear(key))

        self._w_scodes = urwid.Text('')
        self.set_scodes(scodes)
        super().__init__([
            ('weight', 2, urwid.Text(key)),
            ('pack', w_btn_add or urwid.Text('')),
            ('pack', w_btn_clear),
            ('weight', 4, self._w_scodes),
        ], 1)

    def set_scodes(self, scodes):
        self._w_scodes.set_text(__class__._fmt_sc_list(
            scodes) if scodes else ('ss.yellow.fg', '(not set)'))


class _KeyListWidget(urwid.ScrollBar):
    def __init__(self, key_scodes, *, cb_add, cb_clear):
        self._cb_add = cb_add
        self._cb_clear = cb_clear
        self._key_widgets = {}
        self._w_walker = urwid.SimpleFocusListWalker([])
        self.set_key_scodes(key_scodes)
        super().__init__(urwid.ListBox(self._w_walker))

    def set_key_scodes(self, key_scodes, new_set_focus=False):
        key_scodes = dict(key_scodes)
        # update
        for key, w in self._key_widgets.items():
            w.set_scodes(key_scodes.pop(key, None))
        # add new
        if key_scodes:
            for key, scodes in key_scodes.items():
                self._key_widgets[key] = _KeyWidget(
                    key, scodes,
                    cb_add=self._cb_add, cb_clear=self._cb_clear,
                )
                self._w_walker.append(self._key_widgets[key])
            if new_set_focus:
                self._w_walker.set_focus(len(self._w_walker) - 1)

    def set_from_keymap(self, keymap: RCKeymap, new_set_focus=False):
        self.set_key_scodes(keymap.all_scancodes_by_key(), new_set_focus)


class _KeyAddWidget(urwid.Pile):
    _all_keys = {
        k: k[4:] for v in evdev.ecodes.keys.values() for k in (v if isinstance(v, tuple) else (v, ))
    }

    def __init__(self, *, cb_key_add: typing.Callable):
        self._cb_key_add = cb_key_add
        self.w_info = urwid.Text('')
        self.w_grid = None
        self.w_edit = urwid.Edit('Search for a key to add: ')
        urwid.connect_signal(self.w_edit, 'change', self._on_change)
        super().__init__([
            ('pack', urwid.Columns([
                self.w_edit,
                ('pack', self.w_info),
            ], 1)),
        ])

    def clear(self):
        self.w_edit.set_edit_text('')

    def _on_change(self, w, text):
        keys = self._search_keys(text) if text else []
        self.w_info.set_text(
            ('ss.cyan.fg', '(select a key to add)') if keys else '',
        )

        if not keys:
            self.contents = [self.contents[0]]
            self.w_grid = None
            return

        def btn(key):
            w = urwid.Button(key)
            urwid.connect_signal(w, 'click', lambda w: self._cb_key_add(key))
            return w

        if not self.w_grid:
            self.w_grid = urwid.GridFlow([], 0, 1, 0, align='center')
            self.contents.append((self.w_grid, ('pack', None)))
        self.w_grid.contents = [(btn(k), ('given', len(k) + 4)) for k in keys]

    def _search_keys(self, text: str, max=20):
        text = text.upper()
        res = []
        for k, n in __class__._all_keys.items():
            if text in n:
                res.append(k)
        res.sort(key=len)
        return res[:max]


class RCKeymapConfigurator():
    _default_keys = [
        'KEY_UP',
        'KEY_LEFT',
        'KEY_RIGHT',
        'KEY_DOWN',
        'KEY_ENTER',
        'KEY_ESC',
        'KEY_POWER',
        'KEY_RESTART',
    ]

    def __init__(
        self,
        keymap: RCKeymap,
        dev: RCDevice | None,
        *,
        cb_draw_screen: typing.Callable,
        default_keys: list[str] = _default_keys,
    ):
        self._keymap = keymap
        self._dev = dev
        self._dev_lirc = dev and dev.lirc0
        self._cb_draw_screen = cb_draw_screen
        self._default_keys = default_keys
        self._monitor_task = None
        self._changed = False
        self._w = urwid.Frame(None)
        self._w.header = urwid.Filler(
            urwid.Text('RC/IR device (lirc): %s [%s] [%s]' % (
                self._dev_lirc.path,
                self._dev_lirc.dev_number,
                self._dev_lirc.dev_path,
            ) if self._dev_lirc else ('ss.yellow.fg', 'RC/IR device not available, cannot add new keys!')),
            bottom=1,
        )
        self._key_add_widget = _KeyAddWidget(
            cb_key_add=lambda key: self._monitor_start(key),
        )
        self._key_list_widget = _KeyListWidget(
            {k: [] for k in self._default_keys},
            cb_add=(
                lambda key: self._monitor_start(key)
            ) if self._dev_lirc else None,
            cb_clear=lambda key: self._update_key(key, None),
        )
        if self._dev_lirc:
            self._w.body = urwid.Pile([
                ('pack', urwid.Filler(self._key_add_widget, bottom=1)),
                self._key_list_widget,
            ])
        else:
            self._w.body = self._key_list_widget
        self.update()

    @property
    def keymap(self):
        return self._keymap

    @property
    def changed(self):
        return self._changed

    @property
    def widget(self):
        return self._w

    def _set_footer(self, w: urwid.Widget | None, attr_map=None):
        if not w:
            self._w.footer = None
            return
        w_footer = urwid.Filler(urwid.Padding(
            w, left=2, right=2,
        ), top=1, bottom=1)
        if attr_map:
            w_footer = urwid.AttrMap(w_footer, attr_map)
        self._w.footer = urwid.Filler(w_footer, top=1)

    def _cb_monitor(self, key: str, scodes=[], proto_err=None):
        def contents():
            t = 'Receiving, press a key for %s on the remote control...' % key
            yield urwid.Text(t)
            if proto_err:
                t = 'Failed to enable all RC protocols, permission denied. Not all remotes will be detected!'
                yield urwid.Filler(urwid.Text(t, align='center'), top=1)
            t = '(press the same key 3 times to confirm, wait 5 sec. to cancel)'
            yield urwid.Filler(urwid.Text(_KeyWidget._fmt_sc_list(scodes) if scodes else t, align='right'), top=1)
        self._set_footer(urwid.Pile(contents()), 'ss.cyan.bg')
        self._cb_draw_screen()

    def _cb_monitor_done(self, key: str, scode=None):
        if scode:
            self._update_key(key, scode)
            self._set_footer(urwid.Text(('ss.green.fg', 'Added code %s to %s.' % (
                _KeyWidget._fmr_sc(scode), key)), align='center'))
        else:
            self._set_footer(None)
        self._cb_draw_screen()

    def _monitor_start(self, key: str, timeout=5):
        if self._monitor_task:
            return

        async def task():
            # XXX: investigate if all resources are cleaned properly
            #      with the timeout and the cancelled tasks
            async with asyncio.timeout(timeout*1.5) as tm:
                scodes = []
                last_ts = 0

                def cb_start(dev, stop, proto_org, proto_err):
                    self._cb_monitor(key, scodes, proto_err)

                def cb_lirc(dev, stop, sc):
                    nonlocal scodes, last_ts
                    tm.reschedule(asyncio.get_running_loop().time() + timeout)
                    if last_ts == 0:  # ignore first scancode
                        last_ts = sc.timestamp
                    elif sc.timestamp - last_ts > 1e9/4:  # debounce 250ms
                        last_ts = sc.timestamp
                        scodes.append((sc.rc_proto_name, sc.scancode))
                        scodes = scodes[-5:]
                        self._cb_monitor(key, scodes)
                        if scodes and scodes[-3:].count(scodes[-1]) == 3:
                            stop()

                with contextlib.suppress(asyncio.CancelledError):
                    # grab event device to avoid current keys firing
                    with evdev_open_device(self._dev.input0.event0).grab_context():
                        await rc_monitor(
                            self._dev,
                            cb_start=cb_start,
                            cb_lirc=cb_lirc,
                        )

                    if scodes:
                        self._cb_monitor_done(key, scodes[-1])
                        await asyncio.sleep(2)

        def done(tsk):
            exc = tsk.exception()
            if exc and not isinstance(exc, TimeoutError):
                raise exc
            self._cb_monitor_done(key)
            self._monitor_task = None

        self._monitor_task = asyncio.get_running_loop().create_task(task())
        self._monitor_task.add_done_callback(done)

    def _update_key(self, key, scode):
        self._changed = True
        if scode:
            self._keymap.set_scancode(scode[0], scode[1], key)
        else:
            self._keymap.clear_key_scancodes(key)
        self._key_list_widget.set_from_keymap(self.keymap, True)

    def update(self):
        self._key_add_widget.clear()
        self._key_list_widget.set_from_keymap(self.keymap)

    def clear(self):
        self._changed = True
        self._keymap.clear_all_scancodes()
        self._key_add_widget.clear()
        self._key_list_widget.set_from_keymap(self.keymap)

    def close(self):
        if self._monitor_task:
            self._monitor_task.cancel()
