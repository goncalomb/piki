import asyncio
import contextlib
import ctypes
import dataclasses
import enum
import fcntl
import struct

import ioctl_opt

from .input import *
from .sysfs import *

# https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/ioctl.h
# https://github.com/torvalds/linux/blob/master/include/uapi/linux/lirc.h
# https://github.com/torvalds/linux/blob/master/drivers/media/rc/rc-main.c
# https://github.com/torvalds/linux/blob/master/drivers/media/rc/lirc_dev.c


class _lirc():
    MODE_RAW = 0x00000001
    MODE_PULSE = 0x00000002
    MODE_MODE2 = 0x00000004
    MODE_SCANCODE = 0x00000008
    MODE_LIRCCODE = 0x00000010
    SET_SEND_MODE = ioctl_opt.IOW(ord('i'), 0x00000011, ctypes.c_uint32)
    SET_REC_MODE = ioctl_opt.IOW(ord('i'), 0x00000012, ctypes.c_uint32)


class _lirc_scancode(ctypes.Structure):
    FLAG_TOGGLE = 1
    FLAG_REPEAT = 2

    _pack_ = 1
    _fields_ = [
        ('timestamp', ctypes.c_uint64),
        ('flags', ctypes.c_uint16),
        ('rc_proto', ctypes.c_uint16),
        ('keycode', ctypes.c_uint32),
        ('scancode', ctypes.c_uint64),
    ]


class _rc_proto(int, enum.Enum):
    UNKNOWN = 0, 'unknown'
    OTHER = 1, 'other'
    RC5 = 2, 'rc-5'
    RC5X_20 = 3, 'rc-5'
    RC5_SZ = 4, 'rc-5-sz'
    JVC = 5, 'jvc'
    SONY12 = 6, 'sony'
    SONY15 = 7, 'sony'
    SONY20 = 8, 'sony'
    NEC = 9, 'nec'
    NECX = 10, 'nec'
    NEC32 = 11, 'nec'
    SANYO = 12, 'sanyo'
    MCIR2_KBD = 13, 'mce_kbd'
    MCIR2_MSE = 14, 'mce_kbd'
    RC6_0 = 15, 'rc-6'
    RC6_6A_20 = 16, 'rc-6'
    RC6_6A_24 = 17, 'rc-6'
    RC6_6A_32 = 18, 'rc-6'
    RC6_MCE = 19, 'rc-6'
    SHARP = 20, 'sharp'
    XMP = 21, 'xmp'
    CEC = 22, 'cec'
    IMON = 23, 'imon'
    RCMM12 = 24, 'rc-mm'
    RCMM24 = 25, 'rc-mm'
    RCMM32 = 26, 'rc-mm'
    XBOX_DVD = 27, 'xbox-dvd'
    MAX = XBOX_DVD

    sysfs_name: str

    def __new__(cls, value: int, sysfs_name: str):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.sysfs_name = sysfs_name
        return obj


@dataclasses.dataclass
class LIRCScanCode():
    timestamp: int
    flags: int
    rc_proto: int
    keycode: int
    scancode: int

    @property
    def flags_tuple(self):
        F_TR = _lirc_scancode.FLAG_TOGGLE | _lirc_scancode.FLAG_REPEAT
        if self.flags & F_TR == F_TR:
            return 'toggle', 'repeat'
        elif self.flags & _lirc_scancode.FLAG_TOGGLE:
            return 'toggle',
        elif self.flags & _lirc_scancode.FLAG_REPEAT:
            return 'repeat',
        return tuple()

    @property
    def rc_proto_name(self):
        return _rc_proto(self.rc_proto).sysfs_name


@dataclasses.dataclass(eq=False)
class LIRCDevice(ClassDevice):
    _class_name = 'lirc'
    _device_name = 'lirc'


@dataclasses.dataclass(eq=False)
class RCDevice(ClassDevice, children=[LIRCDevice, InputDevice]):
    _class_name = 'rc'
    _device_name = 'rc'
    lirc: list[LIRCDevice]
    lirc0: LIRCDevice | None
    input: list[InputDevice]
    input0: InputDevice | None

    @property
    def protocols(self):
        result: list[tuple[str, bool]] = []
        with open(self.path + '/protocols') as fp:
            line = fp.readline()
            if line:
                line = line.strip()
                for proto in line.split(' '):
                    if proto[0] == '[' and proto[-1] == ']':
                        result.append((proto[1:-1], True))
                    else:
                        result.append((proto, False))
        return result

    @protocols.setter
    def protocols(self, value: None | str | list[tuple[str, bool]]):
        with open(self.path + '/protocols', 'w') as fp:
            if not value:
                fp.write('none\n')
            elif isinstance(value, str):
                fp.write(value + '\n')
            else:
                for proto, on in value:
                    fp.write(('+' if on else '-') + proto + '\n')


