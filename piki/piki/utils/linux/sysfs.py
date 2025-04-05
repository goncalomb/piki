import dataclasses
import os
import typing
import weakref


@dataclasses.dataclass(eq=False)
class ClassDevice():
    _class_name = ''
    _device_name = ''
    path: str
    uevent: dict | None = dataclasses.field(init=False)

    @classmethod
    def _set_child_properties(cls, ccls):
        ccls_devs = weakref.WeakKeyDictionary()

        def ensure_devs(self):
            if self not in ccls_devs:
                devs = list(sysfs_find_class_devices(ccls, self.path))
                dev0 = devs[0] if devs else None
                ccls_devs[self] = devs, dev0

        def get_devs(self):
            ensure_devs(self)
            return ccls_devs[self][0]

        def get_dev0(self):
            ensure_devs(self)
            return ccls_devs[self][1]

        # a void setter is required because without it the dataclass __init__
        # will try to set the instance attribute and raise an exception
        def void_setter(*k): pass

        setattr(cls, ccls._device_name, property(get_devs, void_setter))
        setattr(cls, ccls._device_name + '0', property(get_dev0, void_setter))

    def __init_subclass__(cls, children=[]):
        for ccls in children:
            cls._set_child_properties(ccls)

    def __post_init__(self):
        try:
            self.uevent = dict(sysfs_read_uevent(self.path))
        except FileNotFoundError:
            raise Exception("Invalid device '%s', no uevent file" % self.path)

    def uevent_var(self, name: str, default=None):
        return self.uevent[name] if name in self.uevent else default

    @property
    def dev_number(self):
        major = self.uevent_var('MAJOR')
        minor = self.uevent_var('MINOR')
        return major + ':' + minor if major and minor else None

    @property
    def dev_path(self):
        devname = self.uevent_var('DEVNAME')
        return '/dev/' + devname if devname else None


_ClassDevice_TV = typing.TypeVar('ClassDevice', bound=ClassDevice)


def sysfs_read_uevent(path):
    with open(path + '/uevent') as fp:
        while line := fp.readline():
            line = line.strip()
            k, v = line.split('=', 1)
            yield k, v


def sysfs_scandir(path: str, name: str):
    for f in os.scandir(path):
        if f.is_dir() and f.name.startswith(name) and f.name[len(name):].isdecimal():
            yield f.path


def sysfs_find_class_devices(cls: type[_ClassDevice_TV], path: str | None = None):
    return map(cls, sysfs_scandir(path or '/sys/class/' + cls._class_name, cls._device_name))
