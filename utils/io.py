import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import yaml
from pydantic import BaseModel

from utils.logger import log


def parser(input, meta=False) -> Optional[Dict[str, Any]]:
    parsed = inferred_parsing(input)
    if meta:
        return parsed
    return parsed.get('contents')


def io_dict(**kwargs: Any) -> Dict[str, Any]:
    params = [k for k, v in kwargs.items() if k in ['file', 'content', 'url']]
    if len(params) != 1:
        raise ValueError(
            f'Only one of file/content/url should be provided recieved {params}'
        )
    param = params[0]
    if kwargs.get('url'):
        param = parse_url(kwargs['url'])

    parsed = parser(param)

    if parsed is None:
        raise ValueError(f'No data returned for {param}')

    return parsed


def inferred_parsing(input: str) -> Dict[str, Any]:
    path = Path(input)
    log.info(f'Received input: {input}')

    if path.is_file():
        log.info(f'Processing file: {path}')
        mime_type, _ = mimetypes.guess_type(str(path))
        protocol = 'file'
        strm = io_stream(file=path)
        log.info(f'Read content from {path}')
        result = {
            'by': 'file',
            'file': path.name,
            'mime_type': mime_type or None,
            'protocol': protocol,
            'contents': inferred_parsing(strm),
        }
        return result

    elif path.is_dir():
        log.info(f'Processing directory: {path}')
        results = {'by': 'dir', 'dir': path.name, 'files': []}
        for file in path.iterdir():
            if file.is_file():
                results['files'].append(inferred_parsing(str(file)))
        return results

    else:
        log.info(
            'Input is not a valid file or directory; treating as raw content.'
        )
        result = parse_raw(input)

    return result


def parse_raw(content: str) -> Dict[str, Any]:
    meta = {}
    try:
        data = yaml.safe_load(content)
        mime_type = 'application/x-yaml'
        protocol = 'string'
        meta.update(
            by='yaml',
            mime_type=mime_type,
            protocol=protocol,
            contents=data,
            type=Dict,
        )
    except yaml.YAMLError as e:
        log.error(f'YAML error: {e}')
        return {'Error': 'Invalid YAML'}

    try:
        data = json.loads(content)
        mime_type = 'application/json'
        protocol = 'string'
        meta.update(
            by='json',
            mime_type=mime_type,
            protocol=protocol,
            contents=data,
            type=Dict,
        )
    except json.JSONDecodeError:
        log.info('Failed to parse as JSON, attempting YAML.')

    return meta


def io_stream_os(**kwargs: Dict[str, Any]) -> Optional[str]:
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


def io_stream_fs(**kwargs: Dict[str, Any]) -> Optional[str]:
    raise NotImplementedError('Not implemented for FS')


def io_path_fs(**kwargs: Dict[str, Any]) -> Path:
    raise NotImplementedError('Not implemented for FS')


io_stream = io_stream_os
io_path = io_stream_os


def parse_url(url: str) -> Dict[str, Any]:
    parsed_url = urlparse(url)
    qs = parse_qs(parsed_url.query)

    def parse_nested_qs(qs: Dict[str, List[str]]) -> Dict[str, Any]:
        result = {}
        for k, v in qs.items():
            keys = k.split('.')
            d = result
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = v[0].split(',') if ',' in v[0] else v[0]
        return result

    return parse_nested_qs(qs)
