import typing

import urwid


class WindowStyle():
    def render(self, wd: 'Window'):
        return wd._w


class WindowStyleOverlayLineBox(WindowStyle):
    def __init__(self, *, title_attr=None, attr_map=None):
        self._title_attr = title_attr
        self._attr_map = attr_map

    def render(self, wd):
        w = super().render(wd)
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


class Window():
    _id = 0

    def __init__(
        self, w: urwid.Widget | typing.Callable[['Window'], urwid.Widget], *,
        title: str | None = None,
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

    def modify(
        self, *,
        title: str | None = -1,
        style: WindowStyle | bool = -1,
        overlay: dict | bool = -1,
    ):
        if title != -1:
            self._title = title
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

    def set_active(self):
        if self._manager:
            self._manager._active = self
            self._manager._update()

    def open_window(self, child: 'Window'):
        if not self.is_open:
            raise RuntimeError("Cannot open window on a closed parent")

        if child.is_open:
            raise RuntimeError("Window already open")
        assert (child._manager is None)
        assert (child._parent is None)
        assert (child._child is None)
        assert (child._next is None)

        # add child to top
        child._next = self._child
        self._child = child

        child._parent = self
        child._manager = self._manager
        child._manager._update()

        # call open handler
        if child._on_open(child):
            child.set_active()

    def make_window(
        self, w: urwid.Widget | typing.Callable[['Window'], urwid.Widget], *,
        title: str | None = None,
        style: WindowStyle | bool = True,
        overlay: dict | bool = False,
    ):
        child = Window(w, title=title, style=style, overlay=overlay)
        self.open_window(child)
        return child

    def _overlay_kwargs(self, default: dict):
        if isinstance(self._overlay, dict):
            return {**default, **self._overlay}
        return default if self._overlay else None

    def _render(self, style: WindowStyle | None):
        if self._style == True:
            return style.render(self) if style else self._w
        return self._style.render(self) if self._style else self._w

    def _destroy(self):
        assert (self._parent)
        assert (self._manager)

        # destroy children
        while self._child:
            self._child._destroy()

        # call destroy handler
        self._on_destroy(self)

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

        m = self._manager
        self._manager = None
        m._update()

    def close(self):
        if not self.is_open:
            return False
        if not self._parent:
            # cannot close root window
            return False

        # call close handler
        if not self._on_close(self):
            return False

        # not cancelled, destroy
        self._destroy()
        return True

    def _on_open(self, wd: 'Window'):
        return self._parent._on_open(wd) if self._parent else True

    def _on_close(self, wd: 'Window'):
        return self._parent._on_close(wd) if self._parent else True

    def _on_destroy(self, wd: 'Window'):
        return self._parent._on_destroy(wd) if self._parent else True


class WindowManager():
    _default_window_style = WindowStyleOverlayLineBox()
    _default_window_overlay = {
        'align': 'center',
        'width': ('relative', 55),
        'valign': 'middle',
        'height': 'pack',
    }

    def __init__(
        self, *,
        window_style: WindowStyle | None = _default_window_style,
        window_overlay: dict = _default_window_overlay,
    ):
        self._window_style = window_style
        self._window_overlay = window_overlay
        self._root = Window(urwid.Overlay(
            urwid.Text('!'),
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            'center', 'pack', 'middle', 'pack',
        ), style=False)
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
        def render_down(wd: Window):
            if ol_kwargs := wd._overlay_kwargs(self._window_overlay):
                # overlay window
                assert (wd._parent)
                return urwid.Overlay(
                    # top widget (self)
                    wd._render(self._window_style),
                    # bottom widget (recursive render)
                    render_up(wd._next) if wd._next
                    else render_down(wd._parent),
                    # overlay kwargs
                    **ol_kwargs,
                )
            # full window (stop rendering)
            return wd._render(self._window_style)

        def render_up(wd: Window):
            # find top window
            while wd._child:
                wd = wd._child
            return render_down(wd)

        return render_up(self._active)

    def _update(self):
        if self._active and self._active._manager != self:
            self._active = self._root
        self._widget.original_widget = self._render()
