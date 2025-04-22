import logging
import os
import typing

import urwid

_ss_default_attrs = {
    'button': ['label'],
    'boxbutton': ['label', 'title'],
}


def ss_attr_map_widget(w: urwid.Widget, name: str, *, attrs=None, flags=''):
    if attrs is None:
        attrs = _ss_default_attrs[name] if name in _ss_default_attrs else []
    attr_map = {f'.{a}': f'.{name}.{a}' for a in attrs}
    attr_map[None] = f'.{name}.wrap'
    focus_map = {f'.{a}': f'.{name}/focus.{a}' for a in attrs}
    focus_map[None] = f'.{name}/focus.wrap'
    return urwid.AttrMap(w, attr_map, focus_map)


def ss_attr_map_style(w: urwid.Widget, name: str, style: str, *, attrs=None, flags=''):
    if attrs is None:
        attrs = _ss_default_attrs[name] if name in _ss_default_attrs else []
    attrs += ['wrap']
    a_map = {f'.{name}.{a}': f'{style}.{name}.{a}' for a in attrs}
    f_map = {f'.{name}/focus.{a}': f'{style}.{name}/focus.{a}' for a in attrs}
    return urwid.AttrMap(w, {**a_map, **f_map})


def ss_16color_names(white_is_gray: bool | None = None):
    if white_is_gray is None:
        white_is_gray = os.environ.get('TERM') == 'xterm-256color'
    c_names = ['black', 'red', 'green', 'yellow',
               'blue', 'magenta', 'cyan', 'white']
    c_map = {
        # rename yellow
        'dark yellow': 'brown',
        'light yellow': 'yellow',
        # handle black/gray/white
        'dark black': 'black',
        'light black': 'white' if white_is_gray else 'dark gray',
        'dark white': 'dark gray' if white_is_gray else 'light gray',
        'light white': 'light gray' if white_is_gray else 'white',
    }
    c_dark = (f'dark {c}' for c in c_names)
    c_dark = list(map(lambda c: c_map[c] if c in c_map else c, c_dark))
    c_light = (f'light {c}' for c in c_names)
    c_light = list(map(lambda c: c_map[c] if c in c_map else c, c_light))
    return zip(c_names, c_dark, c_light)


def ss_make_button(label, **kwargs):
    return ss_attr_map_widget(urwid.Button(('.label', label), **kwargs), 'button')


def ss_make_boxbutton(label, **kwargs):
    return ss_attr_map_widget(BoxButton(('.label', label), title_attr='.title', **kwargs), 'boxbutton')


def ss_make_default_palette(prefix='ss', white_is_gray: bool | None = None):
    for color, dark, light in ss_16color_names(white_is_gray):
        # style name
        name = f'{prefix}.{color}'
        # high contrast foreground
        fg_hc = 'white' if color in [
            'magenta', 'cyan', 'white',
        ] else 'light gray'
        # button
        yield f'{name}.button.label', fg_hc, dark
        yield f'{name}.button/focus.label', 'white', dark
        yield f'{name}.button.wrap', 'dark gray', dark
        yield f'{name}.button/focus.wrap', light, dark
        # boxbutton
        yield f'{name}.boxbutton.label', fg_hc, dark
        yield f'{name}.boxbutton/focus.label', 'white', dark
        yield f'{name}.boxbutton.title', fg_hc, dark
        yield f'{name}.boxbutton/focus.title', 'white', dark
        yield f'{name}.boxbutton.wrap', dark, dark
        yield f'{name}.boxbutton/focus.wrap', light, dark
        # generic
        yield f'{name}.fg', dark, ''
        yield f'{name}.bg', fg_hc, dark
        yield f'{name}/bright.fg', light, ''
        yield f'{name}/bright.bg', fg_hc, light


def make_button(label, *, on_click=None, attr_map=None, focus_map=None):
    w_btn = ss_make_button(label)
    if on_click:
        urwid.connect_signal(w_btn.base_widget, 'click', on_click)
    if attr_map or focus_map:
        return urwid.AttrMap(w_btn, attr_map=attr_map, focus_map=focus_map)
    return w_btn


