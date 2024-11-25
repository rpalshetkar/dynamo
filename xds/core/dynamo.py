from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    model_validator,
)

from xds.core.proxies import PROXY_MAP
from xds.utils.field import field_specs
from xds.utils.helpers import jinja_render, typed_list
from xds.utils.logger import ic, log


def proxy_method(method):
    def wrapper(self, *args, **kwargs):
        return getattr(self.__proxied__, method.__name__)(*args, **kwargs)

    return wrapper


def _str_tolist(cls, values):
    for name, field in cls.model_fields.items():
        extra = field.json_schema_extra
        if extra.get('flags', {}).get('list') and values.get(name):
            values[name] = typed_list(extra['itype'], values[name])
        defval = extra.get('defval')
        values[name] = values.get(name, defval)
    return values


@model_validator(mode='before')
def _before(cls, values):
    try:
        return _str_tolist(cls, values)
    except Exception as e:
        ic(
            f'Error validating attributes before creation of object for {cls}: {e}'
        )
        return values


@model_validator(mode='after')
def _after(cls, obj):
    try:
        proxy = getattr(obj, 'proxy', None)
        if not proxy:
            return obj

        dcls: Any = PROXY_MAP.get(proxy)
        if not dcls:
            raise ValueError(f'Proxy class {proxy} not found in {PROXY_MAP}')

        inst = dcls.create(**obj.__dict__)
        obj.__proxied__ = inst
        for export in inst.exports:
            val = getattr(inst, export)
            setattr(cls, export, proxy_method(val) if callable(val) else val)
    except Exception as e:
        ic(f'Error setting proxy methods for {cls}: {e}')
    return obj


def _augment_spec():
    enrich = {}
    enrich = {
        'ns': 'str',
        'nsid': 'str',
        'uid': 'str',
        'uuid': 'uuid',
        'created_ts': 'dt',
        'updated_ts': 'dt',
        'created_by': 'str',
        'updated_by': 'str',
        'args': 'list',
        'kwargs': 'dict',
    }
    return enrich


def __str_model__(model: BaseModel) -> str:
    return jinja_render('model', model=model)


def dynamic_model(data: Dict[str, Any]) -> BaseModel:
    fields = {}
    assert data.get('kind'), 'Kind is required'
    cls_spec = data.get('kind').split('#')
    cls_name = cls_spec[0]
    data.update(_augment_spec())

    for key, value in data.items():
        meta = {}
        if isinstance(value, dict):
            field_type = dynamic_model(value)
            meta = {
                'dtype': str(field_type),
                'required': len(cls_spec) > 1 and 'req' in cls_spec[1],
                'defval': Ellipsis
                if len(cls_spec) > 1 and 'req' in cls_spec[1]
                else None,
            }
        elif isinstance(value, list):
            field_type = List[dynamic_model(value[0])]
            meta = {'dtype': str(field_type)}
        else:
            spec = field_specs(value)
            field_type = spec.pop('type')
            required = 'req' in spec.get('flags', {})
            meta.update(
                {
                    'dtype': str(field_type),
                    'required': required,
                    'defval': spec.get('defval'),
                }
            )
        default = meta.get('defval', None)
        required = meta.get('required', False)
        field = Any
        if default:
            field = Field(default=default, json_schema_extra=meta)
        elif required:
            field = Field(Ellipsis, json_schema_extra=meta)
        else:
            field = Field(json_schema_extra=meta)
        if not required:
            field_type = Optional[field_type]
        fields[key] = (field_type, field)

    try:
        model = create_model(
            cls_name,
            **fields,
            __validators__={'before': _before, 'after': _after},
        )
        model.model_config = ConfigDict(extra='allow', strict=True)
        log.info(f'Creating model for {cls_name} {model}')
        model.__str__ = __str_model__
        ic(model)
        return model
    except Exception as e:
        ic(f'Error creating model {cls_name}: {e}')
        raise


def augment(what: str, model: str, vars: Dict[str, Any]) -> Dict[str, Any]:
    ns = '/'.join([i for i in [what, model, vars.get('ns')] if i])
    uid = 'fta'
    ts = datetime.now()
    ts = ts.isoformat()
    return {
        'ns': ns,
        'nsid': ns.lower(),
        'uid': uid,
        'created_by': uid,
        'updated_by': uid,
        #'uuid': str(uuid4()),
        'created_ts': ts,
        'updated_ts': ts,
    }


def _augment_extra(optional: bool = True):
    field_types = {
        'uid': str,
        'uuid': UUID4,
        'ns': str,
        'nsid': str,
        'args': List[Any],
        'kwargs': Dict[str, Any],
    }
    required = ['uuid', 'ns', 'nsid']
    required = ['uuid', 'nsid']
    field_types = {
        k: Optional[v] if optional else v
        for k, v in field_types.items()
        if k not in required
    }

    fields = {
        param: (
            dtype,
            Field(json_schema_extra={'dtype': str(dtype)}),
        )
        for param, dtype in field_types.items()
    }
    return fields
