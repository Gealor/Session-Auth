from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nickname: str = Field(examples=["Gealor"])
    email: EmailStr = Field(examples=["example@test.com"])


class UserRead(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    deleted_at: datetime | None


class UserRegister(UserBase):
    password: str = Field(min_length=8, examples=["ivan_craft7869"])


class UserRegisterWithRepeatPassword(UserRegister):
    repeat_password: str = Field(examples=["ivan_craft7869"])


class UserWithWorkInformation(UserRead, UserRegister):
    pass


class UserUpdate(BaseModel):
    nickname: str | None = None


class UserDelete(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_active: bool = False
    deleted_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))


class UserChangePassword(BaseModel):
    password: str = Field(examples=["ivan_craft7869"])


# Auth
class LoginCredentials(BaseModel):
    email: EmailStr = Field(examples=["example@test.com"])
    password: str = Field(examples=["ivan_craft7869"])

