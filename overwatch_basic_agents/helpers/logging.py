import logging


log_format = '%(asctime)s %(name)-30s %(levelname)5s: %(message)s'


def setup_logging(verbosity=0):
    from logging import DEBUG, INFO, ERROR, Formatter, StreamHandler, getLogger

    if not verbosity:
        console_level = ERROR
    elif verbosity == 1:
        console_level = INFO
    else:
        console_level = DEBUG

    getLogger().setLevel(DEBUG)

    h = StreamHandler()
    h.setLevel(console_level)
    h.setFormatter(Formatter(log_format))
    getLogger().addHandler(h)


def setup_log_file(log_file_path):
    from logging import DEBUG, Formatter, getLogger
    from logging.handlers import WatchedFileHandler
    if not log_file_path:
        return
    h = WatchedFileHandler(str(log_file_path))
    h.setLevel(DEBUG)
    h.setFormatter(Formatter(log_format))
    getLogger().addHandler(h)
