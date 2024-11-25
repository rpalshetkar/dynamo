from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import pydantic
from icecream import ic
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field, model_validator

from xds.core.dynamo import augment, dynamic_model
from xds.utils.helpers import SingletonMeta
from xds.utils.io import io_path, parser
from xds.utils.logger import log

BLUEPRINTS = 'xds/catalogue/blueprints'
CONFIGS = 'xds/configs'
TEMPLATES = 'xds/catalogue/templates'


class Registry(metaclass=SingletonMeta):
    def __init__(self, **kwargs):
        self.envname: str = kwargs.get('envname', 'prod')
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

        self.register_model('Env')
        self.register_instance('Env', path=self.envfile)
        self.env = self.obj(f'instances/Env/{self.envname}')
        for model in self.env.models:
            self.register_model(model)

    def _filecfgs(self, what: str, dir: str):
        files = parser(dir)
        if not files.get('contents'):
            raise ValueError(f'No model file contents seen in {dir}')
        fconfigs = {f"{what}/{i['kind']}".lower(): i for i in files['contents']}
        if fconfigs:
            self._configs.update(fconfigs)

    def register_model(self, model: str) -> Dict[str, Any]:
        clscfg = self._configs.get(f'models/{model}'.lower())
        assert clscfg, f'{model} Config not found'
        cls = dynamic_model(clscfg)
        self._ns_init('models', cls)

    def register_instance(self, model: Optional[str] = None, **kwargs) -> Any:
        model = model or kwargs.get('kind')
        assert model, 'Model not specified'
        cls = self.model(model)
        vars = parser(**kwargs)
        vars.update(augment('instances', model, vars))
        try:
            inst = cls(**vars)
            self._ns_init('instances', inst)
            return inst
        except Exception as e:
            log.error(f'Error registering instance {model}: {e}')
            raise e

    @classmethod
    def set_env(cls, envname: str) -> Any:
        envmf = f'{BLUEPRINTS}/env.yaml'
        env_cls = dynamic_model(parser(envmf))
        assert env_cls, f'Failed to create Env Model from {envmf}'
        envcf = f'{CONFIGS}/env.{envname}.yaml'
        vars = parser(envcf)
        vars.update(augment('instances', 'Env', vars))
        env = env_cls(**vars)
        assert env, f'Failed to create Env from {envcf}'
        return env

    def _ns_init(self, what: str, obj: Any) -> None:
        # TODO This WOULD have uid tag and environment specific id
        oid = obj.__class__.__name__
        if what == 'models':
            oid = obj.__name__.lower()
            self.models[oid] = obj
        elif what == 'instances':
            oid = f'{obj.__class__.__name__}/{obj.ns}'.lower()
            oid = obj.nsid
            self.instances[oid] = obj
        ns_id = f'{what}/{oid}'
        self.ns[ns_id] = obj
        log.info(f'Initialized {what} NS => {ns_id}')

    def locator(self, nskey: str) -> Any:
        log.info(f'Looking up {nskey} in Registry')
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
        cls = self.locator(f'models/{clstr}')
        assert (
            cls
        ), f'Class {clstr} not found, Registred =>\n{self.models.keys()}'
        return cls

    def obj(self, objkey: str) -> Any:
        return self.locator(objkey)

    instance = obj

    def __repr__(self):
        data = [
            ['Env', ic(self.env)],
            ['Models', ic(self.models)],
            ['Instances', ic(self.instances)],
            ['Callables', ic(self.callables)],
        ]
        sep = '-' * 60 + '\n'
        return sep.join(f'{header} ->{content}\n' for header, content in data)
