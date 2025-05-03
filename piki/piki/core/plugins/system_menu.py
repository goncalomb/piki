import subprocess

import urwid
from piki.plugin import Plugin
from piki.utils.pkg.urwid import (ss_16color_names, ss_attr_map_style,
                                  ss_make_boxbutton, ss_make_button)
from piki.utils.pkg.urwid_window import Window


class JournalLogWindow(Window):
    def __init__(
        self, *,
        comm: str | None = None,
        max_entries=75,
    ):
        self._comm = comm
        self._max_entries = max_entries
        title = 'Log Entries (journalctl) [%smax: %d]' % (
            'comm: %s, ' % self._comm if self._comm else '',
            self._max_entries,
        )
        super().__init__(
            self._make_widget(),
            title=title,
            overlay={
                'width': ('relative', 95),
                'height': ('relative', 85),
            },
        )

    def _journal_entries(self):
        # XXX: consider running the process in the executor (thread)
        #      to avoid blocking the ui
        args = ['journalctl', '-n', str(self._max_entries)]
        if self._comm:
            args += ['_COMM=%s' % self._comm]
        with subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        ) as p:
            with p.stdout as fp:
                while line := fp.readline():
                    l = line.strip().split(']: ', 1)
                    yield (l[0] + ']: ', l[1]) if len(l) > 1 else ('', l[0])
            try:
                status = p.wait(timeout=2)
                if status:
                    yield ('', 'Failed to get log entries!')
                    yield ('', '(journalctl exit status %d)' % status)
            except:
                p.kill()
                raise

    def _make_widget(self):
        w_close = urwid.Button('Close')
        urwid.connect_signal(w_close, 'click', lambda w: self.close())
        w_top = urwid.Button('Top')
        urwid.connect_signal(w_top, 'click', lambda w: w_walker.set_focus(0))

        def contents():
            for l in self._journal_entries():
                yield urwid.Text([('ss.cyan.fg', l[0]), l[1]])
            yield urwid.Filler(urwid.Padding(urwid.Columns([
                ('pack', w_close),
                ('pack', w_top),
            ], 1), 'center', 'clip'), top=1)

        w_walker = urwid.SimpleFocusListWalker(list(contents()))
        w_walker.set_focus(len(w_walker) - 1)
        return urwid.Padding(urwid.ScrollBar(urwid.Padding(urwid.ListBox(w_walker), right=1)), left=1)


class SystemMenuPlugin(Plugin):
    def _message_box(self, cb, message, btn_label, btn_ss_style):
        self.ctl.ui_message_box(message, title='System', buttons=[
            'Cancel',
            (btn_label, btn_ss_style, lambda *_: cb()),
        ])

    def _show_system_information(self):
        def cmd_text(args):
            text = self.ctl.sys_exec(args, output=True).stdout.strip()
            text = '\n'.join(map(lambda x: '  ' + x, text.split('\n')))
            return urwid.Text(text)
        try:
            contents = [
                urwid.Text(('ss.cyan.fg', 'uname -a')),
                cmd_text(['uname', '-a']),
                urwid.Text(('ss.cyan.fg', 'uptime')),
                cmd_text(['uptime']),
                urwid.Text(('ss.cyan.fg', 'free --si -ht')),
                cmd_text(['free', '--si', '-ht']),
                urwid.Text(('ss.cyan.fg', 'hostname -I')),
                cmd_text(['hostname', '-I']),
                urwid.Text(('ss.cyan.fg', 'df -H')),
                cmd_text(['df', '-H']),
            ]
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            self.logger.exception('Error executing command.', exc_info=e)
            contents = [
                urwid.Filler(
                    urwid.Text('Error executing command.', align='center'),
                    top=1, bottom=1,
                ),
                urwid.Text(repr(e), align='center'),
                urwid.Text(str(e), align='center'),
            ]
        self.ctl.ui_window_make(
            urwid.Padding(urwid.ScrollBar(urwid.Padding(
                urwid.ListBox(contents), right=1,
            )), left=1),
            title='System Information',
            overlay={
                'width': ('relative', 80),
                'height': ('relative', 75),
            }
        )

    def _show_log(self, comm: str | None = None):
        self.ctl.ui_window_open(
            JournalLogWindow(comm=comm),
        )

    def _win_show_palette(self, wd):
        prefix = 'ss'

        def btn(label, color):
            return ss_attr_map_style(ss_make_button(label), 'button', f'{prefix}.{color}')

        def box(label, color):
            return ss_attr_map_style(ss_make_boxbutton(label), 'boxbutton', f'{prefix}.{color}')

        exit_button = btn('Close/Exit', 'white')
        urwid.signals.connect_signal(
            exit_button.base_widget, 'click', lambda w: wd.close())

        c_names = list(map(lambda x: x[0], ss_16color_names()))
        return urwid.ScrollBar(urwid.Filler(urwid.Padding(urwid.ListBox([
            urwid.Padding(exit_button, width=20),
            urwid.Text(''),
            urwid.Text([
                (f'{prefix}.cyan.fg', 'urwid.Button'),
                f' styled with {prefix}.[color]:',
            ]),
            urwid.Text(''),
            urwid.Columns([btn(c, c) for c in c_names], 1),
            urwid.Text(''),
            urwid.Text([
                (f'{prefix}.cyan.fg', 'piki.utils.pkg.urwid.BoxButton'),
                f' styled with {prefix}.[color]:',
            ]),
            urwid.Text(''),
            urwid.Columns([box(c, c) for c in c_names], 1),
            urwid.Text(''),
            urwid.Text('Basic 16 color attributes:'),
            urwid.Text(''),
            urwid.Columns([('pack', urwid.Text(f'       {prefix}.[color].fg:'))] +
                          [urwid.Text((f'{prefix}.{c}.fg', c)) for c in c_names], 1),
            urwid.Columns([('pack', urwid.Text(f'       {prefix}.[color].bg:'))] +
                          [urwid.Text((f'{prefix}.{c}.bg', c)) for c in c_names], 1),
            urwid.Columns([('pack', urwid.Text(f'{prefix}.[color]/bright.fg:'))] +
                          [urwid.Text((f'{prefix}.{c}/bright.fg', c)) for c in c_names], 1),
            urwid.Columns([('pack', urwid.Text(f'{prefix}.[color]/bright.bg:'))] +
                          [urwid.Text((f'{prefix}.{c}/bright.bg', c)) for c in c_names], 1),
        ]), left=1, right=1), top=1, bottom=1, height=('relative', 100)))

    def on_ui_create(self):
        def show_palette():
            self.ctl.ui_window_make(
                self._win_show_palette,
                title='PiKi Standard Style (ss) default palette and attributes',
                overlay={
                    'width': ('relative', 95),
                    'height': ('relative', 85),
                }
            )

        def reboot():
            self._message_box(
                lambda: self.ctl.sys_reboot(),
                'Reboot the system?', 'Reboot', 'ss.yellow'
            )

        def shutdown():
            self._message_box(
                lambda: self.ctl.sys_shutdown(),
                'Shutdown the system?', 'Shutdown', 'ss.red'
            )

        self.ctl.ui_menu_setup_root(buttons=[
            ('System', 'piki.menu.system'),
        ])
        self.ctl.ui_menu_setup('piki.menu.system', title='System', buttons=[
            ('Show system information', self._show_system_information),
            ('Show system log', lambda: self._show_log()),
            ('Show piki-core log', lambda: self._show_log('piki-core')),
            ('Show standard style palette', show_palette),
            ('Restart PiKi', self.ctl.loop_stop),
            ('Reboot', reboot),
            ('Shutdown', shutdown),
        ])
