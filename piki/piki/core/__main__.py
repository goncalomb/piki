import logging

from . import Controller

__doc__ = 'PiKi core program (to be run as a service).'


def main():
    logging.basicConfig(level=logging.INFO)
    Controller().run()


if __name__ == '__main__':
    main()