def make_buttons(spec, on_click=None):
    res = []
    for i, item in enumerate(spec):
        label, kwargs = item if isinstance(item, tuple) else (item, {})
        w_btn = make_button(label, **kwargs)
        if on_click:
            urwid.connect_signal(
                w_btn.base_widget, 'click', on_click, user_args=[i],
            )
        res.append(w_btn)
    return res


def make_list_buttons(spec, on_click=None, wrap_around=False):
    return urwid.ListBox(urwid.SimpleFocusListWalker(
        make_buttons(spec, on_click),
        wrap_around,
    ))


class BoxButton(urwid.WidgetWrap):
    # mixin signals from urwid.Button
    signals = urwid.Button.signals
    keypress = urwid.Button.keypress
    mouse_event = urwid.Button.mouse_event

    def __init__(
        self, label, *, space=(2, 1), border=(2, 1),
        align='left', wrap='space', layout=None,  # for urwid.SelectableIcon
        title='', title_align='', title_attr=None,  # for urwid.LineBox
        cursor_position=0,  # cursor_position=-1 -> hide
    ):
        s_x, s_y = space if isinstance(space, tuple) else (space, space)
        b_x, b_y = border if isinstance(border, tuple) else (border, border)
        b_x = b_x if s_x else False
        b_y = b_y if s_y else False
        s_x = s_x - 1 if b_x else s_x
        s_y = s_y - 1 if b_y else s_y

        self._label = urwid.SelectableIcon(
            label, align=align, wrap=wrap, layout=layout,
            cursor_position=1e9 if cursor_position < 0 else cursor_position,
        )
        super().__init__(self._label)

        if s_x:
            self._w = urwid.Padding(self._w, left=s_x, right=s_x)
        if s_y:
            self._w = urwid.Filler(self._w, top=s_y, bottom=s_y)
        if b_x or b_y:
            self._w = urwid.LineBox(
                self._w,
                title=title, title_align=title_align or align, title_attr=title_attr,
                tlcorner='\N{FULL BLOCK}' if b_x > 1 or b_y > 1 else '\N{QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER LEFT}',
                tline=[None, '\N{UPPER HALF BLOCK}', '\N{FULL BLOCK}'][b_y],
                lline=[None, '\N{LEFT HALF BLOCK}', '\N{FULL BLOCK}'][b_x],
                trcorner='\N{FULL BLOCK}' if b_x > 1 or b_y > 1 else '\N{QUADRANT UPPER LEFT AND UPPER RIGHT AND LOWER RIGHT}',
                blcorner='\N{FULL BLOCK}' if b_x > 1 or b_y > 1 else '\N{QUADRANT UPPER LEFT AND LOWER LEFT AND LOWER RIGHT}',
                rline=[None, '\N{RIGHT HALF BLOCK}', '\N{FULL BLOCK}'][b_x],
                bline=[None, '\N{LOWER HALF BLOCK}', '\N{FULL BLOCK}'][b_y],
                brcorner='\N{FULL BLOCK}' if b_x > 1 or b_y > 1 else '\N{QUADRANT UPPER RIGHT AND LOWER LEFT AND LOWER RIGHT}',
            )


class PileLoggingHandler(logging.Handler):
    def __init__(
        self, level: int | str = 0, *,
        pile: urwid.Pile | None = None, max_content=10,
        cb_draw_screen=None, cb_create_widget=None,
    ):
        super().__init__(level)
        self._pile = urwid.Pile([]) if pile is None else pile
        self._max_content = max_content
        self._cb_draw_screen = cb_draw_screen
        self._cb_create_widget = cb_create_widget or (lambda s: urwid.Text(s))

    @property
    def pile(self):
        return self._pile

    def emit(self, record):
        contents = self._pile.contents
        w = self._cb_create_widget(self.format(record))
        contents.append(w if isinstance(w, tuple) else (w, ('pack', None)))
        if self._max_content > 0:
            self._pile.contents = contents[-self._max_content:]
        if self._cb_draw_screen:
            self._cb_draw_screen()


