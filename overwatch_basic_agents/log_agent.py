import argparse
from collections import deque
from datetime import datetime
from itertools import count
import logging
import os
import re
from reprlib import repr as smart_repr
import requests
from socket import getfqdn
from time import monotonic as monotime
from time import sleep, time

from .helpers import BaseConfiguration, setup_logging, setup_log_file


logger = logging.getLogger(__name__)

default_sleep_interval = 10
default_report_timeout = 10

rs = requests.session()


def log_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    setup_logging(verbosity=args.verbose)
    conf = Configuration(args.conf_file)
    setup_log_file(conf.log.file_path)
    logger.debug('Log agent starting')
    run_log_agent(conf)


class Configuration (BaseConfiguration):

    top_level_key = 'overwatch_log_agent'

    def _load(self, data, base_path):
        super()._load(data, base_path)
        if not isinstance(data['log_files'], list):
            raise Exception('Configuration item overwatch_web_agent.watch must be a list')
        self.log_files = [LogFile(d, base_path) for d in data['log_files']]


class LogFile:

    def __init__(self, data, base_path):
        self.path = base_path / data['path']
        self.name = data.get('name')
        self.error_patterns = [Pattern(d) for d in data['error_patterns']]


class Pattern:

    def __init__(self, data):
        self.regex_str = data.get('regex')
        self.regex = re.compile(self.regex_str) if self.regex_str else None


def run_log_agent(conf):
    wfs = [WatchedFile(lf) for lf in conf.log_files]
    sleep_interval = conf.sleep_interval or default_sleep_interval
    while True:
        t0 = monotime()
        report = {
            'label': {
                'agent': 'log',
                'host': getfqdn(),
            },
            'date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'state': {
                'configuration_file': str(conf.conf_file_path),
                'log_files': {},
            },
        }
        for wf in wfs:
            wf.run(timestamp=time())
            wf.add_to_report(report['state'])
        finish_and_send_report(report, conf, sleep_interval, t0)
        sleep(sleep_interval)


def finish_and_send_report(report_data, conf, sleep_interval, t0):
    # add watchdog
    wd_interval = conf.watchdog_interval or sleep_interval + 30
    report_data['state']['watchdog'] = {
        '__watchdog': {
            'deadline': int((time() + wd_interval) * 1000),
        },
    }
    report_data['state']['iteration_duration_s'] = monotime() - t0
    try:
        r = rs.post(
            conf.report_url,
            json=report_data,
            headers={'Authorization': 'token ' + conf.report_token},
            timeout=default_report_timeout)
        logger.debug('Report response: %s', r.text[:100])
        r.raise_for_status()
    except Exception as e:
        logger.error('Failed to post report to %r: %r', conf.report_url, e)
        logger.info('Report token: %s...%s', conf.report_token[:3], conf.report_token[-3:])
        logger.info('Report data: %r', report_data)


class WatchedFile:

    def __init__(self, wf_conf):
        self.wf_conf = wf_conf
        self.f = None
        self.stat = None
        self.error_lines = deque(maxlen=10)
        self.line_counter = count()

    def run(self, timestamp):
        if self.f is None:
            logger.debug('Opening file %s', self.wf_conf.path)
            self.full_path = self.wf_conf.path.resolve()
            self.f = self.full_path.open('rb')
            self.stat = os.stat(self.f.fileno())
        while True:
            line = self.f.readline()
            if line == b'':
                break
            self.process_line(line, timestamp)
        current_stat = os.stat(self.f.fileno())
        same_file = all((
            self.stat.st_ino == current_stat.st_ino,
            self.stat.st_dev == current_stat.st_dev,
        ))
        if not same_file:
            logger.debug('Closing file %s', self.full_path)
            self.f = None
            self.stat = None

    def process_line(self, line_bytes, timestamp):
        try:
            line = line_bytes.decode().rstrip()
        except ValueError as e:
            logger.warning('Failed to decode line %s: %r', smart_repr(line_bytes), e)
            line = str(line_bytes)
        is_error = False
        for ep in self.wf_conf.error_patterns:
            if ep.regex and ep.regex.search(line):
                is_error = True
        if is_error:
            n = next(self.line_counter)
            self.error_lines.append((timestamp, n, line))

    def add_to_report(self, report_state):
        real_name = str(self.wf_conf.name or self.full_path)
        wf_state = report_state['log_files'][real_name] = {
            'path': str(self.full_path),
            'size_bytes': self.stat.st_size,
            'inode': '{}:{}'.format(self.stat.st_dev, self.stat.st_ino),
            'last_error_lines': {},
            'last_error_date': {
                '__value': None,
                '__check': {'state': 'green'},
            },
        }
        for timestamp, n, line in self.error_lines:
            k = '{}:{}'.format(timestamp, n)
            wf_state['last_error_lines'][k] = {
                'date': datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'line': line,
            }
        if self.error_lines:
            last_error_ts = max(ts for ts, n, line in self.error_lines)
            wf_state['last_error_date']['__value'] = datetime.utcfromtimestamp(last_error_ts).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            last_error_dt = time() - last_error_ts
            if last_error_dt < 10 * 60:
                wf_state['last_error_date']['__check']['state'] = 'red'
            #elif last_error_dt < 60 * 60:
            #    wf_state['last_error_date']['__check']['state'] = 'orange'
