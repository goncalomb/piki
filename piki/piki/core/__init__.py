import asyncio
import logging
import os
import subprocess

import evdev
import urwid

from .. import piki_version
from ..plugin import Plugin, PluginControl, PluginEvents, UIInternals
from ..utils import venv_find_dir
from ..utils.linux.input import input_find_devices
from ..utils.pkg.evdev import evdev_open_device
from ..utils.pkg.urwid import ConfigurableMenu, ss_make_default_palette
from ..utils.pkg.urwid_window import Window, WindowFlags, WindowManager
from ..utils.plugin import load_plugins
from . import ui

logger = logging.getLogger(__name__)


class UILoopController():
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
        return UIInternals(self._main_loop, self._w_root, self._wm, self._wd_menu, self._w_frame, self._w_menu)

    def _default_palette(self):
        for p in ss_make_default_palette():
            yield p
        yield 'piki.menu.button.label', '', ''
        yield 'piki.menu.button/focus.label', 'standout', ''
        yield 'piki.menu.button.wrap', '', '',
        yield 'piki.menu.button/focus.wrap', 'dark cyan', ''

    def _ui_reset(self):
        self._w_menu = ConfigurableMenu('piki.menu')
        self._w_frame = urwid.Frame(self._w_menu)
        self._wm = WindowManager()
        self._wd_menu = self._wm.root.make_window(
            self._w_frame,
            title='PiKi Menu',
            flags=WindowFlags.DEFAULT_NO_CLOSE,
        )
        self._w_root = urwid.WidgetPlaceholder(self._wm.widget)
        if (self._main_loop):
            self._main_loop.widget = self._w_root
            self._main_loop.screen.register_palette(self._default_palette())

    def _run(self, main, unhandled_input):
        self._event_loop = urwid.AsyncioEventLoop()
        self._event_loop.alarm(0, main)

        self._main_loop = urwid.MainLoop(
            self._w_root, self._default_palette(),
            event_loop=self._event_loop,
            unhandled_input=unhandled_input,
        )

        self._main_loop.run()


class InputController():
    def start(self, input_key):
        def get_relevant_devices():
            # find all input devices that declare at least one KEY capability
            for dev in input_find_devices():
                if dev.uevent_var('KEY', '0') != '0' and dev.event0:
                    yield dev.event0

        # TODO: more error handling
        # TODO: properly detect when devices are connected/disconnected,
        #       detecting new devices requires a NETLINK_KOBJECT_UEVENT socket
        #       this is how libs like libinput/libudev work, we could just
        #       use libinput, but i think it's a good exercise to explore the
        #       netlink kernel sockets and expand our piki.utils.linux package
        # TODO: we could also rewrite the evdev package in pure python...

        async def read_device(dev):
            try:
                event_io = evdev_open_device(dev)
                logger.info("Reading input events from '%s'" % dev.dev_path)
                while evs := await event_io.async_read():
                    for ev in evs:
                        if ev.type == evdev.ecodes.EV_KEY and ev.value in [0, 1]:
                            names = evdev.ecodes.keys[ev.code] if ev.code in evdev.ecodes.keys else '0x%02x' % ev.code
                            input_key(PluginEvents.InputKeyEvent(
                                ev.code,
                                (names,) if isinstance(names, str) else names,
                                'down' if ev.value else 'up',
                            ))
            except OSError as e:
                logger.warning("Error reading device '%s'" % dev.dev_path)
                logger.warning(e)

        loop = asyncio.get_running_loop()
        for dev in get_relevant_devices():
            loop.create_task(read_device(dev))

    def stop(self):
        # TODO: proper cleanup, just let the tasks be cancelled by
        #       the loop shutdown for now
        pass


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
        self._event_ctl = InputController()

    def _cb_plugin_init(self, p):
        p.ctl = PluginControlImpl(self)
        p.evt = PluginEventsImpl()

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
        # TODO: add some way to sort plugins, 'order' field?
        #       for now just sort by name (internal only)
        self._plugins.sort(key=lambda p: p.name, reverse=True)

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
        self._event_ctl.start(self._input_key)
        for p in self._plugins:
            p.on_main()

    def _unhandled_input(self, data):
        for p in self._plugins:
            p.evt.input_urwid.fire(PluginEvents.InputUrwidEvent(data))
        return True

    def _input_key(self, ev):
        def cb():
            for p in self._plugins:
                p.evt.input_key.fire(ev)
        self._loop_ctl._event_loop.alarm(0, cb)

    def run(self):
        logger.info("Starting PiKi v%s" % piki_version)
        logger.info("piki_venv_dir = %s" % self.piki_venv_dir)
        logger.info("piki_dir = %s" % self.piki_dir)
        logger.info("piki_plugins_dir = %s" % self.piki_plugins_dir)

        self._load_plugins()

        try:
            self._loop_ctl._run(self._main, self._unhandled_input)
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

    def sys_exec(self, args, check=True, output=False):
        return subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if output else subprocess.DEVNULL,
            stderr=subprocess.PIPE if output else subprocess.DEVNULL,
            check=check,
            text=True,
        )

    def sys_reboot(self):
        try:
            self.sys_exec(['sudo', '-n', 'reboot'])
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    def sys_poweroff(self):
        try:
            self.sys_exec(['sudo', '-n', 'poweroff'])
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

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

    def ui_window_open(self, *args, **kwargs):
        self._loop_ctl._wm.root.open_window(*args, **kwargs)

    def ui_window_make(self, *args, **kwargs):
        return self._loop_ctl._wm.root.make_window(*args, **kwargs)

    def ui_window_close_top(self):
        wd_top = self._loop_ctl._wm.root.first_child
        if wd_top:
            wd_top.close()

    def ui_window_close_all(self):
        for wd in list(self._loop_ctl._wm.root.children):
            wd.close()

    def ui_message_box(
        self, body, *,
        buttons='OK',
        callback=None,
        autoclose=True,
        parent: Window | None = None,
        title='',
    ):
        wd_p = self._loop_ctl._wm.root
        if parent and parent.is_open:
            wd_p = parent
        elif self._loop_ctl._wd_menu.is_open:
            wd_p = self._loop_ctl._wd_menu
        return wd_p.make_window(
            ui.message_box(
                body,
                buttons=buttons,
                callback=callback,
                autoclose=autoclose,
            ),
            title=title,
            flags=WindowFlags.DEFAULT_NO_CLOSE,
            overlay=True,
        )


class PluginEventsImpl(PluginEvents):
    class Handlers(PluginEvents.Handlers):
        def __init__(self):
            self._handlers = set()

        def on(self, cb):
            self._handlers.add(cb)

        def off(self, cb):
            # copy to avoid changing the set while iterating
            self._handlers = set(self._handlers)
            self._handlers.discard(cb)

        def fire(self, ev):
            for h in self._handlers:
                h(ev)

    input_urwid: Handlers
    input_key: Handlers

    def __init__(self):
        self.input_urwid = self.Handlers()
        self.input_key = self.Handlers()
