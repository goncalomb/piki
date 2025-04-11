import logging

from . import CoreController

__doc__ = 'PiKi core program (to be run as a service).'


def main():
    logging.basicConfig(level=logging.INFO)
    CoreController().run()


if __name__ == '__main__':
    main()
