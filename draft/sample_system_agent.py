#!/usr/bin/env python3

from datetime import datetime
import logging
import psutil
import requests
import socket
from time import time
import yaml


default_report_address = 'http://127.0.0.1:8090/report'

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        format='%(asctime)s %(name)-20s %(levelname)5s: %(message)s',
        level=logging.DEBUG)

    logger.debug('Collecting report data')

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

    ct = psutil.cpu_times()
    cs = psutil.cpu_stats()

    data = {
        'label': {
            'agent': 'sample_system',
            'host': socket.getfqdn(),
        },
        'date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'values': {
            'cpu': {
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
            },
            'volumes': volumes,
            'watchdog': {
                '__watchdog': {
                    'deadline': int(time() * 1000 + 60*1000),
                },
            },
        },
    }

    print(yaml.dump(data, width=200))

    report_address = default_report_address
    r = requests.post(report_address, json=data)
    r.raise_for_status()
    print(r.content)


if __name__ == '__main__':
    main()
