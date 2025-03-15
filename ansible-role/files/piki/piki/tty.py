import logging
import subprocess
import time
import traceback

import urwid

from . import internal, util


def on_button_press(button, user_data):
    try:
        if user_data == 'show_log':
            util.process_check_call(['chvt', '1'])
            time.sleep(5)
            util.process_check_call(['chvt', '7'])
        elif user_data == 'reset_tty':
            util.process_check_call(
                ['systemctl', 'restart', 'piki-tty'], sudo=True)
        elif user_data == 'reboot':
            util.process_check_call(['reboot'], sudo=True)
        elif user_data == 'poweroff':
            util.process_check_call(['poweroff'], sudo=True)
    except subprocess.CalledProcessError:
        traceback.print_exc()


class MainFrame(urwid.WidgetWrap):
    def __init__(self):
        buttons = urwid.GridFlow([
            urwid.Button('show log', on_button_press, 'show_log'),
            urwid.Button('reset tty', on_button_press, 'reset_tty'),
            urwid.Button('reboot', on_button_press, 'reboot'),
            urwid.Button('poweroff', on_button_press, 'poweroff'),
        ], 15, 2, 0, 'center')
        body = urwid.Filler(urwid.Pile([
            urwid.Text("ACTIONS", 'center'),
            urwid.Divider(),
            buttons,
        ]))
        header = urwid.Filler(urwid.Pile([
            urwid.Text("PiKi: Raspberry [Pi Ki]osk", 'center'),
            urwid.Divider(),
            urwid.Text(util.get_local_ips(), 'center'),
        ]), top=1)
        super().__init__(urwid.Frame(body, header=header))


def main():
    logging.basicConfig(level=logging.INFO)
    ctl = internal.core.Controller()
    ctl.load()
    overlay = urwid.Overlay(
        MainFrame(),
        urwid.SolidFill("\N{MEDIUM SHADE}"),
        urwid.CENTER, (urwid.RELATIVE, 80), urwid.MIDDLE, (urwid.RELATIVE, 80),
    )
    ctl.main_loop(overlay)
