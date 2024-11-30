import typing
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pytest
from icecream import ic

from xds.utils.dates import date_modifier


@pytest.mark.parametrize(
    ('base_date', 'test_cases'),
    [
        (
            '2024-11-10',
            [
                ('Today', 'T', '2024-11-10'),
                ('Next day', '1', '2024-11-11'),
                ('Prior day', '-1', '2024-11-09'),
                ('Prior 2 Bus Day', '-2B', '2024-11-08'),
                ('Month start', 'S', '2024-11-01'),
                ('Month end', 'ME', '2024-11-30'),
                ('Next Month', '1M', '2024-12-10'),
                ('Month End 3 Months', '3ME', '2025-02-28'),
                ('Quarter end', 'Q', '2024-12-31'),
                ('First Quarter', 'Q1', '2024-03-31'),
                ('Third Quarter', '3Q', '2024-09-30'),
                ('Year end', 'YE', '2024-12-31'),
            ],
        ),
        (
            '2024-02-29',
            [
                ('Today', 'T', '2024-02-29'),
                ('Next day', '1', '2024-03-01'),
                ('Prior day', '-1', '2024-02-28'),
                ('Prior 2 Bus Day', '-2B', '2024-02-27'),
                ('Month start', 'S', '2024-02-01'),
                ('Month end', 'ME', '2024-02-29'),
                ('Next Month', '1M', '2024-03-29'),
                ('Month End 3 Months', '3ME', '2024-05-31'),
                ('Year end', 'YE', '2024-12-31'),
            ],
        ),
    ],
)
def test_date_patterns(
    base_date: str, test_cases: List[Tuple[str, str, str]]
) -> None:
    for test_name, modifier, expected in test_cases:
        assert date_modifier(modifier, base_date) == expected, (
            f'Failed on {base_date} {test_name}:'
            f'Expected {expected}, Got {date_modifier(modifier, base_date)}'
        )
