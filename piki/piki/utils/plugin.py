import importlib
import logging
import os
import types
import contextlib


@contextlib.contextmanager
def _replace_attr(obj, name: str, value):
    orig = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield orig
    finally:
        setattr(obj, name, orig)


def _exec_module(location):
    name = os.path.basename(location)
    if os.path.isdir(location):
        location = os.path.join(location, '__init__.py')
    elif name[-3:] == '.py':
        name = name[:-3]
    name = name.replace('.', '_')
    spec = importlib.util.spec_from_file_location(name, location)
    if spec:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def load_plugin(path, plugin_base_class, cb_plugin_init):
    if not issubclass(plugin_base_class, Plugin):
        raise Exception("Plugin base must be subclass of %s" % Plugin)

    plugin_class = None

    @classmethod
    def plugin__init_subclass__(cls):
        nonlocal plugin_class
        if plugin_class:
            raise Exception("Cannot declare multiple plugin classes")
        plugin_class = cls

    # replace __init_subclass__ to capture class
    with _replace_attr(plugin_base_class, '__init_subclass__', plugin__init_subclass__):
        # load plugin
        plugin_module = _exec_module(path)

    # default to base, if plugin class was not declared
    if not plugin_class:
        raise Exception("Plugin did not declare a plugin class")

    def plugin__init__(self):
        self.logger = logging.getLogger(plugin_module.__name__)
        self.module = plugin_module
        self.path = path
        self.name = plugin_module.__name__
        cb_plugin_init(self)

    # replace __init__ for initialization
    with _replace_attr(Plugin, '__init__', plugin__init__):
        # initialize plugin
        plugin = plugin_class()

    return plugin


def load_plugins(path, plugin_base_class, cb_plugin_init):
    if not issubclass(plugin_base_class, Plugin):
        raise Exception("Plugin base must be subclass of %s" % Plugin)

    res = []
    for f in os.scandir(path):
        if f.name[0] in ('.', '_'):
            continue
        try:
            res.append(load_plugin(f.path, plugin_base_class, cb_plugin_init))
        except:
            raise Exception("Failed to load plugin '%s'" % f.path)
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