class WindowStack(urwid.WidgetWrap):
    _default_overlay_kwargs = {
        'align': 'center',
        'width': ('relative', 55),
        'valign': 'middle',
        'height': 'pack',
    }

    class WindowHandle:
        def __init__(self, close):
            self._close = close

        def close(self):
            self._close()

    def __init__(self, base: urwid.Widget):
        super().__init__(base)
        self._stack = [(base, 0, None)]

    def _window_apply(self):
        top_w = None
        top_ol = None
        for w, z, ol in reversed(self._stack):
            if ol is None:
                if top_w:
                    self._w = urwid.Overlay(
                        top_w, w, **top_ol
                    )
                else:
                    self._w = w
                break
            elif not top_w:
                top_w = w
                top_ol = {**self._default_overlay_kwargs, **ol}

    def window_open(
        self, w: urwid.Widget | typing.Callable[[WindowHandle], urwid.Widget], *,
        z=500, overlay=False,
    ):
        z = 0 if z < 0 else z
        bean = None

        def close():
            if bean in self._stack:
                self._stack.remove(bean)
                self._window_apply()

        wh = WindowStack.WindowHandle(close)
        w = w if isinstance(w, urwid.Widget) else w(wh)
        ol = overlay if isinstance(overlay, dict) else (
            {} if overlay else None)

        bean = (w, z, ol)
        self._stack.append(bean)
        self._stack.sort(key=lambda x: x[1])
        self._window_apply()
        return wh

    def window_close_top(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._window_apply()

    def window_close_all(self):
        if len(self._stack) > 1:
            self._stack = [self._stack[0]]
            self._window_apply()


class ConfigurableMenu(urwid.WidgetWrap):
    back_label = 'BACK'
    back_keys = ['esc', 'backspace']
    attr_focused = 'focused'
    attr_disabled = 'disabled'

    def __init__(self, root_key='menu', root_title='', ss_style=None):
        super().__init__(urwid.Pile([]))
        self.attr_focused = root_key + '.' + self.attr_focused
        self.attr_disabled = root_key + '.' + self.attr_disabled
        self._w = ss_attr_map_style(self._w, 'button', ss_style or root_key)
        self._menus = {}
        self._stack = [root_key]
        self.menu_setup(root_key, title=root_title)

    def _menu_apply(self):
        crumbs = '/'.join([self._menus[i][1] for i in self._stack])
        crumbs = crumbs or '/'
        w_back_btn = make_button(
            self.back_label,
            on_click=lambda w_btn: self._menu_pop(),
            attr_map=None if len(self._stack) > 1 else self.attr_disabled,
            focus_map=self.attr_focused,
        )
        w_menu = self._menus[self._stack[-1]][0]
        self._w.base_widget.contents = [
            (urwid.Columns([
                ('pack', w_back_btn),
                ('weight', 1, urwid.Text(crumbs)),
            ], 1), ('pack', None)),
            (w_menu, ('weight', 1)),
        ]

    def _menu_pop(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._menu_apply()

    def _menu_push(self, key):
        if key != self._stack[0] and key in self._menus:
            self._stack.append(key)
            self._menu_apply()

    def keypress(self, size, key):
        if len(self._stack) > 1 and key in self.back_keys:
            self._menu_pop()
            return None
        return super().keypress(size, key)

    def menu_setup(
        self, key: str, *,
        title: str | None = None,
        buttons: list[tuple[str, str | typing.Callable[[], None]]] = [],
        append=True, replace=True,
    ):
        if not replace and key in self._menus:
            _, m_title, m_buttons = self._menus[key]
            title = title or m_title
            buttons = m_buttons + buttons if append else buttons + m_buttons

        def on_click(n, w_btn):
            click = buttons[n][1]
            if isinstance(click, str):
                self._menu_push(click)
            elif callable(click):
                click()
        w_list = make_list_buttons(
            [(label, {
                'focus_map': self.attr_focused,
            }) for label, click in buttons],
            on_click,
        )

        self._menus[key] = (w_list, key if title is None else title, buttons)
        if key in self._stack:
            self._menu_apply()

    def menu_setup_root(
        self, *,
        title: str | None = None,
        buttons: list[tuple[str, str | typing.Callable[[], None]]] = [],
        append=False, replace=False,
    ):
        self.menu_setup(
            self._stack[0],
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def menu_remove(self, key: str):
        if key != self._stack[0] and key in self._menus:
            del self._menus[key]
            if key in self._stack:
                self._stack = [i for i in self._stack if i != key]
                self._menu_apply()
