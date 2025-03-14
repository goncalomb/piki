import subprocess
import sys


def process_check_call(cmd, sudo=False):
    if sudo:
        cmd = ['sudo', '-n'] + cmd
    return subprocess.check_call(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=sys.stderr,
    )


def process_check_output(cmd, sudo=False):
    if sudo:
        cmd = ['sudo', '-n'] + cmd
    return subprocess.check_output(
        cmd,
        stdin=subprocess.DEVNULL,
        stderr=sys.stderr,
        encoding='utf-8',
    )


def get_local_ips():
    return process_check_output(['hostname', '-I']).strip()
