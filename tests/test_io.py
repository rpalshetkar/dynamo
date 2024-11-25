import json
import tempfile
from pathlib import Path

import pytest
import yaml
from icecream import ic

from xds.utils.io import parser


@pytest.fixture(scope='session')
def io_data():
    data = {
        'ydir': 'tests/blueprints',
        'url': (
            'x.go/xds?user.name=John&user.age=30&'
            'user.hobbies=reading,gaming&address.city=HongKong&address.zip=12345'
        ),
        'wrong_url': 'user.name=John&user.age=30&user.hobbies=reading,gaming&address.city',
        'url_dict': {
            'user': {
                'name': 'John',
                'age': '30',
                'hobbies': ['reading', 'gaming'],
            },
            'address': {'city': 'HongKong', 'zip': '12345'},
        },
        'io_dict': {
            'level0': 'level0',
            'level1': {
                'level2': {'level3': {'key': 'value', 'list': [1, 2, 3]}}
            },
        },
    }
    data['io_json'] = json.dumps(data['io_dict']).encode('utf-8')
    data['io_yaml'] = yaml.dump(data['io_dict']).encode('utf-8')

    for ext in ['json', 'yaml']:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f'.{ext}'
        ) as tmp_file:
            tmp_file.write(data[f'io_{ext}'])
            data[f'io_{ext}_file'] = tmp_file.name

    yield data

    Path(data['io_json_file']).unlink()
    Path(data['io_yaml_file']).unlink()


@pytest.mark.usefixtures('io_data')
def test_parser_url(io_data):
    parsed = parser(url=io_data['url'])
    assert parsed == io_data['url_dict']


@pytest.mark.usefixtures('io_data')
def test_parser_yaml_string(io_data):
    yaml_string = yaml.dump(io_data['io_dict'])
    parsed = parser(buffer=yaml_string, mime='yaml')
    assert parsed == io_data['io_dict']


@pytest.mark.usefixtures('io_data')
def test_parser_json_string(io_data):
    json_string = json.dumps(io_data['io_dict'])
    parsed = parser(buffer=json_string, mime='json')
    assert parsed == io_data['io_dict']


@pytest.mark.usefixtures('io_data')
def test_parser_yaml_file(io_data):
    parsed = parser(path=io_data['io_yaml_file'])
    assert parsed == io_data['io_dict']


@pytest.mark.usefixtures('io_data')
def test_parser_yaml_argfile(io_data):
    parsed = parser(io_data['io_yaml_file'])
    assert parsed == io_data['io_dict']


@pytest.mark.usefixtures('io_data')
def test_parser_yaml_argdir(io_data):
    parsed = parser(io_data['ydir'])
    ic(parsed)
    assert parsed


@pytest.mark.usefixtures('io_data')
def test_parser_json_file(io_data):
    parsed = parser(path=io_data['io_json_file'])
    assert parsed == io_data['io_dict']


@pytest.mark.xfail(
    ValueError, reason='Either path or buffer must be provided, but not both'
)
@pytest.mark.usefixtures('io_data')
def test_parser_argissue_fail(io_data):
    parser(
        path=io_data['io_json_file'],
        buffer=io_data['io_json'],
    )


@pytest.mark.xfail(FileNotFoundError, reason='FILE/DIR not found: dummy_path')
@pytest.mark.usefixtures('io_data')
def test_parser_nofile_file(io_data):
    parser(path='dummy_path')


@pytest.mark.xfail(ValueError, reason='Failed to parse the input')
def test_parser_jsonstr_fail():
    invalid_json = '{"key": "value",}'
    parser(buffer=invalid_json, mime='json')


@pytest.mark.xfail(ValueError, reason='Failed to parse as yaml')
def test_parser_yamlstr_fail():
    invalid_yaml = """
        level1:
            level2:
                level3:
                    key: value,,
                    list: [1, 2, 3]
    """.strip()
    parser(buffer=invalid_yaml, mime='yaml')


@pytest.mark.xfail(ValueError, reason='Failed to parse the input')
@pytest.mark.usefixtures('io_data')
def test_parser_url_fail(io_data):
    malformed_url = io_data['wrong_url']
    parser(url=malformed_url)
