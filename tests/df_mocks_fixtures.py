import random
from datetime import date, datetime, timedelta
from random import choice, randint
from typing import Any, Dict, List

import pandas as pd
from faker import Faker

RSEED: int = 72
Faker.seed(RSEED)
random.seed(RSEED)
FAKE: Faker = Faker()


def fake_bow_df(num_rows: int = 100) -> pd.DataFrame:
    groups: List[str] = ['DNS', 'EES', 'DMO', 'RISK', 'MDA']
    cars: List[str] = ['SOOR', 'PRICING', 'RISK', 'DMO', 'EES']
    leads: List[str] = ['AN', 'BZ', 'RC', 'KL', 'KA']
    trains: List[str] = groups
    stakeholders: List[str] = [FAKE.name() for _ in range(20)]
    columns: List[str] = [
        'Train',
        'Car',
        'Headline',
        'Group',
        'Lead',
        'Effort',
        'Errors',
        'Stakeholder',
        'Assignee',
        'Start Date',
        'End Date',
        'Subtasks',
        'Approvals',
        'Reviews',
    ]
    workflow: List[str] = ['Step', 'Who', 'State', 'Comments', 'Is Waiting']

    data: List[Any] = []
    for _ in range(num_rows):
        headline = ' '.join(FAKE.words(randint(2, 5))).title()
        group = choice(groups)
        lead = choice(leads)
        train = choice(trains)
        car = choice(cars)
        effort = randint(1, 30)
        errors = randint(0, 100)
        stakeholder = choice(stakeholders)
        start_date = FAKE.date_between(date(2023, 1, 1), date(2023, 12, 31))
        end_date = start_date + timedelta(days=effort)
        assignee = f'{lead}-DIR{random.randint(1, 5)}'
        sub_df = _subtasks(leads, start_date, end_date, effort)
        approvals: List[Any] = [
            [1, 'Lead', 'Waiting', 'Entry Approval', True],
            [2, 'Accountable', 'Waiting', 'Management Approval', False],
            [3, 'SLT', 'Waiting', 'SLT Approval', False],
        ]
        appr_df = pd.DataFrame(approvals, columns=workflow)
        rv_df = _reviews('xBOW', 'Errors', lead, assignee)
        data.append(
            [
                train,
                car,
                headline,
                group,
                lead,
                effort,
                errors,
                stakeholder,
                assignee,
                start_date,
                end_date,
                sub_df,
                appr_df,
                rv_df,
            ]
        )

    return pd.DataFrame(data, columns=columns)


def _subtasks(
    leads: list[str],
    start_date: date,
    end_date: date,
    effort: int,
) -> pd.DataFrame:
    task_columns: list[str] = [
        'Headline',
        'Group',
        'Start Date',
        'End Date',
        'Effort',
        'Assignee',
    ]
    subtasks: List[List[str | date | int]] = []

    num_subtasks: int = randint(5, 6)
    for _ in range(num_subtasks):
        subtask_headline: str = ' '.join(FAKE.words(randint(2, 5))).title()
        subtask_group: str = choice(leads)
        subtask_start_date: date = FAKE.date_between(start_date, end_date)
        subtask_effort: int = randint(1, effort)
        subtask_end_date: date = subtask_start_date + timedelta(
            days=subtask_effort
        )
        task_lead: str = choice(leads)
        subtask_assignee: str = f'{task_lead}-DIR{random.randint(1, 5)}'
        subtasks.append(
            [
                subtask_headline,
                subtask_group,
                subtask_start_date,
                subtask_end_date,
                subtask_effort,
                subtask_assignee,
            ]
        )

    sub_df: pd.DataFrame = pd.DataFrame(subtasks, columns=task_columns)
    return sub_df


