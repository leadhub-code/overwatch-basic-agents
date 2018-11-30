import argparse
from datetime import datetime
from datetime import timedelta
import logging
import os
import psutil
import requests
from socket import getfqdn
from time import monotonic as monotime
from time import time, sleep

from .helpers import BaseConfiguration, setup_logging, setup_log_file


logger = logging.getLogger(__name__)

default_sleep_interval = 15
default_report_timeout = 10

rs = requests.session()


def system_agent_main():
    p = argparse.ArgumentParser()
    p.add_argument('--verbose', '-v', action='count')
    p.add_argument('conf_file')
    args = p.parse_args()
    try:
        setup_logging(verbosity=args.verbose)
        conf = Configuration(args.conf_file)
        setup_log_file(conf.log.file_path)
        logger.debug('System agent starting')
        run_system_agent(conf)
    except BaseException as e:
        logger.exception('System agent failed: %r', e)
        raise e


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
        r = rs.post(conf.report_url,
            json=report_data,
            headers={'Authorization': 'token ' + conf.report_token},
            timeout=default_report_timeout)
        logger.debug('Report response: %s', r.text[:100])
        r.raise_for_status()
    except Exception as e:
        logger.error('Failed to post report to %r: %r', conf.report_url, e)
        logger.info('Report token: %s...%s', conf.report_token[:3], conf.report_token[-3:])
        logger.info('Report data: %r', report_data)


def gather_state(conf):
    return {
        'cpu': gather_cpu(),
        'load': gather_load(),
        'uptime': gather_uptime(),
        'volumes': gather_volumes(),
        'memory': gather_memory(),
        'swap': gather_swap(),
        'outward_ip4': gather_outward_ip4(),
        'outward_ip6': gather_outward_ip6(),
    }


def gather_outward_ip4():
    try:
        r = rs.get('https://ip4.messa.cz/')
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        logger.warning('Failed to retrieve outward_ip4: %r', e)
        return None


def gather_outward_ip6():
    try:
        r = rs.get('https://ip6.messa.cz/')
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        # log as just info, because some hosts have IPv6 not configured
        logger.info('Failed to retrieve outward_ip6: %r', e)
        return None


def gather_load():
    data = {
        '01m': round(os.getloadavg()[0], 2),
        '05m': round(os.getloadavg()[1], 2),
        '15m': round(os.getloadavg()[2], 2)
    }
    return data


def gather_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_string = str(timedelta(seconds = uptime_seconds))
    except FileNotFoundError as e:
        logger.debug('Cannot determine uptime: %s', e)
        return None
    data = {
        'seconds': round(uptime_seconds, 0),
        'string': uptime_string
    }
    return data


def gather_cpu():
    ct = psutil.cpu_times()
    cs = psutil.cpu_stats()
    data = {
        'count': {
            'logical': psutil.cpu_count(logical=True),
            'physical': psutil.cpu_count(logical=False),
        },
        'times': {},
        'stats': {
            'ctx_switches': cs.ctx_switches,
            'interrupts': cs.interrupts,
            'soft_interrupts': cs.soft_interrupts,
            'syscalls': cs.syscalls,
        },
    }
    for k in 'user', 'system', 'idle', 'iowait':
        try:
            data['times'][k] = getattr(ct, k)
        except AttributeError:
            pass
    return data


def gather_volumes():
    percent_red_threshold = 92
    free_bytes_red_threshold = 2 * 2**30 # 2 GB
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
                'free_bytes': {
                    '__value': usage.free,
                    '__check': {
                        'state': 'red' if usage.total >= free_bytes_red_threshold * 4 and usage.free < free_bytes_red_threshold else 'green',
                    },
                },
                'percent': {
                    '__value': usage.percent,
                    '__check': {
                        'state': 'red' if usage.percent >= percent_red_threshold else 'green',
                    },
                }
            },
        }
    return volumes


def gather_memory():
    mem = psutil.virtual_memory()
    return {
        'total_bytes': mem.total,
        'available_bytes': mem.available,
    }


def gather_swap():
    sw = psutil.swap_memory()
    return {
        'total_bytes': sw.total,
        'used_bytes': sw.used,
        'free_bytes': sw.free,
        'percent': {
            '__value': sw.percent,
            '__check': {
                'state': 'red' if sw.percent > 80 else 'green',
            },
        },
    }
