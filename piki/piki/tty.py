import logging

from . import core


def main():
    logging.basicConfig(level=logging.INFO)
    core.Controller().run()
