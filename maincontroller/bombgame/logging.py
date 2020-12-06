from logging import LogRecord, DEBUG, StreamHandler, Formatter, getLogger, INFO

NOISY_EVENTS = {"PingMessage", "TimerTick"}


def filter_noisy_log(record: LogRecord):
    if record.name == "EventSource" and len(record.args) >= 1 and type(record.args[0]).__name__ in NOISY_EVENTS:
        return False
    if record.name == "ModulePing" and record.levelno == DEBUG:
        return False
    return True


def init_logging(verbose=False):
    handler = StreamHandler()
    handler.addFilter(filter_noisy_log)
    handler.setFormatter(Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    getLogger().setLevel(DEBUG if verbose else INFO)
    getLogger().addHandler(handler)
    if verbose:
        getLogger("websockets").setLevel(INFO)
        getLogger("can").setLevel(INFO)
