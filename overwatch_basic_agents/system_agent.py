import argparse
import logging

from .helpers import BaseConfiguration, setup_logging


logger = logging.getLogger(__name__)


def system_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    setup_logging()
    setup_logging(verbosity=args.verbose)
    conf = Configuration(args.conf_file)
    setup_log_file(conf.log.file_path)


class Configuration (BaseConfiguration):

    top_level_key = 'overwatch_system_agent'

    def _load(self, data, base_path):
        super()._load(data, base_path)
