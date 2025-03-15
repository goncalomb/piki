import importlib
import logging
import os
import types

logger = logging.getLogger(__name__)


def _exec_module(location):
    name = os.path.basename(location)
    if os.path.isdir(location):
        location = os.path.join(location, '__init__.py')
    spec = importlib.util.spec_from_file_location(
        name.replace('.', '_'), location)
    if spec:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def _load_plugin(path, plugin_base_class, cb_plugin_init):
    if not issubclass(plugin_base_class, Plugin):
        raise Exception("Plugin base must be subclass of %s" % Plugin)

    plugin_class = None

    @classmethod
    def plugin_init_subclass(cls):
        nonlocal plugin_class
        if plugin_class:
            raise Exception("Cannot declare multiple plugin classes")
        plugin_class = cls

    # replace __init_subclass__ to capture class
    init_subclass_org = plugin_base_class.__init_subclass__
    plugin_base_class.__init_subclass__ = plugin_init_subclass
    try:
        # load plugin
        plugin_module = _exec_module(path)
    finally:
        plugin_base_class.__init_subclass__ = init_subclass_org

    # default to base, if plugin class was not declared
    if not plugin_class:
        plugin_class = plugin_base_class

    def plugin_init(self):
        self.logger = logging.getLogger(plugin_module.__name__)
        self.module = plugin_module
        self.path = path
        self.name = plugin_module.__name__
        cb_plugin_init(self)

    # replace __init__ for initialization
    init_org = Plugin.__init__
    Plugin.__init__ = plugin_init
    try:
        # initialize plugin
        plugin = plugin_class()
    finally:
        Plugin.__init__ = init_org

    return plugin


def _load_plugins(path, plugin_base_class, cb_plugin_init):
    if not issubclass(plugin_base_class, Plugin):
        raise Exception("Plugin base must be subclass of %s" % Plugin)

    res = []
    for f in os.scandir(path):
        if f.name[0] == '_':
            continue
        logger.info("Loading plugin from '%s'" % f.path)
        try:
            plugin = _load_plugin(
                f.path,
                plugin_base_class,
                cb_plugin_init,
            )
            logger.info("Plugin '%s' loaded" % plugin.name)
            res.append(plugin)
        except Exception as e:
            logger.exception("Exception while loading plugin", exc_info=e)
    return res


class Plugin():
    logger: logging.Logger
    module: types.ModuleType
    path: str
    name: str

    @classmethod
    def __init_subclass__(cls):
        @classmethod
        def init_subclass(cls):
            raise Exception("Cannot declare plugin here")
        cls.__init_subclass__ = init_subclass

    def __init__(self):
        raise Exception("Cannot initialize plugin here")
