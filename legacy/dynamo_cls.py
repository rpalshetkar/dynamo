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
    SingletonMeta,
    dict_flatten,
    dict_unflatten,
    jinja_render,
    po,
    typed_list,
    xlate,
)
from xds.utils.io import parser
from xds.utils.logger import ic, log


class Dynamo(metaclass=SingletonMeta):
    def __init__(self):
        self.blueprints = 'xds/catalogue/blueprints'
        self.core_models = [
            'Env',
            'DS',
            'Enums',
            'Mail',
            'Widget',
            'XDS',
        ]
        self.models = {}
        self._load_core_models()

    @staticmethod
    def proxy_method(method):
        def wrapper(self, *args, **kwargs):
            return getattr(self.__proxied__, method.__name__)(*args, **kwargs)

        return wrapper

    @staticmethod
    def _assign_defaults(model_cls, values):
        for name, field in model_cls.model_fields.items():
            extra = field.json_schema_extra
            if extra.get('flags', {}).get('list') and values.get(name):
                values[name] = typed_list(extra['itype'], values[name])
            defval = extra.get('defval')
            values[name] = values.get(name, defval)
        return values

    @staticmethod
    def _str_model_(model: BaseModel) -> str:
        return jinja_render('model', model=model)

    @staticmethod
    def _str_instance_(inst) -> str:
        log.info(f'Dumping instance {inst}')
        return po(inst.model_dump(exclude_none=True))

    @staticmethod
    def _meta_model(cls):  # noqa: PLW0211
        return {k: v.json_schema_extra for k, v in cls.model_fields.items()}

    def dynamic_model(
        self, data: Dict[str, Any], child: bool = False
    ) -> BaseModel:
        fields = {}
        cls_name, spec = self._parse_spec(data, child, fields)
        if cls_name in self.models:
            log.info(f'Returning {cls_name} from model registry')
            return self.models[cls_name]
        try:
            cfg = ConfigDict(extra='forbid')
            model = create_model(
                cls_name,
                **spec,
                __config__=cfg,
                __validators__={'before': Dynamo._before, 'after': Dynamo._after},
            )
            model.info = self._str_model_(model)
            model.__str__ = self._str_instance_
            model.meta = self._meta_model(model)
            log.info(f'Creating model for {cls_name}')
            #log.info(f'Pydantic Model Info:\n{model.info}')
            #log.info(f'Metadata:\n{po(model.meta)}')
            self.models[cls_name] = model
            return model
        except Exception as e:
            err = f'Error creating model {cls_name}: {e}'
            log.error(err)
            raise ValueError(err) from None

    def _get_class_spec(self, data: Dict[str, Any]) -> Tuple[str, List[str]]:
        kind = data.get('kind')
        if not kind:
            raise ValueError(f'Field kind not found in {data}')

        if 'str=' not in kind:
            kind = f"str={kind}"

        cls_spec = kind.split('#')
        cls_name = cls_spec[0].split('=')[1]
        return cls_name, cls_spec

    def _parse_spec(
        self, data: Dict[str, Any], child: bool, fields: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        cls_name, cls_spec = self._get_class_spec(data)
        if not child:
            data.update(self._mixings())
        xdata = self._process_xrefs(data)
        fields.update(
            {k: self._enrich_field(k, v, cls_spec) for k, v in xdata.items()}
        )
        return cls_name, fields

    def _process_xrefs(self, data: Dict[str, Any]) -> Dict[str, Any]:
        xdata = {}
        for key, value in data.items():
            if isinstance(value, str) and 'xref=' in value:
                xcls = re.sub('(xref=|#.*)', '', value)
                log.info(f'Trying XREF {xcls} in registry')
                if xcls_model := self.models.get(xcls):
                    meta = {
                        k: v['spec']
                        for k, v in xcls_model.meta.items()
                        if v.get('spec')
                    }
                    xdata[key] = meta
                else:
                    log.error(f'XREF {xcls} not found in registry {self.models}')
            else:
                xdata[key] = value
        return xdata

    def _enrich_field(
        self, key: str, value: Any, clsspec: List[str]
    ) -> Tuple[Any, Field]:
        meta = {}
        if isinstance(value, dict):
            field_type = self.dynamic_model(value, child=True)
            meta = {
                'dtype': str(field_type),
                'required': len(clsspec) > 1 and 'req' in clsspec[1],
                'defval': Ellipsis
                if len(clsspec) > 1 and 'req' in clsspec[1]
                else None,
            }
        elif isinstance(value, list):
            field_type = List[self.dynamic_model(value[0], child=True)]
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

    @staticmethod
    def _mixings():
        return {
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
        }

    def _load_core_models(self) -> Dict[str, Any]:
        files = parser(self.blueprints)
        if not files.get('contents'):
            raise ValueError(
                f'No model file contents seen in {self.blueprints}'
            )
        fconfigs = {i['kind']: i for i in files['contents']}
        core_models = {}
        for model in self.core_models:
            core_models[model] = self.dynamic_model(fconfigs[model])
        return core_models

    @staticmethod
    def _get_mixings(what: str, model: str, vars: Dict[str, Any]) -> Dict[str, Any]:
        ns = '/'.join([i for i in [what, model, vars.get('ns')] if i])
        uid = 'fta'
        ts = datetime.now().isoformat()
        return {
            'ns': ns,
            'nsid': ns.lower(),
            'uid': uid,
            'created_by': uid,
            'updated_by': uid,
            'created_ts': ts,
            'updated_ts': ts,
        }

    @staticmethod
    def _normalize_nesting(kws: dict, delim: str) -> dict:
        dots = [k for k in kws.keys() if '.' in k]
        for k in dots:
            kws[k.replace('.', delim)] = kws.pop(k)
        kwmatch = f'kw{delim}kwargs{delim}'
        kwargsv = [k for k in kws.keys() if kwmatch in k]
        for k in kwargsv:
            v = kws.pop(k)
            kws[k.replace(kwmatch, 'kw__')] = v
        return kws


    @staticmethod
    def _build_kws_dict(kwscopy: dict, delim: str) -> dict:
        result = {}
        for k, v in kwscopy.items():
            ky = re.sub(r'(kw|kwargs)__', '', k).replace(delim, '.')
            result[ky] = v
        return result

    @staticmethod
    @model_validator(mode='before')
    def _before(cls, values):
        try:
            delim = '__'
            prefix = 'kw'
            vals = {k: v for k, v in values.items() if v}
            vals['kwargs'] = vals.pop('kws', {})

            kws = dict_flatten(vals, delimiter=delim, prefix=prefix)
            kws = Dynamo._normalize_nesting(kws, delim)

            cleansed = dict_unflatten(kws, delimiter=delim, prefix=prefix)
            cleansed = Dynamo._assign_defaults(cls, cleansed)
            cleansed['kws'] = Dynamo._build_kws_dict(kws.copy(), delim)

            valid_fields = list(cls.model_fields.keys())
            cleansed = {k: v for k, v in cleansed.items() if k in valid_fields}
            log.debug(po(cleansed))
            return cleansed

        except Exception as e:
            ic(
                f'Error validating attributes before creation of object for {cls}: {e}'
            )
        return {}


    @staticmethod
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
                setattr(
                    cls,
                    export,
                    Dynamo.proxy_method(val) if callable(val) else val,
                )
        except Exception as e:
            ic(f'Error setting proxy methods for {cls}: {e}')
        return obj