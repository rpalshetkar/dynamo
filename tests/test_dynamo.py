from pprint import pp
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from tests.df_mocks_fixtures import FAKE_DFS
from xds.core.dynamo import Dynamo
from xds.utils.helpers import po
from xds.utils.io import parser
from xds.utils.logger import ic, log

DSKWARGS = """
kind: DS
ns:
uri:
"""

FAKE_DF_NAMES = ['xbow', 'xait', 'xfunding', 'xcomp']


@pytest.fixture(scope='session')
def setup():
    pd.set_option('display.max_rows', 1500)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', 200)
    pd.set_option('expand_frame_repr', True)
    pd.set_option('display.width', 2000)
    pd.set_option('display.float_format', '{:10,.0f}'.format)
    dspayload = parser(buffer=DSKWARGS)

    dynamo = Dynamo()
    fdir = 'tests/fixtures'
    myml = f'{fdir}/models.yaml'
    testmymls = parser(myml)
    testmodels = {}
    for model in testmymls:
        testmodels[model] = dynamo.register_model(testmymls[model])
    return {
        'coremodels': dynamo.models,
        'testmodels': testmodels,
        'dskwargs': dspayload,
    }


@pytest.mark.usefixtures('setup')
@pytest.mark.parametrize('fakeds', FAKE_DF_NAMES)
def test_ds_fakes(setup, fakeds):
    assert fakeds in FAKE_DFS, f'{fakeds} not in FAKE_DFS'
    dsm = setup['coremodels']['DS']
    payload = setup['dskwargs']
    payload['ns'] = fakeds
    assert dsm, 'DS Model should be created'
    ds = dsm(**payload)
    df: pd.DataFrame = ds.df
    assert not df.empty, 'DS/DF should be created'
    ic(ds.stats())


@pytest.mark.usefixtures('setup')
@pytest.mark.parametrize(
    ('model', 'payload_type', 'payload', 'expected'),
    [
        (
            'ComplexModel',
            'kw',
            {'ds.ns': 'xbow', 'widget.type': 'bar'},
            None,
        ),
        (
            'ComplexModel2',
            'kw',
            {
                'bstr': 'BSTR',
                'kws': {
                    'nested1.aint': 10,
                    'nested1__bstr': 'Override N1 nested',
                },
            },
            None,
        ),
    ],
)
def test_complex_model(
    setup, model: str, payload_type: str, payload: Any, expected: str
) -> None:
    ic(setup, model, payload_type, payload, expected)
    model = setup['testmodels'].get(model)
    assert model, f'{model} not in testmodels'
    if payload_type == 'kw':
        kwargs = payload
        inst = model(**kwargs)
        pp(inst)


@pytest.mark.skip
def test_ds_model_v1(setup):
    from legacy.dynamo_v1 import dynamic_model_v1

    models = setup['models']
    configs = setup['configs']
    dsm = dynamic_model_v1(parser(models['DS']))
    assert dsm, 'DS Model should be created'
    kwargs = ic(parser(configs['bow']))
    ds = dsm(**kwargs)
    df: pd.DataFrame = ds.df
    assert not df.empty, 'DS/DF should be created'
    ic('Stats\n', ds.stats())
