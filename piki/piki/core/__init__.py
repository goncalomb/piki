import asyncio
import logging
import os

import urwid

from .. import piki_version
from ..plugin import Plugin, PluginControl, UIInternals
from ..utils import venv_find_dir
from ..utils.pkg import urwid as tui
from ..utils.plugin import load_plugins

logger = logging.getLogger(__name__)


class UILoopController():
    _default_palette = [
        ('piki.menu.focused', 'standout', ''),
        ('piki.menu.disabled', 'dark gray', ''),
    ]

    def __init__(self):
        self._main_loop = None
        self._event_loop = None
        self._ui_reset()

    @property
    def asyncio_loop(self):
        # XXX: we are accessing urwid internals here (_loop)
        return self._event_loop._loop

    @property
    def internals(self):
        return UIInternals(self._main_loop, self._w_root, self._w_frame)

    def _ui_reset(self):
        self._w_menu = tui.ConfigurableMenu('piki.menu')
        self._w_frame = urwid.Frame(self._w_menu)
        self._w_root = urwid.WidgetPlaceholder(self._w_frame)
        if (self._main_loop):
            self._main_loop.widget = self._w_root
            self._main_loop.screen.register_palette(self._default_palette)

    def _run(self, main):
        self._event_loop = urwid.AsyncioEventLoop()
        self._event_loop.alarm(0, main)

        self._main_loop = urwid.MainLoop(
            self._w_root, self._default_palette,
            event_loop=self._event_loop,
        )

        self._main_loop.run()


class CoreController():
    piki_venv_dir = venv_find_dir()
    piki_dir = os.path.dirname(piki_venv_dir) if piki_venv_dir else os.getcwd()
    piki_plugins_dir = os.path.join(piki_dir, 'plugins')
    piki_plugins_internal_dir = os.path.join(
        os.path.dirname(__file__), 'plugins',
    )

    def __init__(self):
        self._plugins = []  # TODO: type hinting on 'utils.plugin'
        self._loop_ctl = UILoopController()

    def _cb_plugin_init(self, p):
        p.ctl = PluginControlImpl(self)

    def _cb_plugin_internal_init(self, p):
        self._cb_plugin_init(p)
        p.internal = True
        p.name = 'internal:' + p.name

    def _load_plugins(self):
        logger.info("Loading plugins")

        self._plugins = load_plugins(
            self.piki_plugins_internal_dir,
            Plugin,
            self._cb_plugin_internal_init,
        )
        if os.path.isdir(self.piki_plugins_dir):
            self._plugins += load_plugins(
                self.piki_plugins_dir,
                Plugin,
                self._cb_plugin_init,
            )
        else:
            logger.warning("Plugins directory does't exist")

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

    def _ui_reset(self):
        for p in self._plugins:
            p.on_ui_destroy()

        self._loop_ctl._ui_reset()

        for p in self._plugins:
            p.on_ui_create()

    def _main(self):
        for p in self._plugins:
            p.on_main()

    def run(self):
        logger.info("Starting PiKi v%s" % piki_version)
        logger.info("piki_venv_dir = %s" % self.piki_venv_dir)
        logger.info("piki_dir = %s" % self.piki_dir)
        logger.info("piki_plugins_dir = %s" % self.piki_plugins_dir)

        self._load_plugins()

        try:
            self._loop_ctl._run(self._main)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.exception("Uncaught exception", exc_info=e)

        self._unload_plugins()

        # because urwid uses run_forever internally we do some extra
        # cleanup here, similarly to what the default runner does
        # https://github.com/python/cpython/blob/main/Lib/asyncio/runners.py
        # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.close
        loop = self._loop_ctl.asyncio_loop
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


class PluginControlImpl(PluginControl):
    def __init__(self, ctl: CoreController):
        self._core_ctl = ctl
        self._loop_ctl = ctl._loop_ctl
        self._draw_screen_handle = None

    @property
    def loop_asyncio(self):
        return self._loop_ctl.asyncio_loop

    def loop_call_later(self, delay, callback):
        return self._loop_ctl._event_loop.alarm(delay, callback)

    def loop_stop(self):
        def cb():
            raise urwid.ExitMainLoop()
        self.loop_call_later(0, cb)
        # raise urwid.ExitMainLoop()

    @property
    def ui_internals(self):
        return self._loop_ctl.internals

    def ui_draw_screen(self):
        if self._loop_ctl._main_loop and not self._draw_screen_handle:
            def cb():
                self._draw_screen_handle = None
            self._draw_screen_handle = self.loop_call_later(0, cb)

    def ui_reset(self):
        self.loop_call_later(0, self._core_ctl._ui_reset)

    def ui_menu_setup(self, key, *, title=None, buttons=..., append=True, replace=True):
        self.ui_draw_screen()
        self._loop_ctl._w_menu.menu_setup(
            key,
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def ui_menu_setup_root(self, *, title=None, buttons=..., append=False, replace=False):
        self.ui_draw_screen()
        self._loop_ctl._w_menu.menu_setup_root(
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def ui_menu_remove(self, key):
        self.ui_draw_screen()
        self._loop_ctl._w_menu.menu_remove(key)
