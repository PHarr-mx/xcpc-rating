from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator


class TeamBase(BaseModel):
    members: list[str] = Field(min_length=1, max_length=3)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("members")
    @classmethod
    def members_no_duplicates(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("队员列表中存在重复 player_id")
        return value

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


class TeamCreate(TeamBase):
    """新建队伍参数。"""

    id: str | None = None


class TeamUpdate(BaseModel):
    """更新队伍参数。"""

    alias: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> TeamUpdate:
        if self.alias is None:
            raise ValueError("至少提供一个待更新字段")
        return self


class Team(TeamBase):
    id: str
    member_key: str
    size: int
    created_at: date | None = None
    updated_at: date | None = None

    def with_derived_fields(self, *, today: date | None = None) -> Team:
        today = today or date.today()
        return self.model_copy(
            update={
                "size": len(self.members),
                "updated_at": today,
            }
        )

    def to_raw_dict(self) -> dict:
        data = self.model_dump(
            mode="json",
            exclude={"created_at", "updated_at"},
        )
        if not data.get("aliases"):
            data.pop("aliases", None)
        return data