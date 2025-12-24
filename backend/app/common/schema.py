# app/common/schemas.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,   # snake_case → camelCase 변환
        populate_by_name=True,      # 원래 이름(snake)으로도 접근 가능
        from_attributes=True,       # SQLAlchemy 모델에서 직접 변환 허용
    )