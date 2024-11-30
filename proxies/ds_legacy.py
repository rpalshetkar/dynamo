import pandas as pd
from icecream import ic

from tests.df_mocks_fixtures import FAKE_DFS


class DSLegacy:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.df = self._mock_df(**kwargs)
        self.exports = [
            'df',
            'increment',
            'filter',
            'stats',
            'create',
        ]

    @classmethod
    def create(cls, **kwargs):
        ic(f'Calling proxy Create with args: {kwargs}')
        return cls(**kwargs)

    def filter(self, condition):
        return self.df[self.df.apply(condition, axis=1)]

    def stats(self):
        return {
            'rows': len(self.df),
            'columns': self.df.columns.tolist(),
            'head': self.df.head(10),
        }

    def save(self, **kwargs):
        ic(f'Saving DF and adding {kwargs}')
        return self.df

    def delete(self, **kwargs):
        ic(f'Deleting DF and adding {kwargs}')
        return self.df

    def increment(self):
        self.df['processed'] = self.df['storypoint'] * 2
        return self.df

    def _mock_df(self, **kwargs) -> pd.DataFrame:
        ns = kwargs.get('ns', None)
        if ns is None:
            raise ValueError('Namespace for DS not provided')
        ns_df = FAKE_DFS.get(ns)
        if ns_df is None:
            raise ValueError(f'No DS could be found for {ns_df}')
        df = ns_df(kwargs.get('rows', 50))
        return df
