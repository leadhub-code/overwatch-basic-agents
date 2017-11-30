import logging
from pathlib import Path
import yaml


logger = logging.getLogger(__name__)


class BaseConfiguration:

    top_level_key = None

    def __init__(self, cfg_path):
        cfg_path = Path(cfg_path)
        base_path = cfg_path.parent
        data = yaml.safe_load(cfg_path.read_text())
        assert self.top_level_key
        cfg_data = data[self.top_level_key]
        self._load(cfg_data, base_path)

    def _load(self, data, base_path):
        self.report_url = data['report_url']
        self.report_token = data['report_token']
        self.log = _Log(data.get('log'), base_path)
        self.sleep_interval = _float_or_none(data.get('sleep_interval'))
        self.watchdog_interval = _float_or_none(data.get('watchdog_interval'))


def _float_or_none(v):
    try:
        return float(v) if v else None
    except Exception as e:
        raise Exception('Cannot convert value {!r} to float or None: {!r}'.format(v, e)) from None


class _Log:

    def __init__(self, data, base_path):
        self.file_path = None
        if data:
            if data.get('file'):
                self.file_path = base_path / data['file']
