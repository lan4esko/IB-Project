from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ActCreate(BaseModel):
    code: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    revision: str = Field(min_length=1, max_length=100)
    effective_from: date | None = None
    source_uri: str | None = Field(default=None, max_length=1000)


class ActView(ActCreate, View):
    id: int
    created_at: datetime


class RequirementCreate(BaseModel):
    act_id: int = Field(gt=0)
    clause: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=20000)
    applicability: str = Field(default="Не определена", max_length=4000)


class RequirementView(RequirementCreate, View):
    id: int
    created_at: datetime


Stage = Literal["planning", "design", "commissioning", "operation", "suspended", "decommissioned"]


class ObjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    type: str = Field(default="other", min_length=1, max_length=100)
    stage: Stage = "planning"
    owner: str | None = Field(default=None, max_length=200)


class ObjectView(ObjectCreate, View):
    id: int
    created_at: datetime


Status = Literal["planned", "in_progress", "blocked", "awaiting_review", "completed", "cancelled"]


class MeasureCreate(BaseModel):
    requirement_id: int = Field(gt=0)
    info_object_id: int = Field(gt=0)
    action: str = Field(min_length=1, max_length=20000)
    owner: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    status: Status = "planned"
    evidence_uri: str | None = Field(default=None, max_length=1000)
    reviewed_by: str | None = Field(default=None, max_length=200)


class MeasureUpdate(BaseModel):
    action: str | None = Field(default=None, min_length=1, max_length=20000)
    owner: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: date | None = None
    status: Status | None = None
    evidence_uri: str | None = Field(default=None, max_length=1000)
    reviewed_by: str | None = Field(default=None, max_length=200)


class MeasureView(MeasureCreate, View):
    id: int
    created_at: datetime


Role = Literal["admin", "security", "operator", "auditor", "viewer"]

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)

class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,80}$")
    password: str = Field(min_length=12, max_length=128)
    role: Role = "viewer"

class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None

class UserView(View):
    id: int
    username: str
    role: Role
    is_active: bool
    created_at: datetime

class GrantCreate(BaseModel):
    permission: Literal["read", "write"]

class GrantView(View):
    id: int
    object_id: int
    user_id: int
    permission: Literal["read", "write"]


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
