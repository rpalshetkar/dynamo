from pprint import pprint as pp

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    create_model,
    field_validator,
    model_validator,
)


def pydantic_model(name: str, fields: dict):
    processed_fields = {}

    for field_name, field_type in fields.items():
        if isinstance(field_type, dict):
            nested_model = pydantic_model(field_name.title(), field_type)
            processed_fields[field_name] = create_field(
                field_name, nested_model
            )
        else:
            processed_fields[field_name] = create_field(field_name, field_type)

    the_model = create_model(name, **processed_fields)

    @model_validator(mode='before')
    def validate_fields(cls, value, field):
        if isinstance(value, int):
            if not (1 <= value <= 10):
                raise ValueError(
                    f'{field.name.capitalize()} must be between 1 and 10'
                )
        return value

    return the_model


def create_field(name: str, field_type) -> tuple:
    return field_type, Field(
        title=name.title(),
        description=f'Field {name}',
        example=None,
        required=False,
        default=None,
        __validators__=None,
    )


PFIELDS = {
    'name': str,
    'age': int,
    'scores': list[float],
    'address': {'street': str, 'city': str, 'zipcode': str},
}
PersonDelegate = pydantic_model('PersonDelegate', PFIELDS)


def test_dynamic_subclass():
    BaseUser = create_model(
        'BaseUser',
        id=(int, ...),
        name=(str, 'Jane Doe'),
    )
    StudentUser = create_model(
        'StudentUser', __base__=BaseUser, semester=(int, ...)
    )
    student_instance = StudentUser(id=1, name='Alice', semester=2)
    pp(student_instance)


test_dynamic_subclass()
