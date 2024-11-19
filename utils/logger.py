import os
import sys
from pprint import pp
from typing import Any, Optional

from icecream import ic
from loguru import logger
from pydantic import BaseModel

ic.configureOutput(prefix='DEBUG:', includeContext=True)


class AppLogger:
    def __init__(self):
        self.configure_logger()

    def configure_logger(self):
        logger.remove()
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


log = AppLogger()
