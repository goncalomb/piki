import asyncio

from .utils.rc_monitor import *

async def main_run():
    dev_first_valid = None
    for dev in rc.rc_find_devices():
        rc_print_device(dev)
        if not dev_first_valid and dev.lirc0 and dev.input0 and dev.input0.event0:
            dev_first_valid = dev

    if not dev_first_valid:
        print("no valid rc devices to monitor")
        return

    print()

    def cb_start(dev, stop, proto_org, proto_err):
        proto_now = map(lambda x: x[0], filter(lambda x: x[1], dev.protocols))
        print("monitoring", dev.path, "(CTRL-C to exit)")
        if proto_err:
            print("failed to enable all rc protocols, permission denied")
        print("enabled rc protocols:", ', '.join(proto_now))
        print()

    with contextlib.suppress(asyncio.CancelledError):
        await rc_monitor(
            dev_first_valid,
            cb_lirc=lambda dev, stop, sc: rc_print_sc(sc),
            cb_event=lambda dev, stop, ev: rc_print_ev(ev),
            cb_start=cb_start,
        )


def main():
    asyncio.run(main_run())
