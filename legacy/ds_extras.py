from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pandas as pd

SourceTypeVar = Optional[Union[pd.DataFrame, str, bytes, Dict[str, Any]]]
StrLStrTypeVar = Optional[Union[str, List[str]]]


from itertools import islice
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from legacy.reader import Reader
from xds.utils import df_pytypes, icf, xlate, xlation_map


class DSExtra:
    def __init__(
        self,
        source: SourceTypeVar,
        keys: StrLStrTypeVar = None,
        children: Optional[Dict[str, Any]] = None,
    ):
        if keys is None:
            keys = []
        if children is None:
            children = {}
        self._to_df(source)

        if keys:
            if isinstance(keys, str):
                keys = keys.split(',')
        refs = self._xdf(list(keys or []), children)

        self.schema = refs['schema']
        self.df = refs['df']
        self.children = refs['children']

        self.xlations = xlation_map(self.df.columns)
        if self.xlations.get('var'):
            del self.xlations['var']

        self.kv = refs['kv']
        self.length = self.df.count()

    def kv_search(self, kw: Dict[str, Any]) -> pd.DataFrame:
        mask = pd.Series(True, index=self.df.index)
        for field, value in kw.items():
            if field in self.df.columns:
                if isinstance(value, (str)):
                    value = value.split(',')  # noqa: PLW2901
                if isinstance(value, (list, tuple)):
                    mask &= self.df[field].isin(value)
                else:
                    mask &= self.df[field] == value
        return self.df[mask]

    def _to_df(self, data: SourceTypeVar) -> None:
        xp, xdf = Reader().to_df(data)
        xlations = xlation_map(list(xdf.columns))
        xdf.columns = [xlations['var'].get(col) for col in xdf.columns]
        self.protocol: str = xp
        self._odf: pd.DataFrame = xdf

    def _xdf(
        self,
        keys: Optional[List[str]] = None,
        children: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if children is None:
            children = {}
        if keys is None:
            keys = []
        df: pd.DataFrame = self._odf.copy()
        self.keys = [xlate(var)[0] for var in keys]
        schema = df_pytypes(df)
        nested = [col for col, ptype in schema.items() if ptype == 'pd']
        for col, ptype in schema.items():
            if ptype == 'datex':
                df[col] = df[col].dt.strftime('%Y-%m-%d')

        if self.keys:
            unknown = set(self.keys) - set(df.columns)
            if unknown:
                raise ValueError(f'Unknown keys: {unknown}')
            df['key'] = df[self.keys].astype(str).agg('|'.join, axis=1)  # type: ignore  # noqa: PGH003
            df.set_index('key', inplace=True)  # type: ignore  # noqa: PGH003

        nodes: Dict[str, DSExtra] = {}

        for k, val in (children or {}).items():
            child = xlate(k)[0]
            if child not in nested:
                continue
            ccols = val['keys']
            if ccols:
                if isinstance(ccols, str):
                    ccols = ccols.split(',')
                ndf = pd.concat(df[child].tolist(), keys=df.index)
                ndf['pkey'] = ndf.index.get_level_values(0)
                ndf.reset_index(inplace=True, drop=True)
                ckeys: List[str] = ['pkey', *ccols]
                nodes[child] = DSExtra(ndf, keys=ckeys)

        for child in nested:
            df.drop(child, axis=1, inplace=True)

        return {
            'schema': df_pytypes(df),
            'df': df,
            'xlations': xlation_map(list(df.columns)),
            'children': nodes,
            'kv': df.to_dict(orient='index'),
        }

    @property
    def df_humanized(self) -> pd.DataFrame:
        hdf = self.df.copy()
        hdf.columns = [
            self.xlations['human'].get(col, col) for col in hdf.columns
        ]
        return hdf

    def _type(self, col: str) -> Any:
        try:
            return self.df[col].dtype
        except KeyError as err:
            raise ValueError(f'Key {col} not found in dataset') from err

    def __getitem__(self, key: str) -> Dict[str, Any]:
        return self.kv.get(key) or {}

    def __setitem__(self, key: str, value: Any) -> None:
        v: Dict[str, Any] = self.kv.get(key) or {}
        v |= value
        try:
            self.df.loc[key] = v
        except KeyError as err:
            raise ValueError(f'Key missing {key}') from err
        self.kv[key] = v

    def unique(self, cols: StrLStrTypeVar) -> List[str]:
        try:
            return list(
                self.df[cols].astype(str).agg('|'.join, axis=1).unique()
            )
        except KeyError as err:
            raise ValueError(
                f'One of the fields {cols} not found in dataset'
            ) from err

    def join(
        self,
        other: DSExtra,
        on: Optional[Union[str, List[str]]] = None,
        how: str = 'inner',
        lsuffix: str = 'a',
        rsuffix: str = 'b',
        lkeys: Optional[Union[str, List[str]]] = None,
        rkeys: Optional[Union[str, List[str]]] = None,
    ) -> DSExtra:
        def _prepare_df(
            df: pd.DataFrame, kys: Any, suffix: str
        ) -> pd.DataFrame:
            keys: List[str] = (
                kys.split(',')
                if isinstance(kys, str)
                else kys
                if isinstance(kys, list)
                else ['key']
            )
            dfk: pd.DataFrame = df.copy()
            dfk['key'] = df[keys].astype(str).agg('|'.join, axis=1)
            dfk.columns = [f'{col}-{suffix}' for col in dfk.columns]
            return dfk

        ldf = _prepare_df(self.df, lkeys, lsuffix)
        rdf = _prepare_df(self.df, rkeys, rsuffix)
        joined = ldf.join(rdf, on=on, how=how)  # type: ignore  # noqa: PGH003
        return DSExtra(joined, keys=self.keys)

    def __str__(self) -> str:
        kvs = dict(islice(self.kv.items(), 5))
        data: list[tuple[str, Any]] = [
            ('Protocol', self.protocol),
            ('Schema', icf(self.schema)),
            ('Keys', self.keys),
            ('Xlations', icf(self.xlations)),
            ('Columns', icf(self.df.columns)),
            ('Dataframe', self.df.head(10)),
            ('KVs Sample', icf(kvs)),
            ('Children', icf(self.children)),
        ]
        sep: str = '-' * 60 + '\n'
        return sep.join(f'{header} ->{content}\n' for header, content in data)
