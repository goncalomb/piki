import ctypes
import dataclasses
import fcntl
import struct
import typing

import ioctl_opt

from .sysfs import *

# https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/ioctl.h
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/input.h
# https://github.com/torvalds/linux/blob/master/drivers/input/input.c
# https://github.com/torvalds/linux/blob/master/drivers/input/evdev.c


class _input():
    EVIOCSCLOCKID = ioctl_opt.IOW(ord('E'), 0xa0, ctypes.c_uint32)


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


def event_device_ioctl_set_clock_id(fd: int, clock: typing.Literal['realtime', 'monotonic', 'boottime']):
    # https://github.com/torvalds/linux/blob/master/include/uapi/linux/time.h
    clk = {'realtime': 0, 'monotonic': 1, 'boottime': 7}[clock]
    buf = struct.pack('I', clk)
    fcntl.ioctl(fd, _input.EVIOCSCLOCKID, buf)


def input_find_devices():
    return sysfs_find_class_devices(InputDevice)
