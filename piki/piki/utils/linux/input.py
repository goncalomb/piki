import dataclasses

from .sysfs import *

# https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/ioctl.h
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/input.h
# https://github.com/torvalds/linux/blob/master/drivers/input/input.c
# https://github.com/torvalds/linux/blob/master/drivers/input/evdev.c


@dataclasses.dataclass(eq=False)
class EventDevice(ClassDevice):
    _class_name = 'input'
    _device_name = 'event'


@dataclasses.dataclass(eq=False)
class InputDevice(ClassDevice, children=[EventDevice]):
    _class_name = 'input'
    _device_name = 'input'
    event: list[EventDevice]
    event0: EventDevice | None


def event_find_devices():
    return sysfs_find_class_devices(EventDevice)


def input_find_devices():
    return sysfs_find_class_devices(InputDevice)
