import urwid
from piki import piki_source_url, piki_version
from piki.plugin import Plugin
from piki.utils.pkg.urwid_window import TitleBarWS, WindowFlags


class MenuWindowStyle(TitleBarWS):
    def render(self, wd, w):
        w = urwid.Padding(
            w, left=2, right=2,
        )
        return super().render(wd, w)


class DefaultStylePlugin(Plugin):
    _title = ('ss.cyan.fg', 'PiKi')
    _header_message = ['A Raspberry ', ('ss.cyan.fg', 'Pi Ki'), 'osk']
    _footer_message = "piki v%s \N{BULLET} %s" % (
        piki_version, piki_source_url,
    )

    def on_ui_create(self):
        ui = self.ctl.ui_internals
        # restyle menu window
        ui.wd_menu.modify(
            flags=ui.wd_menu.flags & ~WindowFlags.WS_BORDER,
            style=MenuWindowStyle(),
            overlay={
                'width': ('relative', 75),
                'height': ('relative', 100),
            },
        )
        # wrap body
        ui.w_frame.body = urwid.Padding(
            ui.w_frame.body, 'center', ('relative', 45),
        )
        # create header and footer pile
        ui.w_frame.header = urwid.Filler(urwid.Pile([
            urwid.Padding(urwid.BigText(
                self._title, urwid.HalfBlock5x4Font(),
            ), 'center', 'clip'),
            urwid.Text(self._header_message, 'center'),
        ]), top=1, bottom=1)
        ui.w_frame.footer = urwid.Filler(urwid.Pile([
            urwid.Text(self._footer_message, 'center'),
        ]), top=1, bottom=1)
