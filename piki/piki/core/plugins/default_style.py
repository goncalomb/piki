import urwid
from piki.plugin import Plugin

from piki import piki_source_url, piki_version


class DefaultStylePlugin(Plugin):
    _header_message = "PiKi: Raspberry [Pi Ki]osk"
    _footer_message = "piki v%s \N{BULLET} %s" % (
        piki_version, piki_source_url,
    )

    def on_ui_create(self):
        ui = self.ctl.ui_internals
        # wrap root in overlay and padding
        ui.w_root.original_widget = urwid.Overlay(
            urwid.Padding(
                ui.w_root.original_widget,
                left=2, right=2,
            ),
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            'center', ('relative', 80),
            'middle', ('relative', 80),
        )
        # wrap body
        ui.w_frame.body = urwid.Padding(
            ui.w_frame.body, 'center', ('relative', 40)
        )
        # create header and footer pile
        ui.w_frame.header = urwid.Filler(urwid.Pile([
            urwid.Text(self._header_message, 'center'),
        ]), top=1, bottom=1)
        ui.w_frame.footer = urwid.Filler(urwid.Pile([
            urwid.Text(self._footer_message, 'center'),
        ]), top=1, bottom=1)
