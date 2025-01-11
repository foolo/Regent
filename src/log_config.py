import logging

logger = logging.Logger('app')

formatter = logging.Formatter(
    style='{',
    fmt='{levelname:8} {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def set_log_level(level: int):
	logger.setLevel(level)
