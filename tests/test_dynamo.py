from pprint import pp
from typing import TYPE_CHECKING

import pandas as pd
import pytest
from pydantic import BaseModel, ConfigDict, Field

from core.dynamo import dynamic_model
from utils.io import parser
from utils.logger import ic


@pytest.fixture(scope='session')
def setup():
    pd.set_option('display.max_rows', 1500)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', 200)
    pd.set_option('expand_frame_repr', True)
    pd.set_option('display.width', 2000)
    pd.set_option('display.float_format', '{:10,.0f}'.format)

    ds = """
        kind: DS
        ns: str
        proxy: str=DSProxy
        uri: str#req
        protocol: str=http
    """
    dsd = """
        kind: DS
        ns: xbow
        uri: txf://jira
        protocol: http
    """
    widget = """
        kind: Widget
        proxy: str#req
        type: enum=table,pivot,bar,line,gannt,heatmap,sankey
        x: str
        y: str
        c: str
        theme: str
        orient: enum=h,v
        total: bool
    """
    models = {
        'DS': ds,
        'Widget': widget,
        'Jiras': dsd,
    }
    return models


def test_ds_model(setup):
    schema = setup['DS']
    dsm = dynamic_model(parser(schema))
    assert dsm, 'DS Model should be created'
    ic(dsm.model_json_schema())
    kwargs = ic(parser(setup['Jiras']))
    ds = dsm(**kwargs)
    df: pd.DataFrame = ds.df
    assert not df.empty, 'DS/DF should be created'
    ic(ds.stats())
