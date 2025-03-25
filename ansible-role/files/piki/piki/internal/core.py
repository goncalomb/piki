import asyncio
import logging
import os
import subprocess
import time
import typing
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
        self._w_menu.setup_root_menu(buttons=[
            ('Configuration', 'piki.menu.config'),
            ('System', 'piki.menu.system'),
        ])
        self._w_menu.setup_menu('piki.menu.system', title='System', buttons=[
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
        self._main_loop = None

    def _cb_plugin_init(self, plugin):
        plugin.ctl = PluginControl(self)

    def _load_plugins(self):
        logger.info("Loading plugins")
        if os.path.isdir(self.piki_plugins_dir):
            self._plugins = plugin.load_plugins(
                self.piki_plugins_dir,
                Plugin,
                self._cb_plugin_init,
            )
        else:
            logger.info("Plugins directory does't exist")

        for p in self._plugins:
            p.on_load()

        logger.info("Loaded %d plugin(s): %s" % (
            len(self._plugins),
            [p.name for p in self._plugins],
        ))

        for p in self._plugins:
            p.on_ui_create()

    def _unload_plugins(self):
        logger.info("Unloading plugins")

        for p in self._plugins:
            p.on_ui_destroy()

        for p in self._plugins:
            p.on_unload()

    def ui_recreate(self):
        for p in self._plugins:
            p.on_ui_destroy()

        self._ui.recreate()

        for p in self._plugins:
            p.on_ui_create()

    def _main(self):
        for p in self._plugins:
            p.on_main()

    def run(self):
        logger.info("Starting PiKi v%s" % self.piki_version)
        logger.info("piki_venv_dir = %s" % self.piki_venv_dir)
        logger.info("piki_dir = %s" % self.piki_dir)
        logger.info("piki_plugins_dir = %s" % self.piki_plugins_dir)

        self._load_plugins()

        widget, palette = self._ui.get()
        event_loop = urwid.AsyncioEventLoop()
        event_loop.alarm(0, self._main)

        self._main_loop = urwid.MainLoop(
            widget, palette,
            event_loop=event_loop,
        )

        try:
            self._main_loop.run()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.exception("Uncaught exception", exc_info=e)

        self._unload_plugins()

        # because urwid uses run_forever internally we do some extra
        # cleanup here, similarly to what the default runner does
        # https://github.com/python/cpython/blob/main/Lib/asyncio/runners.py
        # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.close
        loop = event_loop._loop
        try:
            tasks = asyncio.tasks.all_tasks(loop)
            if tasks:
                logger.info("Cancelling %s pending task(s)" % len(tasks))
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(
                    *tasks, return_exceptions=True,
                ))
            logger.info("Stopping")
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

        logger.info("End")


class PluginControl():
    piki_dir: str

    def __init__(self, ctl):
        self._ctl = ctl
        self._draw_screen_handle = None
        self.piki_dir = ctl.piki_dir

    def loop_asyncio(self) -> asyncio.AbstractEventLoop:
        # XXX: we are accessing urwid internals here (_loop)
        return self._ctl._main_loop.event_loop._loop

    def loop_call_later(self, delay: float, callback: Callable[[], typing.Any]) -> asyncio.TimerHandle:
        return self._ctl._main_loop.event_loop.alarm(delay, callback)

    def loop_stop(self):
        def cb():
            raise urwid.ExitMainLoop()
        self.loop_call_later(0, cb)
        # raise urwid.ExitMainLoop()

    def ui_draw_screen(self):
        if self._ctl._main_loop and not self._draw_screen_handle:
            def cb():
                self._draw_screen_handle = None
            self._draw_screen_handle = self.loop_call_later(0, cb)

    def ui_recreate(self):
        self.loop_call_later(0, self._ctl.ui_recreate)

    def ui_setup_menu(
        self, key: str, *,
        title: str | None = None,
        buttons: list[tuple[str, str | Callable[[], None]]] = [],
        append=True, replace=True,
    ):
        self.ui_draw_screen()
        self._ctl._ui._w_menu.setup_menu(
            key,
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def ui_setup_root_menu(
        self, *,
        title: str | None = None,
        buttons: list[tuple[str, str | Callable[[], None]]] = [],
        append=False, replace=False,
    ):
        self.ui_draw_screen()
        self._ctl._ui._w_menu.setup_root_menu(
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def ui_remove_menu(self, key: str):
        self.ui_draw_screen()
        self._ctl._ui._w_menu.remove_menu(key)


class Plugin(plugin.Plugin):
    ctl: PluginControl

    def on_load(self): pass
    def on_unload(self): pass
    def on_main(self): pass
    def on_ui_create(self): pass
    def on_ui_destroy(self): pass
