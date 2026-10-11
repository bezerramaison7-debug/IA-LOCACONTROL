from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$"),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Payload):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class PasswordChange(Payload):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class ProfileUpdate(Payload):
    name: Name


class UserCreate(Payload):
    username: Username
    name: Name
    password: Password
    role_codes: list[str] = Field(min_length=1, max_length=5)


class UserUpdate(Payload):
    name: Name
    is_active: bool
    role_codes: list[str] = Field(min_length=1, max_length=5)


class PasswordReset(Payload):
    new_password: Password


class RoleUpdate(Payload):
    permission_codes: list[str] = Field(max_length=30)
