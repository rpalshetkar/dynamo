import re
from datetime import datetime
from pprint import pp
from typing import Any, Dict, List, Optional, Tuple
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
from xds.utils.helpers import (
    dict_flatten,
    dict_unflatten,
    jinja_render,
    po,
    typed_list,
    xlate,
)
from xds.utils.io import parser
from xds.utils.logger import ic, log


def proxy_method(method):
    def wrapper(self, *args, **kwargs):
        return getattr(self.__proxied__, method.__name__)(*args, **kwargs)

    return wrapper


def _assign_defaults(cls, values):
    for name, field in cls.model_fields.items():
        extra = field.json_schema_extra
        if extra.get('flags', {}).get('list') and values.get(name):
            values[name] = typed_list(extra['itype'], values[name])
        defval = extra.get('defval')
        values[name] = values.get(name, defval)
    return values


@model_validator(mode='before')
def _before(cls, values):
    cleansed = {}
    flds = list(cls.model_fields.keys())
    try:
        delim = '__'
        prefix = 'kw'
        vals = {k: v for k, v in values.items() if v}
        vals['kwargs'] = vals.pop('kws', {})
        kws = dict_flatten(vals, delimiter=delim, prefix=prefix)

        dots = [k for k in kws.keys() if '.' in k]
        for k in dots:
            kws[k.replace('.', delim)] = kws.pop(k)
        kwscopy = kws.copy()

        kwmatch = f'kw{delim}kwargs{delim}'
        kwargsv = [k for k in kws.keys() if kwmatch in k]
        for k in kwargsv:
            v = kws.pop(k)
            kws[k.replace(kwmatch, 'kw__')] = v

        cleansed = dict_unflatten(kws, delimiter=delim, prefix=prefix)
        cleansed = _assign_defaults(cls, cleansed)
        cleansed['kws'] = {}

        for k, v in kwscopy.items():
            ky = re.sub(r'(kw|kwargs)__', '', k).replace(delim, '.')
            cleansed['kws'][ky] = v
        cleansed = {k: v for k, v in cleansed.items() if k in flds}
        log.debug(po(cleansed))

    except Exception as e:
        ic(
            f'Error validating attributes before creation of object for {cls}: {e}'
        )
    return cleansed


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


def _str_model_(model: BaseModel) -> str:
    output: str = jinja_render('model', model=model)
    return output


def _str_instance_(inst) -> str:
    log.info(f'Dumping instance {inst}')
    return po(inst.model_dump(exclude_none=True))


def _meta_model(cls):
    meta = {k: v.json_schema_extra for k, v in cls.model_fields.items()}
    return meta


def dynamic_model(data: Dict[str, Any], child: bool = False) -> BaseModel:
    fields = {}
    cls_name, cls_spec, fields = _pre_create(data, child, fields)
    try:
        cfg = ConfigDict(extra='forbid')
        model = create_model(
            cls_name,
            **fields,
            __config__=cfg,
            __validators__={'before': _before, 'after': _after},
        )
        model.info = _str_model_(model)
        model.__str__ = _str_instance_
        model.meta = _meta_model(model)
        log.info(f'Creating model for {cls_name}\n\nModel:\n{model.info}\n\n')
        log.info(f'MetaData:\n{po(model.meta)}')
        return model
    except Exception as e:
        err = f'Error creating model {cls_name}: {e}'
        log.error(err)
        raise ValueError(err) from None


def _pre_create(
    data: Dict[str, Any], child: bool, fields: Dict[str, Any]
) -> Tuple[str, List[str], Dict[str, Any]]:
    assert data.get('kind'), 'Kind is required'
    if 'str=' not in data['kind']:
        log.info(f'Adding defaulting spec {data["kind"]}')
        data['kind'] = f"str={data['kind']}"

    cls_spec = data.get('kind').split('#')
    _, cls_name = cls_spec[0].split('=')

    if not child:
        data.update(_augment_spec())

    for key, value in data.items():
        if isinstance(value, str) and re.search(r'xref=', value):
            _, xcls = value.split('=')
            xcls = None
            if not xcls:
                log.error(f'XRef class {xcls} not found')
                continue
            meta = {k: v['spec'] for k, v in xcls.meta.items() if v.get('spec')}
            data[key] = meta

    for key, value in data.items():
        fields[key] = _enrich_field(key, value, cls_spec)

    return cls_name, cls_spec, fields


def _enrich_field(
    key: str, value: Any, clsspec: List[str]
) -> Tuple[Any, Field]:
    meta = {}
    if isinstance(value, dict):
        field_type = dynamic_model(value, child=True)
        meta = {
            'dtype': str(field_type),
            'required': len(clsspec) > 1 and 'req' in clsspec[1],
            'defval': Ellipsis
            if len(clsspec) > 1 and 'req' in clsspec[1]
            else None,
        }
    elif isinstance(value, list):
        field_type = List[dynamic_model(value[0], child=True)]
        meta = {'dtype': str(field_type)}
    else:
        spec = field_specs(value)
        field_type = spec.pop('type')
        required = 'req' in spec.get('flags', {})
        meta.update(
            {
                'dtype': str(field_type),
                'required': required,
            }
        )
        meta.update(spec)

    default = meta.get('defval', None)
    required = meta.get('required', False)
    field = Any
    if meta:
        meta = {k: v for k, v in meta.items() if v}
        _, eng = xlate(key)
        meta['title'] = eng
    if default:
        field = Field(default=default, json_schema_extra=meta)
    elif required:
        field = Field(Ellipsis, json_schema_extra=meta)
    else:
        field = Field(json_schema_extra=meta)
    if not required:
        field_type = Optional[field_type]

    return field_type, field


def _augment_spec():
    add_spec = {}
    add_spec = {
        'ns': 'str',
        'nsid': 'str',
        'uid': 'str#sys',
        'uuid': 'uuid#sys',
        'created_ts': 'dt#sys',
        'updated_ts': 'dt#sys',
        'created_by': 'str#sys',
        'updated_by': 'str#sys',
        'args': 'list',
        'kws': 'dict',
        #'kwargs': 'dict',
    }
    return add_spec


def audit(what: str, model: str, vars: Dict[str, Any]) -> Dict[str, Any]:
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


@model_validator(mode='before')
def _before_x(cls, values):
    cleansed = {}
    try:
        delim = '__'
        prefix = 'kw'

        if values.get('kwargs'):
            kws = dict_flatten(values['kwargs'], delimiter=delim, prefix=prefix)
            for k in [k for k in kws.keys() if '.' in k]:
                kws[k.replace('.', delim)] = kws.pop(k)
            values.update(kws)

        values = _assign_defaults(cls, values)

        k_unflat = {k: v for k, v in values.items() if '__' in k}
        if k_unflat:
            kws = dict_unflatten(k_unflat, delimiter=delim, prefix=prefix)
            if kws:
                values.update(kws)

        cleansed = {k: v for k, v in values.items() if delim not in k}

    except Exception as e:
        ic(
            f'Error validating attributes before creation of object for {cls}: {e}'
        )
    return cleansed
