import logging

from . import core

__doc__ = 'PiKi core TTY program (to be run as a service).'


def main():
    logging.basicConfig(level=logging.INFO)
    core.Controller().run()


if __name__ == '__main__':
    main()
