import io
import re
from typing import Any, Callable, Dict, Type

import number_parser
import pandas as pd

DataFrameReader = Callable[[Any], pd.DataFrame]
DictReader = Callable[[Dict[str, Any]], pd.DataFrame]


class Reader:
    def __init__(self, **kwargs: Any) -> None:
        self.readers: Dict[str, DataFrameReader] = {  # ignore
            'pd': lambda x: x.copy(),
            'dict': lambda x: pd.DataFrame.from_dict(x, orient='columns'),  # type: ignore  # noqa: PGH003
            'str': lambda x: pd.read_csv(io.StringIO(x)),  # type: ignore  # noqa: PGH003
            'bytes': lambda x: pd.read_csv(io.BytesIO(x)),  # type: ignore  # noqa: PGH003
            'csv': lambda x: pd.read_csv(x, **kwargs),  # type: ignore  # noqa: PGH003
            'sheet': lambda x: pd.read_excel(x, **kwargs),  # type: ignore  # noqa: PGH003
            'json': lambda x: pd.read_json(x, **kwargs),  # type: ignore  # noqa: PGH003
            'xls': lambda x: pd.read_excel(x, **kwargs),  # type: ignore  # noqa: PGH003
            'numbers': lambda x: number_parser.parse_number(x),  # type: ignore  # noqa: PGH003
            # "qzt": lambda x: self._qz_to_df(x, **kwargs),
            # "txf": lambda x: self._txf_to_df(x, **kwargs),
            # "http": lambda x: self._txf_to_df(x, **kwargs),
        }
        self.dtypes: Dict[Any, str] = {
            pd.DataFrame: 'pd',
            dict: 'dict',
            str: 'str',
            bytes: 'bytes',
        }

    def __ios_parser(
        self,
    ) -> None:
        pass

    def _infer_parser(
        self, data: Any
    ) -> tuple[str, Callable[[Any], pd.DataFrame]]:
        for dtype, parser in self.dtypes.items():
            if isinstance(data, dtype):
                return parser, self.readers[parser]

        if isinstance(data, str):
            uri, _ = data.split('://', 1) if '://' in data else ('', data)
            if uri in self.readers:
                return uri, self.readers[uri]

            pattern = r'\.([^.]+)$'
            match = re.search(pattern, data)
            if match and match.group(1) in self.readers:
                return match.group(1), self.readers[match.group(1)]

        raise ValueError(f'Unsupported data type: {type(data)}')

    def to_df(self, data: Any) -> tuple[str, pd.DataFrame]:
        parser, reader = self._infer_parser(data)
        return parser, reader(data)
