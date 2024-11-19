from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from core.proxies import PROXY_MAP
from utils.field import field_specs
from utils.helpers import typed_list
from utils.logger import ic, log


def proxy_method(method):
    def wrapper(self, *args, **kwargs):
        return getattr(self.__proxied__, method.__name__)(*args, **kwargs)

    return wrapper


def _before(cls, values):
    values = _str_tolist(cls, values)
    values['kwargs'] = values
    return values


def _after(cls, obj):
    proxy = obj.proxy
    if proxy:
        dcls: Any = PROXY_MAP.get(proxy)
        if not dcls:
            raise ValueError(f'Proxy class {proxy} not found in {PROXY_MAP}')
        inst = dcls.create(**obj.kwargs)
        obj.__proxied__ = inst
        for export in inst.exports:
            val = getattr(inst, export)
            if callable(val):
                setattr(cls, export, proxy_method(val))
            else:
                setattr(cls, export, val)
    return obj


def _str_tolist(cls, values):
    for name, field in cls.model_fields.items():
        extra = field.json_schema_extra
        if extra.get('flags', {}).get('list') and values.get(name):
            values[name] = typed_list(extra['itype'], values[name])
        default = extra.get('default')
        values[name] = values.get(name, default)
    if extra.get('flags', {}).get('list') and values.get(name):
        return typed_list(extra['itype'], values[name])
    return values


def dynamic_model(data: Dict[str, Any]) -> BaseModel:
    fields = {}
    assert data.get('kind'), 'Kind is required'
    cls_spec = data.get('kind').split('#')
    cls_name = cls_spec[0]

    for key, value in data.items():
        meta = {}
        if isinstance(value, dict):
            field_type = dynamic_model(value)
            meta = {
                'dtype': field_type,
                'required': 'req' in cls_spec[1],
                'default': None if 'req' not in cls_spec[1] else ...,
            }
        elif isinstance(value, list):
            field_type = List[dynamic_model(value[0])]
            meta = {'dtype': field_type}
        else:
            meta = field_specs(value)
            field_type = meta.pop('type')
            if 'req' in meta.get('flags', {}):
                meta['required'] = True

        fields[key] = (field_type, Field(..., json_schema_extra=meta))
        fields['kwargs'] = (
            Dict[str, Any],
            Field(..., json_schema_extra={'title': 'kwargs'}),
        )

    fields['__validators__'] = {
        'before': model_validator(mode='before')(_before),
        'after': model_validator(mode='after')(_after),
    }

    model = create_model(cls_name, **fields)
    model.model_config = ConfigDict(extra='forbid', strict=True)
    log.info(f'Creating model for {cls_name} {model}')
    return model