def _reviews(
    metrics: str, measure: str, lead: str, assignee: str
) -> pd.DataFrame:
    start_date = datetime(2024, 3, 31)
    end_date = datetime.now()
    review_dates: List[Any] = []
    current_date = start_date
    while current_date <= end_date:
        review_dates.append(current_date)
        current_date += timedelta(days=7)

    err_msgs = {
        'xBOW': [
            'Status not updated',
            'Headline standards not followed',
            'Project completed but status not updated',
            'Effort remaining is not proportional',
            'Jira not updating latest story count',
            'JIRA reference not found',
        ],
        'SPAM': [
            'Emails not going via DNS',
            'Email Spam not reduced',
        ],
    }

    data: List[Any] = []
    for review_date in review_dates:
        num_errors = random.randint(1, 4)
        errors = random.sample(err_msgs.get(metrics, []), num_errors)
        error_string = '#'.join(errors)
        error_count = sum(random.randint(5, 10) for _ in range(len(errors)))
        data.append(
            {
                'Date': review_date.strftime('%Y-%m-%d'),
                'Metric': metrics,
                'Measure': measure,
                'Lead': lead,
                'Assignee': assignee,
                'Notes': error_string,
                'Value': error_count,
            }
        )

    return pd.DataFrame(data)


def fake_ait_df(num_rows: int = 100) -> pd.DataFrame:
    countries = ['China', 'Japan', 'Korea', 'India', 'Singapore']
    desks = ['RATES', 'LCT', 'CREDIT', 'TSY']
    currencies = ['USD', 'INR', 'KRW', 'CNY', 'HKD', 'SGD']
    capabilities_l1 = ['Trading', 'Operations', 'Finance']
    capabilities_l2 = {
        'Trading': [
            'Trade Capture',
            'Trading Venues',
            'Risk Management',
            'Electronic Trading',
        ],
        'Operations': ['Settlement', 'Documentation'],
        'Finance': ['Subledger', 'General Ledger'],
    }
    asset_classes = ['CASH', 'FX', 'RATES', 'CMDY']
    products = {
        'CASH': ['CASH', 'MM', 'DEPOSITS', 'LOANS', 'CP'],
        'FX': ['SPOT', 'FXFWD', 'FXSWP', 'NDF', 'NDS', 'FXO', 'EXOTICS'],
        'RATES': [
            'BONDS',
            'REPOS',
            'IRS',
            'CCS',
            'CAPFLR',
            'SWOPT',
            'NRXCCY',
            'TRS',
            'BONDFWD',
            'TBS',
            'SN',
            'FUTURES',
        ],
        'CMDY': [
            'FNO',
            'SWAPS',
            'OPTIONS',
            'FWD',
        ],
    }
    data: List[Dict[str, Any]] = []
    for _ in range(num_rows):
        capability_l1 = random.choice(capabilities_l1)
        asset_class = random.choice(asset_classes)
        row: Dict[str, Any] = {
            'Country': random.choice(countries),
            'Desk': random.choice(desks),
            'Currency': random.choice(currencies),
            'Capability L1': capability_l1,
            'Capability L2': random.choice(capabilities_l2[capability_l1]),
            'Asset Class': asset_class,
            'Product': random.choice(products[asset_class]),
            'Application': f'AIT{random.randint(1, 25)}',
            'Score': random.randint(-100, 500),
        }
        data.append(row)
    return pd.DataFrame(data)


