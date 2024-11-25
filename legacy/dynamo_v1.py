from typing import Any, Dict, List

from pydantic.v1 import BaseModel, Field, create_model
from pydantic.v1.class_validators import root_validator

from xds.core.proxies import PROXY_MAP
from xds.utils.field import field_specs
from xds.utils.helpers import typed_list
from xds.utils.logger import ic, log


def proxy_method(method):
    def wrapper(self, *args, **kwargs):
        return getattr(self.__proxied__, method.__name__)(*args, **kwargs)

    return wrapper


@root_validator(pre=True)
def _before(cls, values):
    try:
        values = _str_tolist(cls, values)
    except Exception as e:
        ic(
            f'Error validationg attributes before creation of object for {cls}: {e}'
        )
    log.info(f'BEFORE {cls}: Attributes {values}')
    return values


@root_validator(pre=False)
def _after(cls, values):
    log.info(f'Validating attributes AFTER {cls}: {values}')
    try:
        proxy = values.get('proxy')
        if proxy:
            dcls: Any = PROXY_MAP.get(proxy)
            if not dcls:
                raise ValueError(
                    f'Proxy class {proxy} not found in {PROXY_MAP}'
                )
            inst = dcls.create(**values)
            cls.__proxied__ = inst
            for export in inst.exports:
                val = getattr(inst, export)
                if callable(val):
                    setattr(cls, export, proxy_method(val))
                else:
                    setattr(cls, export, val)
    except Exception as e:
        ic(f'Error while class setting {cls}: {e}')
    log.info(f'AFTER {cls}: Attributes {values}')
    return values


def _str_tolist(cls, values):
    for name, field in cls.__fields__.items():
        extra = field.field_info.extra
        if extra.get('flags', {}).get('list') and values.get(name):
            values[name] = typed_list(extra['itype'], values[name])
        defval = extra.get('defval')
        values[name] = values.get(name, defval)
    if extra.get('flags', {}).get('list') and values.get(name):
        return typed_list(extra['itype'], values[name])
    return values


def dynamic_model_v1(data: Dict[str, Any]) -> BaseModel:
    fields = {}
    assert data.get('kind'), 'Kind is required'
    cls_spec = data.get('kind').split('#')
    cls_name = cls_spec[0]

    for key, value in data.items():
        meta = {}
        if isinstance(value, dict):
            field_type = dynamic_model_v1(value)
            meta = {
                'dtype': field_type,
                'required': 'req' in cls_spec[1],
                'defval': None if 'req' not in cls_spec[1] else ...,
            }
        elif isinstance(value, list):
            field_type = List[dynamic_model_v1(value[0])]
            meta = {'dtype': field_type}
        else:
            meta = field_specs(value)
            field_type = meta.pop('type')
            if 'req' in meta.get('flags', {}):
                meta['required'] = True

        fields[key] = (field_type, Field(..., **meta))

    try:
        model = create_model(
            cls_name,
            **fields,
            __validators__={'before': _before, 'after': _after},
        )
    except Exception as e:
        ic(f'Error creating model {cls_name}: {e}')
        raise e

    class Config:
        extra = 'forbid'
        strict = True

    model.Config = Config
    log.info(f'Creating model for {cls_name} {model}')
    return model
