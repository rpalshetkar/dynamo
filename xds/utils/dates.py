import re
from datetime import date, datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from icecream import ic

_DATE_MODIFIER = re.compile(r'([TBDWMQY])*([+-])*(\d+)*([DWMQY])*([SE])*')


def date_modifier(date_pattern: str, dt: Optional[str] = None) -> str:
    base_date = datetime.strptime(dt, '%Y-%m-%d').date() if dt else date.today()
    match = re.match(_DATE_MODIFIER, date_pattern.upper())
    if not match:
        raise ValueError('Invalid date shortcut format')

    period_type, sign, terms, units, adjust = match.groups()
    sign = sign or '+'
    multiplier = -1 if sign == '-' else 1
    units = units if units else period_type or 'D'

    ic(date_pattern, base_date, sign, multiplier, terms, units, adjust)
    result_date = dated(base_date, units, terms, multiplier)
    result_date = move_date(result_date, date_pattern, multiplier)
    return result_date.strftime('%Y-%m-%d')


def dated(
    base_date: date, period_unit: str, terms: int, multiplier: int
) -> date:
    if period_unit == 'Y':
        return base_date.replace(day=31, month=12)
    if period_unit in ('Q'):
        qtr = (base_date.month - 1) // 3 + 1 if not terms else int(terms)
        year = base_date.year
        quarter_end_dates = [
            date(year, 3, 31),
            date(year, 6, 30),
            date(year, 9, 30),
            date(year, 12, 31),
        ]
        return quarter_end_dates[qtr - 1]
    periods = int(terms or 0) * multiplier
    if period_unit == 'T':
        return base_date
    if period_unit == 'D':
        return base_date + relativedelta(days=periods)
    if period_unit == 'W':
        return base_date + relativedelta(weeks=periods)
    if period_unit == 'M':
        return base_date + relativedelta(months=periods)
    raise ValueError('Invalid period unit')


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