class LIRCDeviceIO(contextlib.AbstractContextManager):
    _frame_size = ctypes.sizeof(_lirc_scancode)
    _max_frames = 64
    _read_size = _frame_size * _max_frames

    def __init__(self, dev_path: str):
        self._fp = open(dev_path, 'rb', buffering=False)
        self._set_rec_mode_scancode()

    def _set_rec_mode_scancode(self):
        buf = struct.pack('I', _lirc.MODE_SCANCODE)
        fcntl.ioctl(self._fp.fileno(), _lirc.SET_REC_MODE, buf)

    @property
    def closed(self):
        return self._fp.closed

    def read(self):
        buf = self._fp.read(self._read_size)
        if not buf:
            # raise BlockingIOError caught internally
            # this would only happen if fd is set to non-blocking (asyncio)
            # and somehow we tried to read without any data available (bug?)
            raise BlockingIOError()

        # only multiples of frame size are expected
        assert len(buf) % self._frame_size == 0

        # a generator wrapper is required to make sure that the internal read
        # call happens right away instead of on the first yield
        def gen():
            for offset in range(0, len(buf), self._frame_size):
                sc = _lirc_scancode.from_buffer_copy(buf, offset)
                yield LIRCScanCode(sc.timestamp, sc.flags, sc.rc_proto, sc.keycode, sc.scancode)
        return gen()

    def write(self, *args, **kwargs):
        # TODO: add write support
        raise NotImplementedError()

    def close(self):
        self._fp.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        self.close()


class LIRCDeviceAsyncIO(LIRCDeviceIO):
    def __init__(self, dev_path: str):
        super().__init__(dev_path)
        self._loop = asyncio.get_running_loop()
        self._read_future = None
        # set fd to non-blocking to avoid any chance of it blocking the loop
        # even if we never read without knowing there is data available
        os.set_blocking(self._fp.fileno(), False)

    def _read_cb(self):
        self._loop.remove_reader(self._fp)
        try:
            if not self._read_future.done():
                self._read_future.set_result(super().read())
        except Exception as e:
            self._read_future.set_exception(e)
        finally:
            self._read_future = None

    def read(self) -> asyncio.Future[typing.Generator[LIRCScanCode, typing.Any, None]]:
        if not self._read_future:
            self._read_future = self._loop.create_future()
            self._loop.add_reader(self._fp, self._read_cb)
        return self._read_future

    def close(self):
        if not self._fp.closed:
            self._loop.remove_reader(self._fp)
        super().close()
        if not self._read_future:
            # if not reading right now create a new cancelled future that will
            # be returned by any subsequent calls to read
            self._read_future = self._loop.create_future()
        self._read_future.cancel()


def lirc_find_devices():
    return sysfs_find_class_devices(LIRCDevice)


def lirc_open_device(dev_path: str | LIRCDevice):
    if isinstance(dev_path, str):
        return LIRCDeviceIO(dev_path)
    return LIRCDeviceIO(dev_path.dev_path)


def lirc_open_device_async(dev_path: str | LIRCDevice):
    if isinstance(dev_path, str):
        return LIRCDeviceAsyncIO(dev_path)
    return LIRCDeviceAsyncIO(dev_path.dev_path)


def rc_find_devices():
    return sysfs_find_class_devices(RCDevice)


@contextlib.contextmanager
def rc_device_all_protocols_context(sys_path: str | RCDevice):
    dev = RCDevice(sys_path) if isinstance(sys_path, str) else sys_path
    proto_org = dev.protocols
    proto_err = None
    if all(map(lambda x: x[1], proto_org)):
        # all protocols already enabled, nothing to do
        yield proto_org, proto_err
    else:
        # try to enable all protocols
        try:
            dev.protocols = [(p, True) for p, on in proto_org]
        except PermissionError as err:
            proto_err = err
        try:
            yield proto_org, proto_err
        finally:
            # reset protocols
            if not proto_err:
                dev.protocols = proto_org
