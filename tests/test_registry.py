from pathlib import Path

import pytest
from icecream import ic

from xds.core.registry import Registry
from xds.utils.io import parser


@pytest.fixture
def registry():
    return Registry()


def test_registry(registry):
    reg = Registry()
    ic(reg)


def test_env():
    env = Registry.set_env('prod')
    ic(env)
