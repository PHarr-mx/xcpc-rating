from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

OJPlatform = Literal["codeforces", "atcoder", "luogu", "nowcoder"]

STATUS_LABELS: dict[str, str] = {
    "active": "现役",
    "retired": "退役",
    "left": "离队",
}


class PlayerStatus(str, Enum):
    active = "active"
    retired = "retired"
    left = "left"


class OJAccount(BaseModel):
    platform: OJPlatform
    handle: str = Field(min_length=1)
    user_id: str | None = None


class PlayerBase(BaseModel):
    name: str = Field(min_length=1)
    handle: str | None = None
    grade: int = Field(ge=0, le=2035)
    status: PlayerStatus = PlayerStatus.active
    oj_accounts: list[OJAccount] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("handle")
    @classmethod
    def strip_handle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("aliases")
    @classmethod
    def dedupe_aliases(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result


class PlayerCreate(PlayerBase):
    id: str | None = None


class PlayerUpdate(BaseModel):
    name: str | None = None
    handle: str | None = None
    grade: int | None = Field(default=None, ge=0, le=2035)
    status: PlayerStatus | None = None
    oj_accounts: list[OJAccount] | None = None
    aliases: list[str] | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> PlayerUpdate:
        if not any(
            getattr(self, field) is not None
            for field in ("name", "handle", "grade", "status", "oj_accounts", "aliases")
        ):
            raise ValueError("至少提供一个待更新字段")
        return self


class Player(PlayerBase):
    id: str
    grade_label: str | None = None
    status_label: str | None = None
    created_at: date | None = None
    updated_at: date | None = None

    @property
    def is_visible(self) -> bool:
        return self.status != PlayerStatus.left

    def with_derived_fields(self, *, today: date | None = None) -> Player:
        today = today or date.today()
        return self.model_copy(
            update={
                "grade_label": "未设置" if self.grade == 0 else f"{self.grade}级",
                "status_label": STATUS_LABELS[self.status.value],
                "updated_at": today,
            }
        )

    def to_raw_dict(self) -> dict:
        data = self.model_dump(mode="json", exclude={"grade_label", "status_label", "created_at", "updated_at"})
        if not data.get("handle"):
            data.pop("handle", None)
        if not data.get("aliases"):
            data.pop("aliases", None)
        return data