def fake_funding_df(num_rows=100, seed=42) -> pd.DataFrame:
    bis = ['BAU', 'INIT', 'BAU->INIT', 'INIT->BAU']
    lobs: list[str] = ['RATES', 'LCT']
    programs: Dict[str, list[str]] = {
        'RATES': ['ERATES', 'RPRC', 'ROOC'],
        'LCT': ['ELCT', 'LREG', 'LCLR', 'LPRC', 'LOOC'],
    }
    apps: Dict[str, list[str]] = {
        'RATES': ['QZLR', 'RRTW', 'MISTY', 'YB'],
        'LCT': ['BIB', 'CCIL', 'QZLCT', 'CFETS', 'LRTW'],
    }
    externals: list[str] = ['LREG', 'LCLR']
    givers = ['FMTG', 'FMTA']
    receivers = ['FMTG', 'FMTA', 'PTA', 'PTG', 'EIT', 'GTS', 'RFIT', 'OPS']
    pi_cars = ['DNS', 'RISK', 'MDA', 'SOOR', 'PRICING', 'OOC']
    data = {
        'LOB': [],
        'Base Init': [],
        'Allocation': [],
        'Program': [],
        'Giver': [],
        'Receiver': [],
        'PI Car': [],
        'Outcome': [],
        'Funding': [],
    }
    for lob in lobs:
        for bi in bis:
            bi_split: str = 'BAU' if bi.startswith('BAU') else 'INIT'
            pas: List[str] = apps[lob] if bi_split == 'BAU' else programs[lob]
            for pa in pas:
                rows = min(4, num_rows // len(pas))
                for _ in range(rows):
                    data['LOB'].append(lob)
                    data['Base Init'].append(bi_split)
                    data['Allocation'].append(bi)
                    data['Program'].append(pa)
                    data['Giver'].append(random.choice(givers))
                    receiver = random.choice(receivers)
                    if pa not in externals or bi_split != 'INIT':
                        receiver = 'FMTA'
                    car = (
                        random.choice(pi_cars)
                        if receiver == 'FMTA'
                        else f'{receiver}(EXTERNAL)'
                    )
                    data['Receiver'].append(receiver)
                    data['PI Car'].append(car)
                    data['Outcome'].append(
                        f'{pa} - {FAKE.sentence(nb_words=5).title()}'
                    )
                    data['Funding'].append(random.randint(10000, 50000))

    df = pd.DataFrame(data)
    return df


def fake_comp_df(num_employees=100, seed=42):
    ratings = ['E', 'M', 'DNM']
    titles = ['VP', 'DIR', 'AVP', 'OFFICER']
    bands = ['B4', 'B5', 'B6']
    groups = ['DMO', 'ENG', 'MGMT']
    fm_names = {FAKE.name() for _ in range(10)}
    mgr_names = {FAKE.name() for _ in range(6)}

    employees = []

    for i in range(num_employees):
        name = FAKE.name()
        employee_id = i + 1
        rating = random.choice(ratings)
        title = random.choice(titles)
        band = random.choice(bands)
        salary = random.randint(20000, 200000)
        ic = random.randint(2000, 200000)
        group = random.choice(groups)
        fm_name = random.choice(list(fm_names))
        fm_id = random.randint(1, len(fm_names))
        mgr_name = random.choice(list(mgr_names))
        mgr_id = random.randint(1, len(mgr_names))

        salary_pool = salary * random.uniform(0.05, 0.06)
        ic_pool = ic * random.uniform(0.05, 0.06)

        if rating == 'E':
            salary_increment = salary * 0.07
            ic_increment = ic * 0.07
            if random.random() < 0.1:  # noqa: PLR2004
                salary_increment = salary * 0.15
                ic_increment = ic * 0.10
        elif rating == 'M':
            salary_increment = salary * 0.03
            ic_increment = ic * 0.03
        else:
            salary_increment = 0
            ic_increment = 0

        employees.append(
            {
                'Name': name,
                'Id': employee_id,
                'Rating': rating,
                'Title': title,
                'Band': band,
                'Salary': salary,
                'Ic': ic,
                'Mgr Id': mgr_id,
                'Mgr': mgr_name,
                'Fnc Id': fm_id,
                'Fnc Mgr': fm_name,
                'Group': group,
                'Salary Pool': salary_pool,
                'Ic Pool': ic_pool,
                'Salary Incr': salary_increment,
                'Ic Incr': ic_increment,
            }
        )

    df = pd.DataFrame(employees)
    return df


FAKE_DFS = {
    'xbow': fake_bow_df,
    'xait': fake_ait_df,
    'xfunding': fake_funding_df,
    'xcomp': fake_comp_df,
}
