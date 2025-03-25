from collections.abc import Callable
import typing

import urwid


def make_button(label, *, on_click=None, attr_map=None, focus_map=None):
    w_btn = urwid.Button(label)
    if on_click:
        urwid.connect_signal(w_btn, 'click', on_click)
    if attr_map or focus_map:
        if focus_map:
            # hack to hide cursor
            w_btn._label._cursor_position = len(label) + 1
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


class ConfigurableMenu(urwid.WidgetPlaceholder):
    back_label = 'BACK'
    back_keys = ['esc', 'backspace']
    attr_focused = 'focused'
    attr_disabled = 'disabled'

    def __init__(self, root_key='menu', root_title=''):
        super().__init__(urwid.Pile([]))
        self.attr_focused = root_key + '.' + self.attr_focused
        self.attr_disabled = root_key + '.' + self.attr_disabled
        self._menus = {}
        self._stack = [root_key]
        self.setup_menu(root_key, title=root_title)

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
        self.original_widget.contents = [
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

    def setup_menu(
        self, key: str, *,
        title: str | None = None,
        buttons: list[tuple[str, str | Callable[[], None]]] = [],
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

    def setup_root_menu(
        self, *,
        title: str | None = None,
        buttons: list[tuple[str, str | Callable[[], None]]] = [],
        append=False, replace=False,
    ):
        self.setup_menu(
            self._stack[0],
            title=title, buttons=buttons, append=append, replace=replace,
        )

    def remove_menu(self, key: str):
        if key != self._stack[0] and key in self._menus:
            del self._menus[key]
            if key in self._stack:
                self._stack = [i for i in self._stack if i != key]
                self._menu_apply()
