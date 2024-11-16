import logging
from pprint import pprint as pp
from typing import Any

logger = logging.getLogger(__name__)
logger.info('This is an info message.')

import os
import sys


class Logger:
    def __init__(self):
        self.configure_logger()

    def configure_logger(self):
        logger.remove()
        logging.basicConfig(level=logging.INFO)
        environment = os.getenv('env', 'development')
        self.set_logging_level(environment)

    def set_logging_level(self, environment: str) -> None:
        self._add_handler(sys.stderr, 'DEBUG')

    def _add_handler(self, stream, level: str) -> None:
        logger.add(
            stream,
            level=level,
            format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
        )

    def info(self, message: str) -> None:
        logger.info(message)

    def debug(self, message: str) -> None:
        logger.debug(message)

    def error(self, message: str) -> None:
        logger.error(message)

    def warn(self, message: str) -> None:
        logger.warning(message)

    def trace(self, message: str) -> None:
        logger.trace(message)

    def critical(self, message: str) -> None:
        logger.critical(message)


log = Logger()


def pprint_obj(obj: Any, indent: int = 2) -> None:
    for key, value in attr.asdict(obj).items():
        if isinstance(value, dict) and all(
            isinstance(v, dict) for v in value.values()
        ):
            ic(f"{'  ' * indent}{key}:")
            pprint_obj(value, indent + 1)
        else:
            ic(f"{'  ' * indent}{key}: {value}")
