import urwid
from piki.utils.pkg.urwid import (cm_y_as_x, ss_attr_map_style,
                                  ss_make_boxbutton)

from ..utils.pkg.urwid_window import Window


def message_box(
    body, *,
    buttons='OK',
    callback=None,
    autoclose=True,
):
    default_spec = ('OK', 'ss.white', None, autoclose)
    default_buttons = {
        'OK': ('OK', 'ss.cyan'),
        'Cancel': ('Cancel', 'ss.white'),
        'Yes': ('Yes', 'ss.cyan'),
        'No': ('No', 'ss.magenta'),
    }

    if isinstance(buttons, str):
        buttons = map(
            lambda s: default_buttons[s] if s in default_buttons else s,
            buttons.split(','),
        )

    def win(wd: Window):
        def make_button(i, spec):
            label, style, cback, aclose = map(
                lambda d, v: d if v is None else v,
                default_spec,
                spec + default_spec[len(spec):],
            )
            btn = ss_attr_map_style(
                ss_make_boxbutton(label),
                'boxbutton', style,
            )
            if aclose:
                urwid.connect_signal(
                    btn.base_widget, 'click', lambda w: wd.close())
            if cback:
                urwid.connect_signal(
                    btn.base_widget, 'click', lambda w: cback(wd, i))
            if callback:
                urwid.connect_signal(
                    btn.base_widget, 'click', lambda w: callback(wd, i))
            return btn

        def make_buttons():
            for i in range(len(buttons), 3):
                yield urwid.Text('')
            for i, spec in enumerate(buttons):
                spec = (spec,) if isinstance(spec, str) else spec
                yield make_button(i, spec)

        contents = [
            body if isinstance(body, urwid.Widget) else urwid.Text(body)
        ]
        nonlocal buttons
        if buttons:
            buttons = list(buttons)
            contents.append(urwid.Filler(
                cm_y_as_x(urwid.Columns(make_buttons(), 1)),
                top=1,
            ))
        return urwid.Filler(
            urwid.Padding(
                urwid.Pile(contents),
                left=2, right=2,
            ), top=1, bottom=1,
        )
    return win
