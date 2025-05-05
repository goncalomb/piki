import enum
import typing

import urwid


class WindowEvent():
    def __init__(self, wd: 'Window', cancelable: bool = False):
        self._wd = wd
        self._cancelable = cancelable
        self._canceled = False

    @property
    def wd(self):
        return self._wd

    @property
    def cancelable(self):
        return self._cancelable

    @property
    def canceled(self):
        return self._canceled

    def cancel(self):
        if self._cancelable:
            self._canceled = True


class WindowFlags(enum.Flag):
    BASIC = 0
    """ basic: empty window with no style """
    ESC_CLOSE = enum.auto()
    """ escape close: close window with escape key """
    WS_BORDER = enum.auto()
    """ window style border: show window border """
    WS_TITLE = enum.auto()
    """ window style title: show window title """
    WS_CLOSE = enum.auto()
    """ window style close: show close button """
    WMS_TASK = enum.auto()
    """ window manager style task: show on window manager task bar """
    DEFAULT = BASIC | ESC_CLOSE | WS_BORDER | WS_TITLE | WS_CLOSE | WMS_TASK
    """ default window flags """
    DEFAULT_NO_CLOSE = BASIC | WS_BORDER | WS_TITLE | WMS_TASK
    """ default window flags (disable non-programmatic close) """


class WindowStyle():
    def render(self, wd: 'Window', w: urwid.Widget):
        return w


class OverlayLineBoxWS(WindowStyle):
    def __init__(self, *, title_attr=None, attr_map=None):
        self._title_attr = title_attr
        self._attr_map = attr_map

    def render(self, wd, w):
        w = super().render(wd, w)
        if not wd.is_overlay:
            return w
        w = urwid.LineBox(
            w,
            title=wd.title,
            title_align='left',
            title_attr=self._title_attr,
        )
        return urwid.AttrMap(
            w, attr_map=self._attr_map,
        ) if self._attr_map else w


class TitleBarWS(WindowStyle):
    def widgets_top_left(self, wd: 'Window'):
        if WindowFlags.WS_TITLE in wd.flags:
            if title := wd.title:
                yield urwid.Text(title)

    def widgets_top_right(self, wd: 'Window'):
        if WindowFlags.WS_CLOSE in wd.flags and wd.is_active_child:
            label = 'Close [Esc]' if WindowFlags.ESC_CLOSE in wd.flags else 'Close'
            w_close = urwid.Button(label)
            urwid.connect_signal(w_close, 'click', lambda w: wd.close())
            yield w_close

    def _pad_col(self, gen):
        lst = list(gen)
        return ('pack', urwid.Padding(
            urwid.Columns(lst, 1),
            left=1, right=1,
        )) if lst else None

    def render(self, wd, w):
        w = super().render(wd, w)
        if WindowFlags.WS_BORDER not in wd.flags:
            return w
        syb = urwid.LineBox.Symbols.LIGHT
        if wd.is_active_child:
            syb = urwid.LineBox.Symbols.DOUBLE
        w_top = urwid.Columns(filter(lambda w: w, [
            (1, urwid.Text(syb.TOP_LEFT if wd.is_overlay else syb.HORIZONTAL)),
            self._pad_col(self.widgets_top_left(wd)),
            urwid.Divider(syb.HORIZONTAL),
            self._pad_col(self.widgets_top_right(wd)),
            (1, urwid.Text(syb.TOP_RIGHT if wd.is_overlay else syb.HORIZONTAL)),
        ]))
        if not wd.is_overlay:
            return urwid.Pile([
                ('pack', w_top),
                w,
            ], focus_item=1)
        return urwid.Pile([
            ('pack', w_top),
            urwid.Columns([
                (1, urwid.SolidFill(syb.VERTICAL)),
                w,
                (1, urwid.SolidFill(syb.VERTICAL)),
            ], box_columns=[0, 2]),
            ('pack', urwid.Columns([
                (1, urwid.Text(syb.BOTTOM_LEFT)),
                urwid.Divider(syb.HORIZONTAL),
                (1, urwid.Text(syb.BOTTOM_RIGHT)),
            ])),
        ], focus_item=1)


