import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import yaml
from icecream import ic

from xds.utils.logger import log


def parser(
    input: Optional[str] = None, **kwargs: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if isinstance(input, dict):
        return input

    path = input or kwargs.get('path')
    buffer: str | None = kwargs.get('buffer')
    url: str | None = kwargs.get('url')
    if [path, buffer, url].count(None) != 2:  # noqa: PLR2004
        raise ValueError('Only on off path/buffer/url must be provided')

    if url:
        return _parse_url(url)

    if buffer:
        return _parse_raw(buffer)

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'FILE/DIR not found: {path}')

    if path.is_file():
        log.info(f'Reading contents from {path}')
        mime = 'yaml' if path.suffix == '.yaml' else 'json'
        return _parse_raw(io_buffer(file=path), mime=mime)

    elif path.is_dir():
        log.info(f'Processing directory: {path}, Results in contents field')
        results = {'by': 'dir', 'dir': path.name, 'contents': []}
        for file in path.iterdir():
            if file.is_file():
                f = str(file)
                res = parser(f)
                if res:
                    res['path'] = f
                    results['contents'].append(res)
        return results


def _parse_raw(buffer: str, mime: str | None = None) -> Dict[str, Any]:
    if not buffer:
        log.error('No buffer to parse')
        return {}

    def try_parse(parser, content, mime):
        try:
            data = parser(content)
            return data
        except Exception as e:
            log.error(f'Failed to parse as {mime}: {e}')

    mimes = [mime] if mime else ['yaml', 'json']
    for mtype in mimes:
        meta = try_parse(
            yaml.safe_load if mtype == 'yaml' else json.loads,
            buffer,
            mtype,
        )
        if meta:
            return meta
    raise ValueError(f'Failed to parse {buffer[:100]} as {mimes}')


def _parse_url(url: str) -> Dict[str, Any]:
    parsed_url = urlparse(url)
    ic(parsed_url)
    path = parsed_url.path
    query = parsed_url.query
    ic(path, query)
    if not path or re.search(r'&', path):
        raise ValueError(f'Invalid URL Path {path} in {url}')
    qs = parse_qs(query)

    def parse_nested_qs(qs: Dict[str, List[str]]) -> Dict[str, Any]:
        result = {}
        for k, v in qs.items():
            keys = k.split('.')
            d = result
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = v[0].split(',') if ',' in v[0] else v[0]
        return result

    parsed = parse_nested_qs(qs) or {}
    log.info(f'Parsed URL: {parsed}')
    return parsed


def io_buffer_os(**kwargs: Dict[str, Any]) -> Optional[str]:
    path = io_path(**kwargs)
    try:
        with open(path, 'r', encoding='utf-8') as fp:
            return fp.read()
    except Exception as e:
        log.error(f'Error: An I/O reading the file {path}: {e}')
    return None


def io_path_os(**kwargs: Dict[str, Any]) -> Path:
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


def io_buffer_fs(**kwargs: Dict[str, Any]) -> Optional[str]:
    raise NotImplementedError('Not implemented for FS')


def io_path_fs(**kwargs: Dict[str, Any]) -> Path:
    raise NotImplementedError('Not implemented for FS')


io_buffer = io_buffer_os
io_path = io_path_os
