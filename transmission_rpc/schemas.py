from pydantic import BaseModel


class RpcResponse(BaseModel):
    result: str
    tag: int
    arguments: dict
