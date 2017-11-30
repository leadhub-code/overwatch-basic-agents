import logging
from pathlib import Path
import yaml


logger = logging.getLogger(__name__)


class BaseConfiguration:

    def __init__(self, cfg_path):
        cfg_path = Path(cfg_path)
        base_path = cfg_path.parent
        data = yaml.safe_load(cfg_path.read_text())['overwatch_hub']
        self.report_url = data['report_url']
        self.report_token = data['report_token']
        self.report_tokens = set()
        self.log = _Log(data.get('log'), base_path)


class _HTTPInterface:

    def __init__(self, data):
        self.bind_host = 'localhost'
        self.bind_port = 8090
        if data:
            if data.get('bind_host'):
                self.bind_host = data['bind_host']
            if data.get('bind_port'):
                self.bind_port = int(data['bind_port'])


class _Log:

    def __init__(self, data, base_path):
        self.file_path = None
        if data:
            if data.get('file'):
                self.file_path = base_path / data['file']
