import re
from datetime import datetime
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

from icecream import ic

_MODIFIERS = {
    'type_kd': 'int|float|bool|str|listi|listf|listb|lists|kw|date|time|dt|email|time|href',
    'op_kv': 'le|ge|gt|lt|ne|eq|max|min',
    'query_kv': 'has|end|start|in|enum|range',
    'render_kv': 'color|heatmap',
    'ux_kd': 'multi|lines|form|order|ex',
    'xref_kv': 'xref',
    'bool_k': 'req|uniq|key|ro|hide|secret|fuzzy',
}

_MODIFIERS_PATTERN = re.compile(
    '|'.join(
        f'#(?P<k_{key}>{pattern})(?:=(?P<v_k_{key}>.*?))?(?=#|$)(?=#)?'
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
    'listi': List[int],
    'listf': List[float],
    'listb': List[bool],
    'lists': List[str],
    'kw': Dict[str, Any],
}


def field_spec(
    input_string: str,
) -> Optional[List]:
    matches = re.finditer(_MODIFIERS_PATTERN, f'#{input_string}#')
    result = {}
    for match in matches:
        matched = {
            key: value
            for key, value in match.groupdict().items()
            if value is not None
        }
        key = next((k for k in matched.keys() if k.startswith('k_')), None)
        real_key = matched.get(key, None)
        if not real_key:
            continue
        value = matched.get(f'v_{key}')
        if key.endswith('_kv') and not value:
            raise ValueError(f'{real_key} must have a value')
        if key.find('_bool') > -1:
            value = True
        result.update({real_key: value})

    types = [
        (k, _TYPE_MAP[k], result.get(k))
        for k in result.keys()
        if k in _TYPE_MAP
    ]
    if len(types) > 1:
        raise ValueError(f'Only one type allowed, given {types.keys()}')
    if not types:
        types = [('str', str, None)]
    dtype, rtype, default = types[0]
    result['type'] = rtype
    if default:
        if dtype.startswith('list'):
            xtype = rtype.__args__[0]
            result['default'] = [xtype(i) for i in default.split(',')]
        else:
            result['default'] = rtype(default)
    if result.get('in'):
        result['in'] = [rtype(i) for i in result['in'].split(',')]
    return result


def cmp_value(value1: Any, value2: Any, operator: str) -> bool:
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


def query_operation(operation: str, value: Any, collection: List[Any]) -> bool:
    operations = {
        'has': lambda v, c: v in c,
        'end': lambda v, c: c[-1] == v if c else False,
        'start': lambda v, c: c[0] == v if c else False,
        'in': lambda v, c: v in c,
        'enum': lambda v, c: v in c,
        'range': lambda v, c: all(x >= v[0] and x <= v[1] for x in c),
    }

    if operation not in operations:
        raise ValueError(f'Invalid operation: {operation}')

    return operations[operation](value, collection)
