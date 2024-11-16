from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import re
from typing import Any, Optional
from icecream import ic

_DATE_MODIFIER = re.compile(r'([TBDWMQY])*([+-])*(\d+)*([DWMQY])*([SE])*')


def date_modifier(date_pattern: str, dt: Optional[str] = None) -> date:
    base = datetime.strptime(dt, '%Y-%m-%d').date() if dt else date.today()
    pattern = _DATE_MODIFIER.pattern
    match = re.match(pattern, date_pattern.upper())
    if not match:
        raise ValueError('Invalid date shortcut format')
    dt, sign, terms, units, adjust = match.groups()
    sign = sign or '+'
    mult = -1 if sign == '-' else 1
    units = units if units else dt or 'D'
    terms = int(terms or 0) * mult
    ic(date_pattern, base, sign, mult, terms, units, adjust)
    base = dated(base, units, terms)
    base = move_date(base, date_pattern, mult)
    return base.strftime('%Y-%m-%d')


def dated(base_date: date, period_unit: str, periods: int) -> date:
    match period_unit:
        case 'T':
            return base_date
        case 'D':
            return base_date + relativedelta(days=periods)
        case 'W':
            return base_date + relativedelta(weeks=periods)
        case 'M':
            return base_date + relativedelta(months=periods)
        case 'Q':
            base_date = base_date + relativedelta(months=periods * 3)
            qtr = (base_date.month - 1) // 3 + 1
            mth = qtr * 3
            day = 31 if mth in [3, 12] else 30
            return base_date.replace(month=mth, day=day)
        case 'Y':
            return base_date.replace(day=31, month=12)


def move_date(base_date: date, pattern: str, mult: int) -> date:
    if 'E' in pattern and 'S' in pattern:
        raise ValueError('Cannot specify both E and S')
    if 'S' in pattern:
        base_date = base_date.replace(day=1)
    elif 'E' in pattern:
        base_date = (base_date + relativedelta(months=1)).replace(
            day=1
        ) - relativedelta(days=1)
    if 'B' in pattern:
        while base_date.weekday() >= 5:  # noqa: PLR2004
            base_date += relativedelta(days=mult * 1)
    return base_date
