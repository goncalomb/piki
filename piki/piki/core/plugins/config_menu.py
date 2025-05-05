import os

import urwid
from piki.core import CoreController
from piki.plugin import Plugin
from piki.utils.linux.rc import RCDevice, rc_find_devices
from piki.utils.pkg.urwid_window import Window
from piki.utils.rc_keytable import RCKeymap, RCKeymapConfigurator


class RCKeymapConfiguratorWindow(Window):
    def __init__(self, plugin: Plugin, file: str, dev: RCDevice):
        self._plugin = plugin
        self._file = file
        self._ask_close = True

        self._keymap = RCKeymap()
        if os.path.isfile(self._file):
            self._keymap.load(self._file)
            # XXX: not handling errors

        self._cfg = RCKeymapConfigurator(
            self._keymap, dev,
            cb_draw_screen=plugin.ctl.ui_draw_screen,
        )

        w_btn_save = urwid.Button('Save and Close')
        urwid.connect_signal(w_btn_save, 'click', lambda w: self._save())
        w_btn_clear = urwid.Button('Clear All')
        urwid.connect_signal(w_btn_clear, 'click', lambda w: self._cfg.clear())

        super().__init__(
            urwid.Padding(
                urwid.Pile([
                    ('pack', urwid.Filler(
                        urwid.Padding(
                            urwid.Columns([w_btn_save, w_btn_clear], 1),
                            width=('relative', 50),
                        ),
                        top=1, bottom=1,
                    )),
                    self._cfg.widget,
                ]),
                left=1, right=1,
            ),
            title='RC/IR Configurator',
            overlay={
                'width': ('relative', 85),
                'height': ('relative', 85),
            },
        )

    def _close_force(self):
        self._ask_close = False
        self.close()

    def _save(self):
        self._cfg.close()
        if self._cfg.changed:
            # XXX: don't trim, ir-keytable fails with 'Segmentation fault'
            #      with empty rc map files 'ir-keytable -a /etc/rc_maps.cfg'
            self._keymap.save(self._file, trim=False)
            self._msg_saved()
        else:
            self._close_force()

    def _msg_saved(self):
        self._plugin.ctl.ui_message_box(
            'Saved, a reboot is required for the changes to take effect. Reboot now?',
            buttons=[
                ('Reboot', 'ss.cyan', lambda *_: self._plugin.ctl.sys_reboot()),
                ('No', 'ss.white'),
            ],
            callback=lambda *_: self._close_force(),
            parent=self,
            title='RC/IR Configurator',
        )

    def _msg_ask(self):
        self._plugin.ctl.ui_message_box(
            'Not saved, close anyway?',
            buttons=[
                ('No', 'ss.white'),
                ('Yes', 'ss.yellow', lambda *_: self._close_force()),
            ],
            parent=self,
            title='RC/IR Configurator',
        )

    def on_close(self, ev):
        if ev.wd == self:
            self._cfg.close()
            if self._ask_close and self._cfg.changed:
                self._msg_ask()
                ev.cancel()
        super().on_close(ev)


class ConfigMenuPlugin(Plugin):
    def _rpi_config_rc(self):
        def is_rpi_rc(dev: RCDevice):
            return dev.lirc0 is not None and dev.uevent_var('DRV_NAME') == 'gpio_ir_recv' and dev.uevent_var('NAME') == 'rc-empty'
        file = os.path.join(CoreController.piki_dir, 'rc-empty.toml')
        dev = next(filter(is_rpi_rc, rc_find_devices()), None)
        self.ctl.ui_window_open(RCKeymapConfiguratorWindow(self, file, dev))

    def on_ui_create(self):
        self.ctl.ui_menu_setup_root(buttons=[
            ('Configuration', 'piki.menu.config'),
        ])
        self.ctl.ui_menu_setup('piki.menu.config', title='Configuration', buttons=[
            ('RPi: Configure RC/IR', self._rpi_config_rc),
        ])
