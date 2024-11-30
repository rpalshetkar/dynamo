import typing
from typing import Any, Dict, List, Tuple

import pytest
from icecream import ic

from xds.utils.field import field_specs


@pytest.mark.parametrize(
    ('spec', 'expected'),
    [
        (
            'xref=DS#req#list',
            {
                'type': typing.List['DS'],  # noqa: F821
                'flags': {'req': True, 'list': True},
                'spec': 'xref=DS#req#list',
            },
        ),
        (
            'dict#req',
            {
                'flags': {'dict': True, 'req': True},
                'spec': 'dict#req',
                'type': typing.Dict[str, typing.Any],
            },
        ),
        (
            'int#key#in=17,18,19#all#any',
            {
                'flags': {'key': True, 'all': True, 'any': True},
                'enum_type': {'in': '17,18,19'},
                'enums': [17, 18, 19],
                'spec': 'int#key#in=17,18,19#all#any',
                'type': int,
            },
        ),
        (
            'req#ge=10#regex=abc.*#fuzzy#color=red#multi#list',
            {
                'flags': {
                    'fuzzy': True,
                    'multi': True,
                    'req': True,
                    'list': True,
                },
                'ops_type': {'ge': '10'},
                'spec': 'req#ge=10#regex=abc.*#fuzzy#color=red#multi#list',
                'type': typing.List[str],
                'ux_str': {'color': 'red'},
            },
        ),
        (
            'req#color=0x10#has=y#start=z#gt=rpx#fuzzy#key#uniq',
            {
                'flags': {
                    'fuzzy': True,
                    'key': True,
                    'req': True,
                    'uniq': True,
                },
                'ops_str': {'has': 'y', 'start': 'z'},
                'ops_type': {'gt': 'rpx'},
                'spec': 'req#color=0x10#has=y#start=z#gt=rpx#fuzzy#key#uniq',
                'type': str,
                'ux_str': {'color': '0x10'},
            },
        ),
        (
            'int=42#req#uniq#key#gt=45#lt=50',
            {
                'defval': '42',
                'flags': {'key': True, 'req': True, 'uniq': True},
                'ops_type': {'gt': 45, 'lt': 50},
                'spec': 'int=42#req#uniq#key#gt=45#lt=50',
                'type': int,
            },
        ),
    ],
)
def test_fld_spec(spec: str, expected: Dict[str, Any]) -> None:
    results = field_specs(spec)
    ic(spec, results)
    assert results == expected, (
        f'\nFailed on spec: {spec}\n'
        f'Expected: {expected}\n'
        f'Got:      {results}'
    )
