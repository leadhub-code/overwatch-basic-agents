import argparse
import logging

from .helpers import setup_logging, setup_log_file


logger = logging.getLogger(__name__)





def web_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    setup_logging(verbosity=args.verbose)
    conf = Configuration(args.conf_file)
    setup_log_file(conf.log_file_path)
