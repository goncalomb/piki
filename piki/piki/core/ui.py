import urwid
from piki.utils.pkg.urwid import (cm_y_as_x, ss_attr_map_style,
                                  ss_make_boxbutton)


def message_box(
    body, *,
    buttons='OK', title='', title_attr=None,
    callback=None, autoclose=True, attr_map=None,
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

    def win(wh):
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
                    btn.base_widget, 'click', lambda w: wh.close())
            if cback:
                urwid.connect_signal(
                    btn.base_widget, 'click', lambda w: cback(wh, i))
            if callback:
                urwid.connect_signal(
                    btn.base_widget, 'click', lambda w: callback(wh, i))
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
        w = urwid.Pile(contents)
        if title is not None:
            w = urwid.LineBox(
                urwid.Filler(urwid.Padding(
                    w, left=2, right=2), top=1, bottom=1
                ),
                title=title,
                title_align='left',
                title_attr=title_attr
            )
        if attr_map:
            w = urwid.AttrMap(w, attr_map)
        return w
    return win
