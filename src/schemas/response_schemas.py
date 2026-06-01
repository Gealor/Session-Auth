from pydantic import BaseModel


class ResponseBaseSchema(BaseModel):
    msg: str


class ResponseSchema(ResponseBaseSchema):
    pass
