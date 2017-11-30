#!/usr/bin/env python3

from datetime import datetime
import logging
import requests
import socket
from time import time
from time import monotonic as monotime
import yaml


default_report_address = 'http://127.0.0.1:8090/report'

watch_urls = [
    'https://www.messa.cz/cs/',
    'https://www.messa.cz/en/',
    'http://ip.messa.cz/',
]

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        format='%(asctime)s %(name)-20s %(levelname)5s: %(message)s',
        level=logging.DEBUG)

    logger.debug('Starting')

    rs = requests.session()

    for url in watch_urls:
        logger.info('Monitoring address %s', url)

        t0 = monotime()
        r = rs.get(url)
        td = monotime() - t0

        search_string = 'source'

        data = {
            'label': {
                'agent': 'sample_web',
                'host': socket.getfqdn(),
                'url': url,
            },
            'date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'values': {
                'url': url,
                'final_url': r.url,
                'response': {
                    'status_code': {
                        '__value': r.status_code,
                        '__check': {
                            'state': 'green' if r.status_code == 200 else 'red',
                        },
                    },
                    'content_length': len(r.content),
                    'duration': td,
                },
                'check_content': {
                    'search_string': search_string,
                    'present': {
                        '__value': search_string in r.text,
                        '__check': {
                            'state': 'green' if search_string in r.text else 'red',
                        },
                    },
                },
                'watchdog': {
                    '__watchdog': {
                        'deadline': int(time() * 1000 + 10000),
                    },
                },
            },
        }

        #print(yaml.dump(data, width=200))

        report_address = default_report_address
        auth_token = 'secret_report_token'
        r = rs.post(report_address, json=data, headers={'Authorization': 'token ' + auth_token})
        r.raise_for_status()
        print(r.content)


if __name__ == '__main__':
    main()
