from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TypeAlias
from urllib.parse import parse_qs, urlparse

import pandas as pd
from flatten_dict import flatten
from icecream import ic
from jinja2 import Environment, Template

from xds.utils.io import io_buffer

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


def typed_list(
    dtype: type, values: Optional[str | List[Any]]
) -> Optional[List[Any]]:
    if values is None:
        return None
    vals: List[Any] = values.split(',') if isinstance(values, str) else values
    return [dtype(v) for v in vals]


@lru_cache(maxsize=100)
def jinja_template(
    template: str, tdir: str = 'xds/catalogue/templates'
) -> Template:
    jtemplate = f'{template}.jinja2'
    tpath = f'{tdir}/{jtemplate}'
    return Template(io_buffer(file=tpath))


def jinja_render(
    template: Optional[str] = None, data: Optional[Any] = None, **kwargs: Any
) -> str:
    template = template or kwargs.get('template')
    template = jinja_template(template)
    return template.render(**kwargs)