from typing import Callable

import pandas as pd

from tests.fixtures.tdf import FAKE_DFS


def get_panda_type(get_df: str) -> pd.DataFrame:
    return FAKE_DFS[get_df]


def get_panda_type_callable(get_df: str) -> Callable:
    return get_panda_type