class Window():
    _id = 0

    def __init__(
        self, w: urwid.Widget | typing.Callable[['Window'], urwid.Widget], *,
        title: str | None = None,
        flags: WindowFlags = WindowFlags.DEFAULT,
        style: WindowStyle | bool = True,
        overlay: dict | bool = False,
    ):
        self._id = __class__._id
        __class__._id += 1
        self._manager: WindowManager | None = None
        self._parent: Window | None = None
        self._child: Window | None = None
        self._next: Window | None = None
        self._w = w if isinstance(w, urwid.Widget) else w(self)
        self._title = title
        self._flags = flags
        self._style = style
        self._overlay = overlay

    @property
    def parent(self):
        return self._parent

    @property
    def first_child(self):
        return self._child

    @property
    def next_sibling(self):
        return self._next

    @property
    def children(self):
        if self._child:
            wd = self._child
            yield wd
            while wd := wd._next:
                yield wd

    @property
    def siblings(self):
        if self._parent:
            for wd in self._parent.children:
                if wd != self:
                    yield wd

    @property
    def title(self):
        return 'WIN-%d' % self._id if self._title is None else self._title

    @property
    def flags(self):
        return self._flags

    def modify(
        self, *,
        title: str | None = -1,
        flags: WindowFlags = -1,
        style: WindowStyle | bool = -1,
        overlay: dict | bool = -1,
    ):
        if title != -1:
            self._title = title
        if flags != -1:
            self._flags = flags
        if style != -1:
            self._style = style
        if overlay != -1:
            self._overlay = overlay
        if self._manager:
            self._manager._update()

    @property
    def is_overlay(self):
        return self._overlay is not False

    @property
    def is_open(self):
        # test for _manager instead of _parent
        # because root window has not parent and is always 'open'
        return bool(self._manager)

    @property
    def is_active_child(self):
        if self._manager and not self._child:
            wd = self._manager._active
            if wd == self:
                return True
            while wd := wd._child:
                if wd == self:
                    return True
        return False

    @property
    def is_active_parent(self):
        if not self._manager:
            return False
        if self._manager._active == self:
            return True
        return any(map(lambda wd: wd.is_active_child, self.children))

    def set_active(self):
        if self._manager:
            ev = WindowEvent(self, True)
            self.on_active(ev)
            if not ev.canceled:
                self._manager._active = self
                self._manager._update()

    def open_window(
        self, wd: 'Window', *,
        active=True,
    ):
        if not self.is_open:
            raise RuntimeError("Cannot open window on a closed parent")

        if wd.is_open:
            raise RuntimeError("Window already open")
        assert (wd._manager is None)
        assert (wd._parent is None)
        assert (wd._child is None)
        assert (wd._next is None)

        # add child to top
        wd._next = self._child
        self._child = wd

        wd._parent = self
        wd._manager = self._manager
        wd._manager._update()

        # call on_open handler
        wd.on_open(WindowEvent(wd))

        if active:
            wd.set_active()

    def make_window(
        self, w: urwid.Widget | typing.Callable[['Window'], urwid.Widget], *,
        title: str | None = None,
        flags: WindowFlags = WindowFlags.DEFAULT,
        style: WindowStyle | bool = True,
        overlay: dict | bool = False,
        active=True,
    ):
        wd = Window(w, title=title, flags=flags, style=style, overlay=overlay)
        self.open_window(wd, active=active)
        return wd

    def _overlay_kwargs(self, default: dict):
        if isinstance(self._overlay, dict):
            return {**default, **self._overlay}
        return default if self._overlay else None

    def _render(self, style: WindowStyle | None):
        if self._style == True:
            return style.render(self, self._w) if style else self._w
        return self._style.render(self, self._w) if self._style else self._w

    def _destroy(self):
        assert (self._parent)
        assert (self._manager)

        # destroy children
        while self._child:
            self._child._destroy()

        # update active window
        if self._manager._active == self:
            # set root as active in case event is canceled
            self._manager._active = self._manager._root
            (self._next or self._parent).set_active()

        # remove from parent child list
        pc = self._parent._child
        assert (pc)
        if pc == self:
            self._parent._child = self._next
        else:
            assert (pc._next)
            while pc._next != self:
                pc = pc._next
                assert (pc._next)
            assert (pc._next == self)
            pc._next = self._next
        self._next = None
        self._parent = None

        try:
            self._manager._update()
        finally:
            self._manager = None

        # call on_destroy handler
        self.on_destroy(WindowEvent(self))

    def close(self):
        if not self.is_open:
            return False
        if not self._parent:
            # cannot close root window
            return False

        # call on_close handler
        ev = WindowEvent(self, True)
        self.on_close(ev)
        if ev.canceled:
            return False

        # not cancelled, destroy
        self._destroy()
        return True

    def on_open(self, ev: WindowEvent):
        if self._parent:
            self._parent.on_open(ev)

    def on_active(self, ev: WindowEvent):
        if self._parent:
            self._parent.on_active(ev)

    def on_close(self, ev: WindowEvent):
        if self._parent:
            self._parent.on_close(ev)

    def on_destroy(self, ev: WindowEvent):
        if self._parent:
            self._parent.on_destroy(ev)


