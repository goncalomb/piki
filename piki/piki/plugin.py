import asyncio
import dataclasses
import typing

import urwid

from .utils import plugin as _plugin


@dataclasses.dataclass(frozen=True)
class UIInternals():
    main_loop: urwid.MainLoop | None
    w_root: urwid.WidgetPlaceholder
    w_frame: urwid.Frame


class PluginControl():
    @property
    def loop_asyncio(self) -> asyncio.AbstractEventLoop:
        """
        The underlying asyncio loop.
        """

    def loop_call_later(self, delay: float, callback: typing.Callable[[], typing.Any]) -> asyncio.TimerHandle:
        """
        Schedule callback on the event loop.
        """

    def loop_stop(self):
        """
        Stop the event loop and gracefully terminate the program.
        """

    @property
    def ui_internals(self) -> UIInternals:
        """
        The urwid internals. Contents may change, use at your own risk.

        Allows full control over the UI widgets.
        """

    def ui_draw_screen(self):
        """
        Schedule draw screen, this is required when manually changing the UI
        (i.e. creating/changing urwid widgets) from an async task.

        It's not required when changing the UI from 'on_ui_create', when
        calling other 'ctl.ui_XXX' functions, or when changing the UI from a
        'ctl.loop_call_later' callback.
        """

    def ui_reset(self):
        """
        Schedule UI reset, it will call 'on_ui_destroy' (all plugins)
        reset the internal UI widgets, and call 'on_ui_create' (all plugins).
        """

    def ui_menu_setup(
        self, key: str, *,
        title: str | None = None,
        buttons: list[tuple[str, str | typing.Callable[[], None]]] = [],
        append=True, replace=True,
    ):
        """
        Add/Configure menu.
        """

    def ui_menu_setup_root(
        self, *,
        title: str | None = None,
        buttons: list[tuple[str, str | typing.Callable[[], None]]] = [],
        append=False, replace=False,
    ):
        """
        Configure the root menu (e.g. add buttons).
        """

    def ui_menu_remove(self, key: str):
        """
        Remove menu.
        """


class Plugin(_plugin.Plugin):
    """
    Main lifecycle:
        (load internal plugins)
        (load user plugins)
        on_load
        (create internal ui widgets)
        on_ui_create
        (start event loop)
        on_main
        (event loop runs until asked to stop)
        on_ui_destroy
        on_unload

    Reset UI lifecycle:
        ('ui_reset' called)
        on_ui_destroy
        (recreate internal ui widgets)
        on_ui_create
    """

    internal = False
    ctl: PluginControl

    def on_load(self):
        """
        Called after the loading all the plugins.

        The event loop is NOT available.
        """

    def on_unload(self):
        """
        Called before terminating the program.

        The event loop is NOT available.
        """

    def on_main(self):
        """
        Called after starting the event loop.

        Put your main logic here (e.g. scheduling tasks).

        You should not run blocking code here (or on other lifecycle
        callbacks). Any blocking code should be run as asyncio tasks
        (coroutines), on the executor (threads), or as subprocesses.

        The event loop IS available.
        """

    def on_ui_create(self):
        """
        Called after resetting the UI and before the event loop starts.

        Create your UI here (e.g. call 'ctl.ui_XXX' functions or manually
        create urwid widgets).

        The event loop MAY NOT be available (don't use it).
        """

    def on_ui_destroy(self):
        """
        Called before resetting the UI and before terminating the program.

        Destroy your UI here (e.g. clear references to widgets or reset any
        UI state). There is no need to call any 'ctl.ui_XXX' functions because
        all the widgets are recreated internally.

        The event loop MAY NOT be available (don't use it).
        """
