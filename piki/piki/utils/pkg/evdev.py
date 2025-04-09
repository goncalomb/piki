import asyncio
import typing

from evdev import *

from ..linux import input as _input

# this util is a extension of the 'evdev' package with some asyncio fixes
# and better integration with our other linux input utils


class EventDeviceIO(InputDevice):
    def __init__(self, dev):
        super().__init__(dev)
        self._read_future = None
        # extra: monotonic clock
        _input.event_device_ioctl_set_clock_id(self.fd, 'monotonic')

    # fixed: not checking for invalid future (e.g. cancelled)
    def _set_result(self, future, cb):
        self._read_future = None
        if not future.done():
            super()._set_result(future, cb)

    # fixed: read not happening synchronously because of generator
    def read(self):
        rest = super().read()
        # call next to advance generator and trigger the internal file read
        first = next(rest)

        # return a new generator that yields everything anyway
        def gen():
            yield first
            for r in rest:
                yield r
        return gen()

    # XXX: we don't need this
    def async_read_one(self):
        raise NotImplementedError()

    # fixed: not keeping track of future to cancel on close
    def async_read(self) -> asyncio.Future[typing.Generator[InputEvent, typing.Any, None]]:
        if not self._read_future:
            self._read_future = super().async_read()
        return self._read_future

    # XXX: we don't need this
    def async_read_loop(self):
        raise NotImplementedError()

    # fixed: not removing reader and not cancelling future
    def close(self):
        try:
            if not self.fd < 0:
                asyncio.get_running_loop().remove_reader(self.fd)
        except RuntimeError:
            # not asyncio session
            pass
        super().close()
        if not self._read_future:
            self._read_future = asyncio.get_running_loop().create_future()
        self._read_future.cancel()

    # extra: use as context manager
    def __enter__(self):
        return self

    # extra: use as context manager
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def evdev_find_devices():
    return _input.event_find_devices()


def evdev_open_device(dev_path: str | _input.EventDevice):
    if isinstance(dev_path, str):
        return EventDeviceIO(dev_path)
    return EventDeviceIO(dev_path.dev_path)
