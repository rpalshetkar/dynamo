import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from icecream import ic


def icf(var: Any, header: Optional[str] = None) -> None:
    if header:
        ic(header)
    ic(var)


def io_stream(**kwargs: Dict[str, Any]) -> Optional[str]:
    path = io_path(**kwargs)
    try:
        with open(path, 'r', encoding='utf-8') as fp:
            return fp.read()
    except Exception as e:
        print(f'Error: An I/O reading the file {path}: {e}')
    return None


def io_path(**kwargs: Dict[str, Any]) -> Path:
    file: str = kwargs.get('file')
    dir: str = kwargs.get('dir')
    cpath = Path(file)
    if cpath.exists():
        return cpath
    if dir:
        fpath = Path(dir, file)
        if fpath.exists():
            return fpath
    raise FileNotFoundError(f'File Not found for {dir}/{file}')


def read_yaml(contents: Optional[str]) -> Optional[Any]:
    if contents is None:
        return None
    try:
        return yaml.safe_load(contents)
    except yaml.YAMLError as e:
        ic(f'Error parsing YAML: {e}')
    except Exception as e:
        ic(f'Unexpected error reading YAML: {e}')
    return None


def read_json(contents: Optional[str]) -> Optional[Any]:
    if contents is None:
        return None
    try:
        return json.loads(contents)
    except (json.JSONDecodeError, Exception) as e:
        raise ValueError(f'Failed to parse JSON: {e}') from e


def parse_content(content: str) -> Optional[Any]:
    try:
        return read_yaml(content)
    except yaml.YAMLError:
        return read_json(content)
