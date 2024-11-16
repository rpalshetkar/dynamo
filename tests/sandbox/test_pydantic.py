import re
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pprint import pp
from typing import Any, Dict, List, Optional

import yaml
from icecream import ic
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    PositiveInt,
    ValidationError,
    condecimal,
    conint,
    create_model,
    field_validator,
)

from tests.sandbox.utils.field import field_spec

ic.configureOutput(prefix='DEBUG:', includeContext=True)


def infer_type(field_name: str, value: Any) -> Any:
    type_mapping = {
        int: lambda v: (int, ...),
        float: lambda v: (float, ...),
        Decimal: lambda v: (condecimal(gt=0), ...),
        bool: lambda v: (bool, ...),
        dict: create_model_from_dict,
        list: lambda v: (List[Dict[str, Any]], ...)
        if v and isinstance(v[0], dict)
        else (List[Any], ...),
    }

    return type_mapping.get(type(value), lambda v: (Optional[Any], None))(value)


def create_model_from_dict(data: Dict[str, Any]) -> Any:
    fields = {}
    cls_name = data.get('kind', 'DynamicModel').title()
    print(f'Creating model for {cls_name}')
    for key, value in data.items():
        if isinstance(value, str):
            _ = ic(field_spec(value))
            return (EmailStr, ...) if '@' in value else (str, ...)
        if isinstance(value, dict):
            field_type = (create_model_from_dict(value), ...)
        else:
            field_type = infer_type(key, value)
        fields[key] = field_type
    model = create_model(cls_name, **fields)
    """
    for key in [k for k in ['dt', 'date', 'time'] if k in fields.keys()]:

        @field_validator(key, pre=True)
        def validate_date(cls, v):
            if isinstance(v, str):
                return datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
            else:
                return datetime.strptime(v, '%Y-%m-%d').date()
            return v

        setattr(model, f'validate_{key}', validate_date)
    """

    return model


def test_pydantic_model():
    user_data_yaml = """
    kind: User
    id: int=1
    name: str=John Doe#req#key
    email: john.doe@example.com
    age: int=30
    balance: float=100.50
    role: enum=ro,rw,adm
    addresses:
      - street: 123 Main St
        kind: Address
        city: Anytown
        zip_code: 12345
    tags:
      - premium
      - newsletter
    score: 100
    preference:
      kind: Preference
      theme: dark
      notifications: true
      language: en
    """

    user_data = ic(yaml.safe_load(user_data_yaml))

    UserModel = create_model_from_dict(user_data)

    try:
        user_instance = UserModel(**user_data)
        print(user_instance)

        print('\nGenerated User Model Schema with Metadata:')
        pp(user_instance.model_json_schema())

    except ValidationError as e:
        print(e.json())
