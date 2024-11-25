from pprint import pp
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from xds.core.dynamo import dynamic_model
from xds.utils.io import parser
from xds.utils.logger import ic


@pytest.fixture(scope='session')
def setup():
    pd.set_option('display.max_rows', 1500)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', 200)
    pd.set_option('expand_frame_repr', True)
    pd.set_option('display.width', 2000)
    pd.set_option('display.float_format', '{:10,.0f}'.format)

    fdir = 'tests/fixtures'
    myml = f'{fdir}/models.yaml'
    cyml = f'{fdir}/data.yaml'
    models = parser(myml)
    configs = parser(cyml)

    return {'models': models, 'configs': configs}


@pytest.mark.usefixtures('setup')
def test_ds_model(setup):
    models = setup['models']
    configs = setup['configs']
    dsm = dynamic_model(parser(models['DS']))
    assert dsm, 'DS Model should be created'
    ic(dsm.model_json_schema())
    kwargs = ic(parser(configs['bow']))
    ds = dsm(**kwargs)
    df: pd.DataFrame = ds.df
    assert not df.empty, 'DS/DF should be created'
    ic(ds.stats())


@pytest.mark.skip
def test_ds_model_v1(setup):
    from legacy.dynamo_v1 import dynamic_model_v1

    models = setup['models']
    configs = setup['configs']
    dsm = dynamic_model_v1(parser(models['DS']))
    assert dsm, 'DS Model should be created'
    ic(dsm.schema_json())
    kwargs = ic(parser(configs['bow']))
    ds = dsm(**kwargs)
    df: pd.DataFrame = ds.df
    assert not df.empty, 'DS/DF should be created'
    ic(ds.stats())
