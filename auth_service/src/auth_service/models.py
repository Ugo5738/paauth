from typing import List, Optional
from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class UserTokenData(BaseModel):
    user_id: str = Field(..., alias="sub")
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    exp: int


class AppClientTokenData(BaseModel):
    client_id: str = Field(..., alias="sub")
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    exp: int
    iss: Optional[str] = None
    aud: Optional[str] = None
