
import asyncio
import contextlib

import click

from .linux.rc import rc_find_devices
from .rc_monitor import rc_monitor, rc_print_device, rc_print_ev, rc_print_sc

__doc__ = 'PiKi utility program.'


async def rc_monitor_run(dev, no_lirc, no_input):
    if no_lirc:
        print("INFO: not monitoring lirc device by request")
    elif not dev.lirc0:
        print("WARNING: not monitoring lirc device, no interface")
        no_lirc = True

    if no_input:
        print("INFO: not monitoring input device by request")
    elif not dev.input0 or not dev.input0.event0:
        print("WARNING: not monitoring input device, no interface")
        no_input = True

    if no_lirc and no_input:
        print()
        print('nothing to do')
        return

    def cb_start(dev, stop, proto_org, proto_err):
        proto_now = map(lambda x: x[0], filter(lambda x: x[1], dev.protocols))
        if proto_err:
            print("WARNING: failed to enable all rc protocols, permission denied")
        print("enabled rc protocols:", ', '.join(proto_now))
        print("monitoring", dev.path, "(CTRL-C to exit)")
        print()

    with contextlib.suppress(asyncio.CancelledError):
        await rc_monitor(
            dev,
            cb_lirc=None if no_lirc else lambda d, stop, sc: rc_print_sc(sc),
            cb_event=None if no_input else lambda d, stop, ev: rc_print_ev(ev),
            cb_start=cb_start,
        )


@click.group(help=__doc__)
def main():
    pass


@main.group(help="Utilities to manage remote controller (rc) devices.")
def rc():
    pass


@rc.command(name='list', help="List rc devices.")
def _():
    for dev in rc_find_devices():
        rc_print_device(dev)


@rc.command(name='monitor', help="Monitor rc device events.")
@click.argument('device')
@click.option('--no-lirc', is_flag=True, help="Don't monitor lirc events.")
@click.option('--no-input', is_flag=True, help="Don't monitor input events.")
def _(device, no_lirc, no_input):
    def find_dev():
        for dev in rc_find_devices():
            if dev.path == device or dev.path.split('/')[-1] == device:
                return dev

    ctx = click.get_current_context()
    dev = find_dev()
    if not dev:
        ctx.fail("Device '%s' not found, use /sys/class/rc/rcX or just rcX." % device)

    rc_print_device(dev)
    print()
    asyncio.run(rc_monitor_run(dev, no_lirc, no_input))


if __name__ == '__main__':
    main()
