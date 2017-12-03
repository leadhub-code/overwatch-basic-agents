import argparse
from datetime import datetime
import logging
import psutil
import requests
from socket import getfqdn
from time import monotonic as monotime
from time import time, sleep

from .helpers import BaseConfiguration, setup_logging, setup_log_file


logger = logging.getLogger(__name__)

default_sleep_interval = 15

rs = requests.session()


def system_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    setup_logging()
    setup_logging(verbosity=args.verbose)
    conf = Configuration(args.conf_file)
    setup_log_file(conf.log.file_path)
    logger.debug('System agent starting')
    run_system_agent(conf)


class Configuration (BaseConfiguration):

    top_level_key = 'overwatch_system_agent'

    def _load(self, data, base_path):
        super()._load(data, base_path)


def run_system_agent(conf):
    sleep_interval = conf.sleep_interval or default_sleep_interval
    while True:
        run_system_agent_iteration(conf, sleep_interval)
        sleep(sleep_interval)


def run_system_agent_iteration(conf, sleep_interval):
    report_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    report_label = {
        'agent': 'system',
        'host': getfqdn(),
    }
    t0 = monotime()
    report_state = gather_state(conf)
    duration = monotime() - t0
    report_state['duration'] = duration

    # add watchdog
    wd_interval = conf.watchdog_interval or sleep_interval + 30
    report_state['watchdog'] = {
        '__watchdog': {
            'deadline': int((time() + wd_interval) * 1000),
        },
    }

    report_data = {
        'label': report_label,
        'date': report_date,
        'state': report_state,
    }

    try:
        r = rs.post(conf.report_url, json=report_data, headers={'Authorization': 'token ' + conf.report_token})
        logger.debug('Report response: %s', r.text[:100])
        r.raise_for_status()
    except Exception as e:
        logger.error('Failed to post report to %r: %r', conf.report_url, e)
        logger.info('Report token: %s...%s', conf.report_token[:3], conf.report_token[-3:])
        logger.info('Report data: %r', report_data)


def gather_state(conf):
    return {
        'cpu': gather_cpu(),
        'volumes': gather_volumes(),
    }


def gather_cpu():
    ct = psutil.cpu_times()
    cs = psutil.cpu_stats()
    return {
        'count': {
            'logical': psutil.cpu_count(logical=True),
            'physical': psutil.cpu_count(logical=False),
        },
        'times': {
            'user': ct.user,
            'system': ct.system,
            'idle': ct.idle,
            'iowait': ct.iowait,
        },
        'stats': {
            'ctx_switches': cs.ctx_switches,
            'interrupts': cs.interrupts,
            'soft_interrupts': cs.soft_interrupts,
            'syscalls': cs.syscalls,
        },
    }


def gather_volumes():
    volumes = {}
    for p in psutil.disk_partitions():
        usage = psutil.disk_usage(p.mountpoint)
        volumes[p.mountpoint] = {
            'mountpoint': p.mountpoint,
            'device': p.device,
            'fstype': p.fstype,
            'opts': p.opts,
            'usage': {
                'total_bytes': usage.total,
                'used_bytes': usage.used,
                'free_bytes': usage.free,
                'percent': {
                    '__value': usage.percent,
                    '__alarm': {
                        'state': 'green',
                    },
                }
            },
        }
    return volumes
