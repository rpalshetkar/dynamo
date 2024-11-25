import os
import sys
from pprint import pp
from typing import Any, Optional

from icecream import ic
from loguru import logger
from pydantic import BaseModel

ic.configureOutput(prefix='DEBUG:', includeContext=True)


class AppLogger(BaseModel):
    level: str = 'DEBUG'
    format: str = '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}'
    stream: Any = None

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.stream: Any = sys.stdout
        self.configure_logger()

    def configure_logger(self) -> None:
        logger.remove()
        environment = os.getenv('env', 'development')
        self.set_logging_level(environment)

    def set_logging_level(self, environment: str) -> None:
        level = self.level if environment == 'production' else 'DEBUG'
        self._add_handler(self.stream, level)

    def _add_handler(self, stream: Any, level: str) -> None:
        logger.add(
            self.stream,
            level=level,
            format=self.format,
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
