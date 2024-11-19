import re
from datetime import date, datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from icecream import ic

_DATE_MODIFIER = re.compile(r'([TBDWMQY])*([+-])*(\d+)*([DWMQY])*([SE])*')


def date_modifier(date_pattern: str, dt: Optional[str] = None) -> str:
    """Convert date pattern to formatted date string.

    Args:
        date_pattern: Pattern string (e.g. 'T', 'D+1', 'M-3E')
        dt: Optional base date string in YYYY-MM-DD format

    Returns:
        Formatted date string in YYYY-MM-DD format
    """
    base_date = datetime.strptime(dt, '%Y-%m-%d').date() if dt else date.today()
    match = re.match(_DATE_MODIFIER, date_pattern.upper())
    if not match:
        raise ValueError('Invalid date shortcut format')

    period_type, sign, terms, units, adjust = match.groups()
    sign = sign or '+'
    multiplier = -1 if sign == '-' else 1
    units = units if units else period_type or 'D'
    periods = int(terms or 0) * multiplier

    ic(date_pattern, base_date, sign, multiplier, periods, units, adjust)
    result_date = dated(base_date, units, periods)
    result_date = move_date(result_date, date_pattern, multiplier)
    return result_date.strftime('%Y-%m-%d')


def dated(base_date: date, period_unit: str, periods: int) -> date:  # noqa: PLR0911
    if period_unit == 'T':
        return base_date
    elif period_unit == 'D':
        return base_date + relativedelta(days=periods)
    elif period_unit == 'W':
        return base_date + relativedelta(weeks=periods)
    elif period_unit == 'M':
        return base_date + relativedelta(months=periods)
    elif period_unit in ('P', 'Q'):
        if periods < 1 or periods > 4:  # noqa: PLR2004
            raise ValueError('Periods for quarters must be between 1 and 4')
        year = base_date.year
        if base_date.month > periods * 3:
            raise ValueError('Cannot cross over to the next year')
        if period_unit == 'P':
            quarter_end_dates = [
                date(year, 3, 31),  # Q1
                date(year, 6, 30),  # Q2
                date(year, 9, 30),  # Q3
                date(year, 12, 31),  # Q4
            ]
            return quarter_end_dates[periods - 1]
        else:
            return date(year, periods * 3, 1) + relativedelta(
                months=1, days=-1
            )  # End of the corresponding quarter
    elif period_unit == 'Y':
        return base_date.replace(day=31, month=12)
    else:
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
