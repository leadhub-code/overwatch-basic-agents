import logging
from pathlib import Path
from pytest import fixture
import sys


logging.basicConfig(
    format='~ %(asctime)s %(name)-20s %(levelname)5s: %(message)s',
    stream=sys.stdout,
    level=logging.DEBUG)


@fixture
def temp_dir(tmpdir):
    # use stdlib Path instead of py.path
    return Path(str(tmpdir))


@fixture
def project_dir():
    d = Path(__file__).parent.parent.resolve()
    assert (d / 'setup.py').is_file()
    return d
