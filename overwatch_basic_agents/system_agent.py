import argparse
from collections import OrderedDict
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
    report_label = OrderedDict()
    report_label['agent'] = 'system'
    report_label['host'] = getfqdn()
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
    state = OrderedDict()
    state['cpu'] = gather_cpu()
    state['load'] = gather_load()
    state['uptime'] = gather_uptime()
    state['volumes'] = gather_volumes()
    state['memory'] = gather_memory()
    state['swap'] = gather_swap()
    state['outward_ip4'] = gather_outward_ip4()
    state['outward_ip6'] = gather_outward_ip6()
    return state


def value(value, counter=None, unit=None, check_state=None):
    '''
    Helper function to generate the report value metadata fragment.
    '''
    data = {
        '__value': value,
    }
    if counter:
        data['__counter'] = True
    if unit:
        data['__unit'] = unit
    if check_state:
        data.setdefault('__check', {})
        data['__check']['state'] = check_state
    return data


def gather_outward_ip4():
    try:
        r = rs.get('https://ip4.messa.cz/', timeout=10)
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        logger.warning('Failed to retrieve outward_ip4: %r', e)
        return None


def gather_outward_ip6():
    try:
        r = rs.get('https://ip6.messa.cz/', timeout=10)
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        # log as just info, because some hosts have IPv6 not configured
        logger.info('Failed to retrieve outward_ip6: %r', e)
        return None


def gather_load():
    data = OrderedDict()
    data['01m'] = round(os.getloadavg()[0], 2)
    data['05m'] = round(os.getloadavg()[1], 2)
    data['15m'] = round(os.getloadavg()[2], 2)
    return data


def gather_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_string = str(timedelta(seconds = uptime_seconds))
    except FileNotFoundError as e:
        logger.debug('Cannot determine uptime: %s', e)
        return None
    data = OrderedDict()
    data['seconds'] = value(round(uptime_seconds, 0), unit='seconds')
    data['string'] = uptime_string
    return data


def gather_cpu():
    ct = psutil.cpu_times()
    cs = psutil.cpu_stats()
    data = OrderedDict()
    data['count'] = OrderedDict()
    data['count']['logical'] = psutil.cpu_count(logical=True)
    data['count']['physical'] = psutil.cpu_count(logical=False)
    data['times'] = OrderedDict()
    data['stats'] = OrderedDict()
    data['stats']['ctx_switches'] = value(cs.ctx_switches, counter=True)
    data['stats']['interrupts'] = value(cs.interrupts, counter=True)
    data['stats']['soft_interrupts'] = value(cs.soft_interrupts, counter=True)
    data['stats']['syscalls'] = value(cs.syscalls, counter=True)
    for k in 'user', 'system', 'idle', 'iowait':
        try:
            data['times'][k] = value(getattr(ct, k), unit='seconds', counter=True)
        except AttributeError:
            pass
    return data


def gather_volumes():
    percent_red_threshold = 92
    free_bytes_red_threshold = 2 * 2**30 # 2 GB
    volumes = OrderedDict()
    for p in psutil.disk_partitions():
        usage = psutil.disk_usage(p.mountpoint)

        usage_free_state = 'red' if usage.total >= free_bytes_red_threshold * 4 and usage.free < free_bytes_red_threshold else 'green'
        usage_percent_state = 'red' if usage.percent >= percent_red_threshold else 'green'

        v_data = OrderedDict()
        v_data['mountpoint'] = p.mountpoint
        v_data['device'] = p.device
        v_data['fstype'] = p.fstype
        v_data['opts'] = p.opts
        v_data['usage'] = OrderedDict()
        v_data['usage']['total_bytes'] = value(usage.total, unit='bytes')
        v_data['usage']['used_bytes'] = value(usage.used, unit='bytes')
        v_data['usage']['free_bytes'] = value(usage.free, unit='bytes', check_state=usage_free_state)
        v_data['usage']['percent'] = value(usage.percent, unit='percents', check_state=usage_percent_state)
        volumes[p.mountpoint] = v_data
    return volumes


def gather_memory():
    mem = psutil.virtual_memory()
    data = OrderedDict()
    data['total_bytes'] = value(mem.total, unit='bytes')
    data['available_bytes'] = value(mem.available, unit='bytes')
    return data


def gather_swap():
    sw = psutil.swap_memory()
    data = OrderedDict()
    data['total_bytes'] = value(sw.total, unit='bytes')
    data['used_bytes'] = value(sw.used, unit='bytes')
    data['free_bytes'] = value(sw.free, unit='bytes')
    data['percent'] = value(sw.percent, check_state='red' if sw.percent > 80 else 'green')
    return data
