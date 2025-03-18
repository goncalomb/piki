import logging
import os
import subprocess
import time
from collections.abc import Callable

import urwid

from .. import util
from . import plugin, tui

logger = logging.getLogger(__name__)


def _system_action(action):
    try:
        if action == 'show_log':
            util.process_check_call(['chvt', '1'])
            time.sleep(5)
            util.process_check_call(['chvt', '7'])
        elif action == 'reset_tty':
            util.process_check_call(
                ['systemctl', 'restart', 'piki-tty'], sudo=True)
        elif action == 'reboot':
            util.process_check_call(['reboot'], sudo=True)
        elif action == 'power_off':
            util.process_check_call(['poweroff'], sudo=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.exception(
            "Exception while performing system action", exc_info=e)


class UIController():
    def __init__(self):
        self._w_menu = None
        self._w_wrap = urwid.WidgetPlaceholder(None)
        self.recreate()

    def recreate(self):
        self._w_menu = tui.ConfigurableMenu('piki.menu')
        self._w_menu.add_root_menu_buttons([
            ('Configuration', 'piki.menu.config'),
            ('System', 'piki.menu.system'),
        ])
        self._w_menu.add_menu('piki.menu.system', 'System', [
            ('Show system log (5 sec.)', lambda: _system_action('show_log')),
            ('Reset TTY', lambda: _system_action('reset_tty')),
            ('Restart', lambda: _system_action('reboot')),
            ('Power off', lambda: _system_action('power_off')),
        ])

        w_header = urwid.Filler(urwid.Pile([
            urwid.Text(Controller.piki_header_message, 'center'),
        ]), top=1, bottom=1)

        w_body = urwid.Padding(self._w_menu, 'center', ('relative', 40))

        w_footer = urwid.Filler(urwid.Pile([
            urwid.Text(Controller.piki_footer_message, 'center'),
        ]), top=1, bottom=1)

        self._w_wrap.original_widget = urwid.Frame(w_body, w_header, w_footer)

    def get(self):
        w_overlay = urwid.Overlay(
            self._w_wrap,
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            'center', ('relative', 80),
            'middle', ('relative', 80),
        )
        palette = [
            ('piki.menu.focused', 'standout', ''),
            ('piki.menu.disabled', 'dark gray', ''),
        ]
        return w_overlay, palette


class Controller():
    piki_venv_dir = util.find_venv_dir()
    piki_dir = os.path.dirname(piki_venv_dir) if piki_venv_dir else os.getcwd()
    piki_plugins_dir = os.path.join(piki_dir, 'plugins')
    piki_version = util.find_piki_version('(unknown)')
    piki_source_url = "https://github.com/goncalomb/piki"
    piki_header_message = "PiKi: Raspberry [Pi Ki]osk"
    piki_footer_message = "piki v%s \N{BULLET} %s" % (
        piki_version, piki_source_url,
    )

    def __init__(self):
        self._plugins = []
        self._ui = UIController()
        logger.info("Starting PiKi Core")
        logger.info("piki_venv_dir = %s" % self.piki_venv_dir)
        logger.info("piki_dir = %s" % self.piki_dir)
        logger.info("piki_plugins_dir = %s" % self.piki_plugins_dir)

    def _cb_plugin_init(self, plugin):
        plugin.ctl = PluginControl(self)

    def _load_plugins(self):
        if os.path.isdir(self.piki_plugins_dir):
            self._plugins = plugin._load_plugins(
                self.piki_plugins_dir,
                Plugin,
                self._cb_plugin_init,
            )

        for p in self._plugins:
            p.on_load()

        logger.info("Loaded %d plugin(s): %s" % (
            len(self._plugins),
            [p.name for p in self._plugins],
        ))

        for p in self._plugins:
            p.on_ui_create()

    def ui_recreate(self):
        for p in self._plugins:
            p.on_ui_destroy()

        self._ui.recreate()

        for p in self._plugins:
            p.on_ui_create()

    def main_loop(self):
        self._load_plugins()

        widget, palette = self._ui.get()
        loop = urwid.MainLoop(widget, palette)

        for p in self._plugins:
            p.on_main()

        loop.run()


class PluginControl():
    piki_dir: str

    def __init__(self, ctl):
        self._ctl = ctl
        self.piki_dir = ctl.piki_dir

    def ui_recreate(self):
        self._ctl.ui_recreate()

    def ui_menu_add(self, key: str, title: str, buttons: list[tuple[str, str | Callable[[], None]]] = []):
        self._ctl._ui._w_menu.add_menu(key, title, buttons)

    def ui_menu_remove(self, key: str):
        self._ctl._ui._w_menu.remove_menu(key)

    def ui_menu_buttons_add(self, key: str, buttons: list[tuple[str, str | Callable[[], None]]], top=False):
        self._ctl._ui._w_menu.add_menu_buttons(key, buttons)

    def ui_menu_root_buttons_add(self, buttons: list[tuple[str, str | Callable[[], None]]], top=True):
        self._ctl._ui._w_menu.add_root_menu_buttons(buttons)


class Plugin(plugin.Plugin):
    ctl: PluginControl

    def on_load(self): pass
    def on_main(self): pass
    def on_ui_create(self): pass
    def on_ui_destroy(self): pass
