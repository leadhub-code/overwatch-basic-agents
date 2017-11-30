import argparse
import logging

from .helpers import setup_logging


logger = logging.getLogger(__name__)


def system_agent_main():
    p = argparse.ArgumentParser()
    args = p.parse_args()
    setup_logging()
