import logging
import os
import shutil
import subprocess
import sys

import click

from . import CoreController

__doc__ = 'PiKi core program.'


def exec_check_call(cmd, stdin=subprocess.DEVNULL):
    print('executing: %s' % cmd, file=sys.stderr)
    subprocess.check_call(cmd, stdin=stdin)


def restart_piki_core():
    exec_check_call(['sudo', 'systemctl', 'restart', 'piki-core.service'])


@click.group(help=__doc__)
def main():
    pass


@main.command(help="Run piki-core (to be run as service connected to a tty).")
def run():
    logging.basicConfig(level=logging.INFO)
    CoreController().run()


@main.group(help="Debug utilities.")
def debug():
    pass


@debug.command(name='restart', help="Restart piki-core.")
def _():
    try:
        restart_piki_core()
    except Exception as e:
        print(e, file=sys.stderr)


@debug.command(name='send-plugin', help="Write/Update plugin file over SSH to a remote piki installation.")
@click.argument('file')
@click.argument('ssh-args', required=True, nargs=-1)
@click.option('-d', '--piki-dir', default='/opt/piki', help="Remote piki installation location (piki_dir).")
@click.option('-n', '--name', help="Remote plugin filename defaults to local basename.")
@click.option('-r', '--restart', is_flag=True, help="Also restart piki-core.")
def _(file, ssh_args, piki_dir, name, restart):
    try:
        if not name:
            name = os.path.basename(file)
        with open(file, 'rb') as fp:
            exec_check_call(['ssh'] + list(ssh_args) + [
                '--', os.path.join(piki_dir, 'bin', 'piki-core'),
                'debug', 'write-plugin',
            ] + (['-r', name] if restart else [name]), stdin=fp)
    except Exception as e:
        print(e, file=sys.stderr)


@debug.command(name='write-plugin', help="Write/Update plugin file from STDIN, use over SSH or with 'send-plugin'.")
@click.argument('name')
@click.option('-r', '--restart', is_flag=True, help="Also restart piki-core.")
def _(name, restart):
    try:
        piki_plugins_dir = CoreController.piki_plugins_dir
        path = os.path.join(piki_plugins_dir, name)
        print('writing: %s' % path, file=sys.stderr)
        with open(path, 'wb') as fp:
            shutil.copyfileobj(sys.stdin.buffer, fp)
        if restart:
            restart_piki_core()
    except Exception as e:
        print(e, file=sys.stderr)


if __name__ == '__main__':
    main()
