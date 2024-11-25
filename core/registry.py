from pathlib import Path
from typing import Any, Dict, Optional

from icecream import ic
from pydantic import BaseModel, Field

from xds.core.dynamo import Dynamo
from xds.utils.io import io_path
from xds.utils.logger import log


class Registry(BaseModel):
    factory: Any = Field(default_factory=lambda: Dynamo())
    ns: Dict[str, Any] = Field(default_factory=dict)
    models: Dict[str, Any] = Field(default_factory=dict)
    instances: Dict[str, Any] = Field(default_factory=dict)
    env: Any = Field(init=False)

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Registry, cls).__new__(cls)
        return cls._instance

    def __attrs_post_init__(self):
        self._env_init()
        models = self.env.models.split(',')
        for model in models:
            log.info(f'Initializing Model {model}')
            self._model_init(model, dir=self.env.blueprints)

    def _env_init(self) -> Any:
        mdir = 'xds/catalogue/blueprints'
        self.config = 'xds/configs'
        self._model_init('env', dir=mdir)
        file = f'{self.config}/env.prod.yaml'
        log.info(f'Booting Environment from {file}')
        env = self.instance(file=file)
        self.env = env
        return env

    def _model_init(self, model: str, **kwargs: Dict[str, Any]) -> Any:
        if 'file' not in kwargs:
            kwargs['file'] = f'{model}.yaml'
        fpath = io_path(**kwargs)
        cls = self.factory.d2c(file=fpath)
        self._ns_init('models', cls)

    def instance(self, **kwargs: Dict[str, Any]) -> Any:
        file = kwargs.get('file')
        if file and not Path.exists(Path(kwargs['file'])):
            kwargs['file'] = io_path(dir=self.config, file=file)
            log.info(f'Initializing from {kwargs["file"]}')
        inst = self.factory.instance(**kwargs)
        self._ns_init('instances', inst)
        return inst

    def _inst_file(self, **kwargs: Dict[str, Any]) -> str:
        config: str = kwargs.get('config')
        if 'file' in kwargs:
            file: str = kwargs.get('file')
            dir = (
                config
                if config
                else (getattr(self.env, 'config', None) if self.env else None)
            )
            fpath = io_path(dir=dir, file=file)
            kwargs['file'] = fpath
        return fpath

    def _ns_init(self, what: str, obj: Any) -> None:
        """
        This could have uid tag and environment specific id
        """
        oid = obj.__class__.__name__
        if what == 'models':
            oid = obj.__name__.lower()
            self.models[oid] = obj
        elif what == 'instances':
            oid = f'{obj.__class__.__name__}/{obj.ns}'.lower()
            self.instances[oid] = obj
        ns_id = f'{what}/{oid}'
        self.ns[ns_id] = obj
        obj.nsid = ns_id
        log.info(f'Initialized {what} NS => {ns_id}')

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
        cls = self.locator(f'models/{clstr}')
        assert cls, f'Class {clstr} not found in registry, Registred =>\n{self.models.keys()}'
        return cls

    def obj(self, objkey: str) -> Any:
        return self.locator(objkey)
