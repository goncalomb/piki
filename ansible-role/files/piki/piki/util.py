import os
import subprocess
import sys


def find_venv_dir():
    if 'VIRTUAL_ENV' in os.environ:
        return os.environ['VIRTUAL_ENV']
    if sys.executable:
        parts = sys.executable.split(os.path.sep)
        for i in range(0, len(parts) - 1):
            if parts[i] == '.venv' and parts[i + 1] == 'bin':
                return os.sep.join(parts[:i + 1])
    return ''


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
