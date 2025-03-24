import logging

from . import internal


def main():
    logging.basicConfig(level=logging.INFO)
    internal.core.Controller().run()