class WindowManagerStyle():
    def render(self, wm: 'WindowManager', w: urwid.Widget):
        return w


class TaskBarWMS(WindowManagerStyle):
    def __init__(self, label_len=15):
        self._label_len = label_len

    def render(self, wm, w):
        def btn(wd: Window):
            l = wd.title
            if self._label_len > 0 and len(l) > self._label_len:
                l = l[:self._label_len - 1] + '\N{HORIZONTAL ELLIPSIS}'
            w_close = urwid.Button('[%s]' % l if wd.is_active_parent else l)
            urwid.connect_signal(w_close, 'click', lambda w: wd.set_active())
            return 'pack', w_close
        w = super().render(wm, w)
        wd_list = list(filter(
            lambda wd: WindowFlags.WMS_TASK in wd.flags,
            wm.root.children,
        ))
        if len(wd_list) <= 1:
            return w
        return urwid.Pile([
            w, ('pack', urwid.Columns(map(btn, reversed(wd_list)), 1)),
        ])


class WindowManager():
    class _WindowCloser(urwid.WidgetPlaceholder):
        def __init__(self, wd: 'Window', w: urwid.Widget):
            super().__init__(w)
            self._wd = wd

        def keypress(self, size, key):
            key = super().keypress(size, key)
            if key == 'esc':
                self._wd.close()
                return None
            return key

    _default_style = TaskBarWMS()
    _default_window_style = TitleBarWS()
    _default_window_overlay = {
        'align': 'center',
        'width': ('relative', 55),
        'valign': 'middle',
        'height': 'pack',
    }

    def __init__(
        self, *,
        style: WindowManagerStyle | None = _default_style,
        window_style: WindowStyle | None = _default_window_style,
        window_overlay: dict = _default_window_overlay,
    ):
        self._style = style
        self._window_style = window_style
        self._window_overlay = window_overlay
        self._root = Window(urwid.Overlay(
            urwid.Text('!'),
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            'center', 'pack', 'middle', 'pack',
        ), flags=WindowFlags.BASIC, style=False)
        # root window has no parent but has manager
        self._root._manager = self
        self._active = self._root
        self._widget = urwid.WidgetPlaceholder(self._render())

    @property
    def root(self):
        return self._root

    @property
    def active(self):
        return self._active

    @property
    def widget(self):
        return self._widget

    def _render(self):
        def render_wd(wd: Window, top=False):
            if top and WindowFlags.ESC_CLOSE in wd.flags:
                return __class__._WindowCloser(wd, wd._render(self._window_style))
            return wd._render(self._window_style)

        def render_down(wd: Window, top=False):
            if ol_kwargs := wd._overlay_kwargs(self._window_overlay):
                # overlay window
                assert (wd._parent)
                return urwid.Overlay(
                    # top widget (self)
                    render_wd(wd, top),
                    # bottom widget (recursive render)
                    render_up(wd._next) if wd._next
                    else render_down(wd._parent),
                    # overlay kwargs
                    **ol_kwargs,
                )
            # full window (stop rendering)
            return render_wd(wd, top)

        def render_up(wd: Window):
            # find top window
            while wd._child:
                wd = wd._child
            return render_down(wd, True)

        w = render_up(self._active)
        return self._style.render(self, w) if self._style else w

    def _update(self):
        self._widget.original_widget = self._render()
