import asyncio
import contextlib
import subprocess

import urwid
from piki.plugin import Plugin
from piki.utils.pkg.urwid import (ss_16color_names, ss_attr_map_style,
                                  ss_make_boxbutton, ss_make_button)


class SystemMenuPlugin(Plugin):
    def _run(self, args):
        return subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @contextlib.contextmanager
    def _run_safe_ctx(self):
        try:
            yield
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            self.logger.exception("Subprocess exception", exc_info=e)

    def _run_safe(self, args):
        with self._run_safe_ctx():
            return self._run(args)

    def _run_message_box(self, args, message, btn_label, btn_ss_style):
        self.ctl.ui_message_box(message, title='System', buttons=[
            'Cancel',
            (btn_label, btn_ss_style, lambda *_: self._run_safe(args)),
        ])

    def _show_log(self):
        async def task():
            with self._run_safe_ctx():
                # TODO: remove hardcoded vts
                self._run(['chvt', '1'])
                await asyncio.sleep(5)
                self._run(['chvt', '7'])
        self.ctl.loop_asyncio.create_task(task())

    def _win_show_palette(self, wh):
        prefix = 'ss'

        def btn(label, color):
            return ss_attr_map_style(ss_make_button(label), 'button', f'{prefix}.{color}')

        def box(label, color):
            return ss_attr_map_style(ss_make_boxbutton(label), 'boxbutton', f'{prefix}.{color}')

        exit_button = btn('Close/Exit', 'white')
        urwid.signals.connect_signal(
            exit_button.base_widget, 'click', lambda w: wh.close())

        c_names = list(map(lambda x: x[0], ss_16color_names()))
        return urwid.Padding(urwid.Filler(urwid.Pile([
            urwid.Padding(exit_button, width=20),
            urwid.Text(''),
            urwid.Text((
                f'{prefix}.white/bright.fg',
                'PiKi Standard Style (ss) default palette attributes:',
            )),
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
        ])), left=2, right=2)

    def on_ui_create(self):
        def show_palette():
            self.ctl.ui_window_open(self._win_show_palette)

        def reboot():
            self._run_message_box(
                ['sudo', '-n', 'reboot'],
                'Reboot the system?', 'Reboot', 'ss.yellow'
            )

        def shutdown():
            self._run_message_box(
                ['sudo', '-n', 'shutdown'],
                'Shutdown the system?', 'Shutdown', 'ss.red'
            )

        self.ctl.ui_menu_setup_root(buttons=[
            ('System', 'piki.menu.system'),
        ])
        self.ctl.ui_menu_setup('piki.menu.system', title='System', buttons=[
            ('Show system log (5 sec.)', self._show_log),
            ('Show standard style palette', show_palette),
            ('Restart PiKi', self.ctl.loop_stop),
            ('Reboot', reboot),
            ('Shutdown', shutdown),
        ])
