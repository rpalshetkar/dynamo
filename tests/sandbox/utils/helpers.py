from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TypeAlias
from urllib.parse import parse_qs, urlparse

import pandas as pd
import yaml
from flatten_dict import flatten
from icecream import ic

from tests.sandbox.utils.io import (
    icf,
    io_stream,
    parse_content,
    read_json,
    read_yaml,
)

_NO_XLATIONS_SPECIALS = ['LOB', 'PL', 'PI']


XlationMap: TypeAlias = Dict[str, Dict[str, str]]
ic.configureOutput(prefix='DEBUG:', includeContext=True)


class SingletonMeta(type):
    _instances: ClassVar[Dict[str, Any]] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


def df_pytypes(df: pd.DataFrame) -> Dict[str, str]:
    overrides = {
        'datetime.date': 'date',
        'pandas.core.frame.DataFrame': 'pd',
    }
    types = {
        col: str(df[col].apply(type).unique()[0]).split("'")[1]
        for col in df.columns
    }
    for col, ptype in types.items():
        if ptype in overrides:
            types[col] = overrides[ptype]
    return types


def xlate(val: str) -> Tuple[str, str]:
    var = re.sub(r'\W+', '_', val).lower()
    arr: List[str] = [
        i.upper() if i.upper() in _NO_XLATIONS_SPECIALS else i.title()
        for i in var.split('_')
    ]
    eng = ' '.join(arr)
    return var, eng


def xlation_map(vals: List[str]) -> Dict[str, Dict[str, str]]:
    xlations: Dict[str, Dict[str, str]] = {
        'human': {},
        'var': {},
    }
    for val in vals:
        var, eng = xlate(val)
        xlations['human'][var] = eng
        xlations['var'][eng] = var
        xlations['var'][val] = var
    return xlations


def is_pivot(df: pd.DataFrame) -> bool:
    index_pivoted = isinstance(df.index, pd.MultiIndex) or (
        df.index.name is not None and df.index.name != 'key'
    )
    column_pivoted = (
        isinstance(df.columns, pd.MultiIndex) or len(df.columns.names) > 1
    )
    return index_pivoted or column_pivoted


def parse_url(url: str) -> Dict[str, Any]:
    parsed_url = urlparse(url)
    qs = parse_qs(parsed_url.query)

    def parse_nested_qs(qs: Dict[str, List[str]]) -> Dict[str, Any]:
        result = {}
        for k, v in qs.items():
            keys = k.split('.')
            d = result
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = v[0].split(',') if ',' in v[0] else v[0]
        return result

    return parse_nested_qs(qs)


def io_dict(**kwargs: Any) -> Dict[str, Any]:
    if {'file', 'content', 'url'} <= kwargs.keys():
        raise ValueError(
            "Only one of 'file', 'content', or 'url' should be provided"
        )

    if 'file' in kwargs:
        file_path = str(kwargs['file'])
        content = io_stream(file=file_path)
        if file_path.lower().endswith(('.yaml', '.yml')):
            data = read_yaml(content)
        elif file_path.lower().endswith('.json'):
            data = read_json(content)
        else:
            raise ValueError(f'Unsupported file format: {file_path}')

    elif 'content' in kwargs:
        data = parse_content(kwargs['content'])

    elif 'url' in kwargs:
        data = parse_content(parse_url(kwargs['url']))

    else:
        icf(f'Creating data from kwargs: {kwargs}')
        data = kwargs

    if data is None:
        raise ValueError('No data returned')

    return data


def flat(data):
    if isinstance(data, list):
        return flatten(
            {
                k: flat(v) if isinstance(v, (list, dict)) else v
                for item in data
                for k, v in item.items()
            }
        )
    elif isinstance(data, dict):
        return flatten(
            {
                k: flat(v) if isinstance(v, (list, dict)) else v
                for k, v in data.items()
            }
        )
    return data
