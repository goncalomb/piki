import logging
import os

import urwid

from .. import util
from . import plugin

logger = logging.getLogger(__name__)


class Controller():
    piki_venv_dir = util.find_venv_dir()
    piki_dir = os.path.dirname(piki_venv_dir) if piki_venv_dir else os.getcwd()
    piki_plugins_dir = os.path.join(piki_dir, 'plugins')

    def __init__(self):
        self._plugins = []
        logger.info("Starting PiKi Core")
        logger.info("piki_venv_dir = %s" % self.piki_venv_dir)
        logger.info("piki_dir = %s" % self.piki_dir)
        logger.info("piki_plugins_dir = %s" % self.piki_plugins_dir)

    def _cb_plugin_init(self, plugin):
        plugin.ctl = PluginControl(self)

    def load(self):
        if os.path.isdir(self.piki_plugins_dir):
            self._plugins = plugin._load_plugins(
                self.piki_plugins_dir,
                Plugin,
                self._cb_plugin_init,
            )
        for p in self._plugins:
            p.on_load()
        logger.info("Loaded %d plugin(s): %s" % (
            len(self._plugins),
            [p.name for p in self._plugins],
        ))

    def main_loop(self, widget):
        loop = urwid.MainLoop(widget)
        for p in self._plugins:
            p.on_main()
        loop.run()


class PluginControl():
    piki_dir: str

    def __init__(self, ctl):
        self.piki_dir = ctl.piki_dir


class Plugin(plugin.Plugin):
    ctl: PluginControl

    def on_load(self): pass
    def on_main(self): pass
