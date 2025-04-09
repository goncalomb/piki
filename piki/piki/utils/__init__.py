import importlib.metadata
import os
import sys


def pkg_find_version(name: str, unknown=None):
    try:
        return importlib.metadata.version(name)
    except ModuleNotFoundError:
        return unknown


def venv_find_dir(name='.venv'):
    if 'VIRTUAL_ENV' in os.environ:
        return os.environ['VIRTUAL_ENV']
    if sys.executable:
        parts = sys.executable.split(os.path.sep)
        for i in range(0, len(parts) - 1):
            if parts[i] == name and parts[i + 1] == 'bin':
                return os.sep.join(parts[:i + 1])
    return ''
