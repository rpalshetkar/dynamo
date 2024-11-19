import re
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from icecream import ic

from utils.helpers import typed_list

_MODIFIERS = {
    'type': 'int|float|bool|str|date|time|datetime',
    'flag': 'req|uniq|key|ro|hide|secret|fuzzy|multi|list',
    'ops_num': 'rank|lines',
    'ops_str': 'has|end|start',
    'ops_type': 'le|ge|gt|lt|max|min|ne|eq',
    'ux_str': 'color|heatmap|xref|href',
    'lst_type': 'in|enum|range',
}

_MODIFIERS_PATTERN = re.compile(
    '|'.join(
        f'#(?P<k_{key}>{pattern})(?:=(?P<v_{key}>.*?))?(?=#|$)(?=#)?'
        for key, pattern in _MODIFIERS.items()
    )
)

_TYPE_MAP = {
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'date': datetime.date,
    'time': datetime.time,
    'dt': datetime,
}

_LIST_OPS = {
    'has': lambda v, c: v in c,
    'end': lambda v, c: c[-1] == v if c else False,
    'start': lambda v, c: c[0] == v if c else False,
    'in': lambda v, c: v in c,
    'enum': lambda v, c: v in c,
    'range': lambda v, c: v >= c[0] and v <= c[1],
}

_STR_OPS = {
    'has': lambda v, c: re.search(v, c),
    'end': lambda v, c: re.search(rf'{v}$', c),
    'start': lambda v, c: re.search(rf'^{v}', c),
}


def field_specs(
    value: Any,
) -> Optional[Dict[str, Any]]:
    results = {'type': str, 'flags': {}, 'spec': value}
    to_match = f'#{str(value).strip()}#'
    matches = [
        {k: v for k, v in match.groupdict().items() if v}
        for match in re.finditer(_MODIFIERS_PATTERN, to_match)
    ]
    for match in matches:
        if match.get('k_type'):
            val = match['k_type']
            results.update({'type': val})
        if match.get('v_type'):
            default = match['v_type']
            results.update({'default': default})
        if match.get('k_flag'):
            results['flags'].update({match['k_flag']: True})
        for key in _MODIFIERS.keys():
            if key in ['type', 'flag']:
                continue
            if not results.get(key):
                results[key] = {}
            k = match.get(f'k_{key}')
            v = match.get(f'v_{key}')
            if k:
                results[key].update({k: v})
    results = post_fix(results)
    return results


def post_fix(results: Dict[str, Any]) -> Dict[str, Any]:
    if results.get('flags'):
        results['flags'] = {k: True for k in results['flags']}
    flags = results.get('flags', {})
    dtype = results.get('type', 'str')
    itype: type = _TYPE_MAP.get(dtype, dtype)
    results['type'] = itype
    default = results.get('default')
    if flags.get('list'):
        results['type'] = List[itype]
        if default:
            results['default'] = typed_list(itype, default)
    dtypes = {
        'ops_num': int,
        'ops_str': str,
        'ops_type': itype,
        'lst_type': itype,
        'ux_str': itype,
    }
    for key in ['ops_num', 'ops_type', 'ops_str', 'lst_type']:
        if results.get(key):
            for k, v in results[key].items():
                results[key][k] = dtypes[key](v)
    results = {k: v for k, v in results.items() if v}
    return results


def convert_value(value: Any) -> Any:
    if isinstance(value, str):
        if ',' in value:
            return [convert_value(v) for v in value.split(',')]
        if value.isdigit() or value.isnumeric():
            return float(value)
        return value
    elif isinstance(value, dict):
        return {k: convert_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [convert_value(v) for v in value]
    return value


def infer_type(value: Any) -> Any:
    type_mapping = {
        str: (str, ...),
        int: (int, ...),
        float: (float, ...),
        list: (List[Any], ...),
        dict: (Dict[str, Any], ...),
        bool: (bool, ...),
    }
    if isinstance(value, str) and re.search(r',', value):
        types: set = {infer_type(v)[0] for v in value.split(',')}
        assert len(types) == 1, f'Only one type allowed, given {types}'
        return (List[types.pop()], ...)
    return type_mapping.get(type(value), (Optional[Any], None))


def comparators(value1: Any, value2: Any, operator: str) -> bool:
    operators: Dict[str, Callable[[Any, Any], bool]] = {
        'eq': lambda x, y: x == y,
        'ne': lambda x, y: x != y,
        'gt': lambda x, y: x > y,
        'lt': lambda x, y: x < y,
        'ge': lambda x, y: x >= y,
        'le': lambda x, y: x <= y,
    }

    if operator not in operators:
        raise ValueError(f'Invalid operator: {operator}')

    return operators[operator](value1, value2)


def operators(operation: str, value: Any, within: str | List[Any]) -> bool:
    ops = _LIST_OPS if isinstance(within, list) else _STR_OPS
    if (
        operation == 'range'
        and len(within) != 2  # noqa: PLR2004
        and not isinstance(within[0], type(value))
    ):
        raise ValueError('Range requires two values of the same type')

    if operation in ['has', 'start', 'end'] and isinstance(within, str):
        within = [within]

    if operation not in ops:
        raise ValueError(f'Invalid operation: {operation}')

    return ops[operation](value, within)
