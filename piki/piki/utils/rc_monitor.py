import asyncio
import contextlib

from .linux import rc
from .pkg import evdev


async def rc_monitor(dev: rc.RCDevice, *, cb_lirc=None, cb_event=None, cb_start=None):
    if cb_lirc and not (dev_lirc := dev.lirc0):
        cb_lirc = None
    if cb_event and not dev.input0 or not (dev_event := dev.input0.event0):
        cb_event = None

    with (
        rc.rc_device_all_protocols_context(dev) as (proto_org, proto_err),
        rc.lirc_open_device_async(dev_lirc) if cb_lirc else contextlib.nullcontext() as lirc_io,
        evdev.evdev_open_device(dev_event) if cb_event else contextlib.nullcontext() as event_io,
    ):
        def stop():
            # graceful stop
            # internal cancelled futures are suppressed, see below
            if lirc_io:
                lirc_io.close()
            if event_io:
                event_io.close()

        async def read_lirc():
            if lirc_io:
                with contextlib.suppress(asyncio.CancelledError):
                    while scs := await lirc_io.read():
                        for sc in scs:
                            cb_lirc(dev, stop, sc)

        async def read_event():
            if event_io:
                with contextlib.suppress(asyncio.CancelledError):
                    while evs := await event_io.async_read():
                        for ev in evs:
                            cb_event(dev, stop, ev)

        if cb_start:
            cb_start(dev, stop, proto_org, proto_err)

        await asyncio.gather(read_lirc(), read_event())


def rc_print_device(dev: rc.RCDevice):
    print('%s:' % dev.path.split('/')[-1], dev.path)
    for k, v in dev.uevent.items():
        print('  %s=%s' % (k, v))
    if d := dev.lirc0:
        print('  lirc: %s [%s] [%s]' % (d.path, d.dev_number, d.dev_path))
    if dev.input0 and (d := dev.input0.event0):
        print('  event: %s [%s] [%s]' % (d.path, d.dev_number, d.dev_path))
    print('  protocols:', end='')
    for proto, on in dev.protocols:
        print((' [%s]' if on else ' %s') % proto, end='')
    print()


def rc_print_sc(sc: rc.LIRCScanCode, **kwargs):
    print(
        '%d.%06d:' % (sc.timestamp / 1e9, sc.timestamp % 1e9 / 1e3), 'lirc',
        'proto=%s(0x%02x)' % (sc.rc_proto_name, sc.rc_proto),
        'keycode=%s(0x%04x)' % (evdev.ecodes.keys[sc.keycode], sc.keycode),
        'scancode=0x%04x' % sc.scancode,
        'flags=%s' % ','.join(sc.flags_tuple),
        **kwargs,
    )


def rc_print_ev(ev: evdev.InputEvent, **kwargs):
    print(
        '%d.%06d:' % (ev.sec, ev.usec), 'event',
        'type=%s(0x%02x)' % (evdev.ecodes.EV[ev.type], ev.type),
        'code=%s(0x%04x)' % (evdev.ecodes.bytype[ev.type][ev.code], ev.code),
        'value=0x%04x' % ev.value,
        **kwargs,
    )
