import argparse
from datetime import datetime
import logging
import requests
from socket import AF_INET, getfqdn, socket
import ssl
from time import monotonic as monotime
from time import sleep, time
from urllib.parse import urlparse

from .helpers import BaseConfiguration, setup_logging, setup_log_file


logger = logging.getLogger(__name__)

default_sleep_interval = 30
default_timeout = 10
default_report_timeout = 10
default_user_agent = 'Overwatch Web Agent'


def web_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    try:
        setup_logging(verbosity=args.verbose)
        conf = Configuration(args.conf_file)
        setup_log_file(conf.log.file_path)
        logger.debug('Web agent starting')
        run_web_agent(conf)
    except BaseException as e:
        logger.exception('Web agent failed: %r', e)
        raise e


class Configuration (BaseConfiguration):

    top_level_key = 'overwatch_web_agent'

    def _load(self, data, base_path):
        super()._load(data, base_path)
        if not isinstance(data['watch'], list):
            raise Exception('Configuration item overwatch_web_agent.watch must be a list')
        self.watch_targets = [Target(d) for d in data['watch']]


class Target:

    def __init__(self, data):
        self.name = data.get('name')
        self.url = data['url']
        self.response_contains = data.get('response_contains')


def run_web_agent(conf):
    sleep_interval = conf.sleep_interval or default_sleep_interval
    while True:
        run_web_agent_iteration(conf, sleep_interval)
        sleep(sleep_interval)


def run_web_agent_iteration(conf, sleep_interval):
    rs = requests.session()
    for n, target in enumerate(conf.watch_targets, start=1):
        logger.info('Processing target %d/%d: %s', n, len(conf.watch_targets), target.url)
        process_target(conf, sleep_interval, rs, target)


def process_target(conf, sleep_interval, rs, target):
    report_data = {
        'date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'label': {
            'agent': 'web',
            'host': getfqdn(),
            'target': target.name or target.url,
        },
        'state': {},
    }
    check_target(rs, target, report_data['state'])

    # add watchdog
    wd_interval = conf.watchdog_interval or sleep_interval + 30
    report_data['state']['watchdog'] = {
        '__watchdog': {'deadline': int((time() + wd_interval) * 1000)},
    }

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


def check_target(rs, target, report_state, timeout=None):
    '''
    parameter timeout is used in tests
    '''
    report_state['name'] = target.name
    report_state['url'] = target.url

    # check SSL
    if target.url.startswith('https://'):
        p = urlparse(target.url)
        logger.info('Checking SSL cert of %s:%s', p.hostname, p.port)
        hostname = p.hostname
        port = p.port or 443
        t0 = monotime()
        cx = ssl.create_default_context()
        conn = cx.wrap_socket(socket(AF_INET), server_hostname=hostname)
        conn.settimeout(5)
        conn.connect((p.hostname, port or 443))
        try:
            cert = conn.getpeercert()
            peer_ip, peer_port = conn.getpeername()
            logger.debug('Connected to %s (%s) port %s, cert: %r', hostname, peer_ip, port, cert)
        finally:
            conn.close()
        del conn
        del cx
        expire_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
        remaining_days = (expire_date - datetime.utcnow()).total_seconds() / 86400
        report_state['ssl_certificate'] = {
            'hostname': hostname,
            'port': port,
            'ip': peer_ip,
            'notBefore': cert['notBefore'],
            'notAfter': cert['notAfter'],
            'serialNumber': cert['serialNumber'],
            'remaining_days': {
                '__value': remaining_days,
                '__check': {
                    'state': 'red' if remaining_days < 10 else 'green',
                },
            },
        }
        duration = monotime() - t0
        logger.info('SSL check took %.3f s', duration)

    # make HTTP request
    t1 = monotime()
    try:
        try:
            r = rs.get(target.url,
                headers={
                    'User-Agent': default_user_agent,
                },
                timeout=timeout or default_timeout)
        finally:
            duration = monotime() - t1
            report_state['duration_seconds'] = duration
    except Exception as e:
        logger.info('Exception while processing url %r: %r', target.url, e)
        report_state['error'] = {
            '__value': str(e),
            '__check': {'state': 'red'},
        }
        return

    report_state['error'] = {
        '__value': None,
        '__check': {'state': 'green'},
    }
    report_state['final_url'] = r.url
    report_state['response'] = {
        'status_code': {
            '__value': r.status_code,
            '__check': {
                'state': 'green' if r.status_code == 200 else 'red',
            },
        },
        'content_length': len(r.content),
    }

    if target.response_contains:
        present = target.response_contains in r.text
        report_state['response_contains'] = {
            'text': target.response_contains,
            'present': {
                '__value': present,
                '__check': {
                    'state': 'green' if present else 'red',
                },
            },
        }
