import inspect
import re
from datetime import datetime
from pprint import pp
from typing import Any, Dict, List, Optional, Tuple

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


from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from xds.utils.helpers import SingletonMeta
from xds.utils.io import io_path, parser
from xds.utils.logger import log

BLUEPRINTS = 'xds/catalogue/blueprints'
CONFIGS = 'xds/configs'
TEMPLATES = 'xds/catalogue/templates'
ENVNAME = 'bootstrap'


class Dynamo(metaclass=SingletonMeta):
    def __init__(self, **kwargs):
        self.envname: str = kwargs.get('env', ENVNAME)
        self.ns: Dict[str, Any] = kwargs.get('ns', {})
        self.blueprints: str = kwargs.get('blueprints', BLUEPRINTS)
        self.configs: str = kwargs.get('configs', CONFIGS)
        self.templates: str = kwargs.get('templates', TEMPLATES)

        self.models: Dict[str, Any] = {}
        self.instances: Dict[str, Any] = {}
        self.callables: Dict[str, Any] = {}
        self.jinjas: Dict[str, Any] = {}
        self._configs: Dict[str, Any] = {}
        self.env: Any = None

        self.envfile = f'{self.configs}/env.{self.envname}.yaml'

        self._filecfgs('models', self.blueprints)
        self._filecfgs('configs', self.configs)
        assert self._filecfgs, 'No Configs seen in Registry'

        env_cls = 'Env'
        self.register_model(env_cls)
        self.register_instance(env_cls, path=self.envfile)
        self.env = self.obj(f'instances/{env_cls}/{self.envname}')
        log.info(f'Env => {self.env.nsid}')
        for model in self.env.models:
            self.register_model(model)
        self.allowed_callees = ['register_model']

    def _filecfgs(self, what: str, dir: str):
        files = parser(dir)
        if not files.get('contents'):
            raise ValueError(f'No model file contents seen in {dir}')
        fconfigs = {f"{what}/{i['kind']}".lower(): i for i in files['contents']}
        if fconfigs:
            self._configs.update(fconfigs)

    def register_model(self, model: str = None) -> Any:
        model_ref = {}
        try:
            if model and isinstance(model, dict):
                model_ref = model
            else:
                clscfg = self._configs.get(f'models/{model}'.lower())
                assert clscfg, f'{model} Config not found'
                model_ref = clscfg
            cls_name = model_ref.get('kind')
            cls = self.dynamic_model(model_ref)
            self._ns_init('models', cls_name, cls)
            return cls
        except Exception as e:
            log.error(f'Error registering model {model}: {e}')
            raise e

    def register_instance(self, model: Optional[str] = None, **kwargs) -> Any:
        model = model or kwargs.get('kind')
        assert model, 'Model not specified'
        vars = parser(**kwargs)
        vars.update(self._get_mixings('instances', model, vars))
        try:
            cls = self.model(model)
            if not cls:
                raise ValueError(f'Model {model} not found')
            inst = cls(**vars)
            self._ns_init('instances', model, inst)
            return inst
        except Exception as e:
            log.error(f'Error registering instance {model}: {e}')
            raise e

    def dynamic_model(
        self, data: Dict[str, Any], child: bool = False
    ) -> BaseModel:

        caller = inspect.stack()[1].function
        callees = ['register_model', '_enrich_field']
        if caller not in callees:
            raise PermissionError(f"{caller} is not in {callees} for dynamic_model")

        fields = {}
        cls_name, _ = self._get_class_spec(data)
        model = self.model(cls_name)
        if model:
            log.info(f'Returning {cls_name} from model registry cache')
            return model
        try:
            cls_name, normalized_fields = self._parse_spec(data, child, fields)
            cfg = ConfigDict(extra='forbid')
            model = create_model(
                cls_name,
                **normalized_fields,
                __config__=cfg,
                __validators__={'before': Dynamo._before, 'after': Dynamo._after},
            )
            model.info = self._str_model_(model)
            model.__str__ = self._str_instance_
            model.meta = self._meta_model(model)
            log.info(f'Creating model for {cls_name}')
            #log.debug(f'Pydantic Model Info:\n{model.info}')
            #log.debug(f'Metadata:\n{po(model.meta)}')
            #self.models[cls_name] = model
            return model
        except Exception as e:
            err = f'Error creating model {cls_name}: {e}'
            log.error(err)
            raise ValueError(err) from None

    def set_env(self, envname: str = ENVNAME) -> Any:
        envmf = f'{BLUEPRINTS}/env.yaml'
        env_cls = self.dynamic_model(parser(envmf))
        assert env_cls, f'Failed to create Env Model from {envmf}'
        envcf = f'{CONFIGS}/env.{envname}.yaml'
        vars = parser(envcf)
        vars.update(self._get_mixings('instances', 'Env', vars))
        env = env_cls(**vars)
        assert env, f'Failed to create Env from {envcf}'
        return env

    def _ns_init(self, what: str, model: str, obj: Any) -> None:
        oid = model.lower()
        if what == 'models':
            self.models[oid] = obj
        elif what == 'instances':
            oid = (obj.nsid or f'{model}/{obj.ns}').lower()
            self.instances[oid] = obj
        ns_id = f'{what}/{oid}'.lower()
        obj.nsid = ns_id
        self.ns[ns_id] = obj
        log.info(f'Namespace => {ns_id} Initialized')

    def locator(self, nskey: str) -> Any:
        obj = self.ns.get(nskey.lower())
        if obj:
            return obj

        parts = nskey.split('/')
        if nskey.startswith('models/'):
            obj = self.models.get(parts[1])
            if obj:
                return obj

        if nskey.startswith('instances/'):
            obj = self.instances.get(f'{parts[1]}/{parts[2]}')
            if obj:
                return obj
            else:
                last = f'/{parts[-1]}'
                found = [i for i in self.ns if i.endswith(last)]
                if len(found) == 1:
                    log.info(f'Found {found[0]} for {nskey} with fuzzy search')
                    return self.ns[found[0]]
        return None

    def model(self, clstr: str) -> Any:
        return self.locator(f'models/{clstr}')

    def obj(self, objkey: str) -> Any:
        return self.locator(objkey)

    instance = obj

    def __str__(self) -> str:
        data = [
            ['Env', ic(self.env)],
            ['Models', ic(self.models)],
            ['Instances', ic(self.instances)],
            ['Callables', ic(self.callables)],
        ]
        sep = '-' * 60 + '\n'
        return sep.join(f'{header} ->{content}\n' for header, content in data)


    @staticmethod
    def proxy_callback(method):
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

    def restrict(self, callees: List[str]):
        pass

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
            if key == 'kind':
                meta['cls_name'] = value
            meta.update(spec)

        default = meta.get('defval', None)
        required = meta.get('required', False)
        field = Any
        if meta:
            meta = {k: v for k, v in meta.items() if v}
            var, eng = xlate(key)
            meta['title'] = eng
            meta['var'] = var
        if default:
            field = Field(default=default, alias=var, json_schema_extra=meta)
        elif required:
            field = Field(Ellipsis, alias=var, json_schema_extra=meta)
        else:
            field = Field(alias=var, json_schema_extra=meta)
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

    @staticmethod
    def _get_mixings(what: str, model: str, vars: Dict[str, Any]) -> Dict[str, Any]:
        ns = '/'.join([i for i in [model, vars.get('ns')] if i])
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
                    Dynamo.proxy_callback(val) if callable(val) else val,
                )
        except Exception as e:
            ic(f'Error setting proxy methods for {cls}: {e}')
        return obj