from __future__ import annotations

import json

import pytest

from team.exceptions import (
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from team.models import TeamCreate, TeamUpdate
from team.store import make_member_key


class TestTeamCreate:
    def test_create_and_get(self, team_service):
        team = team_service.create_team(
            TeamCreate(
                members=["p001", "p002", "p003"],
                aliases=["测试队"],
            )
        )
        assert team.id.startswith("t")
        assert team.id == "t001"  # sequential, 3-digit padded
        assert team.member_key == "p001|p002|p003"
        assert team.size == 3
        assert team.aliases == ["测试队"]

        fetched = team_service.get_team(team.id)
        assert fetched.id == team.id
        assert fetched.members == ["p001", "p002", "p003"]

    def test_create_duplicate_member_key_rejected(self, team_service):
        team_service.create_team(
            TeamCreate(members=["p001", "p002"], aliases=["队A"])
        )
        with pytest.raises(TeamAlreadyExistsError):
            team_service.create_team(
                TeamCreate(members=["p002", "p001"], aliases=["队B"])
            )

    def test_create_duplicate_members_rejected(self, team_service):
        with pytest.raises(ValueError, match="重复"):
            TeamCreate(members=["p001", "p001", "p002"], aliases=["重复队"])

    def test_member_order_independent(self, team_service):
        t1 = team_service.create_team(
            TeamCreate(members=["p003", "p001", "p002"], aliases=["任意顺序"])
        )
        assert t1.member_key == "p001|p002|p003"

    def test_single_member(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001"], aliases=["单挑"])
        )
        assert team.size == 1
        assert team.member_key == "p001"

    def test_two_members(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001", "p002"], aliases=["双打"])
        )
        assert team.size == 2
        assert team.member_key == "p001|p002"

    def test_four_members_rejected(self):
        with pytest.raises(ValueError):
            TeamCreate(members=["p001", "p002", "p003", "p004"], aliases=["四人队"])


class TestTeamQuery:
    def test_list_all(self, team_service):
        team_service.create_team(TeamCreate(members=["p001"], aliases=["A"]))
        team_service.create_team(TeamCreate(members=["p002"], aliases=["B"]))
        assert len(team_service.list_teams()) == 2

    def test_get_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.get_team("t_nonexistent")

    def test_find_by_members(self, team_service):
        team_service.create_team(TeamCreate(members=["p001", "p002"], aliases=["测试"]))
        found = team_service.find_by_members(["p002", "p001"])
        assert found is not None
        assert found.aliases == ["测试"]

    def test_find_by_members_not_found(self, team_service):
        assert team_service.find_by_members(["p999"]) is None


class TestAddAlias:
    def test_add_alias(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001", "p002"], aliases=["初始名"])
        )
        updated = team_service.add_alias(team.id, "新别名")
        assert updated.aliases == ["初始名", "新别名"]

    def test_add_alias_duplicate_ignored(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001"], aliases=["唯一"])
        )
        updated = team_service.add_alias(team.id, "唯一")
        assert updated.aliases == ["唯一"]

    def test_add_alias_empty_rejected(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001"], aliases=["A"])
        )
        with pytest.raises(TeamValidationError, match="别名不能为空"):
            team_service.add_alias(team.id, "   ")

    def test_add_alias_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.add_alias("t_nonexistent", "x")


class TestTeamUpdate:
    def test_add_alias_via_update(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], aliases=["初始名"]))
        updated = team_service.update_team(team.id, TeamUpdate(alias="新队名"))
        assert "初始名" in updated.aliases
        assert "新队名" in updated.aliases

    def test_duplicate_alias_not_added(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], aliases=["唯一"]))
        updated = team_service.update_team(team.id, TeamUpdate(alias="唯一"))
        assert updated.aliases == ["唯一"]

    def test_update_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.update_team("t_nonexistent", TeamUpdate(alias="x"))

    def test_update_no_fields(self, team_service):
        from team.models import TeamUpdate
        with pytest.raises(ValueError, match="至少提供"):
            TeamUpdate()


class TestTeamDelete:
    def test_delete(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], aliases=["待删除"]))
        team_id = team.id
        removed = team_service.delete_team(team_id)
        assert removed.id == team_id
        with pytest.raises(TeamNotFoundError):
            team_service.get_team(team_id)

    def test_delete_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.delete_team("t_nonexistent")


class TestTeamPersistence:
    def test_persists_to_json(self, temp_team_store, team_service):
        team = team_service.create_team(TeamCreate(members=["p001", "p002"], aliases=["持久化"]))
        raw = json.loads(temp_team_store.raw_path.read_text(encoding="utf-8"))
        assert len(raw) == 1
        assert raw[0]["id"] == team.id
        assert raw[0]["member_key"] == "p001|p002"
        assert raw[0]["members"] == ["p001", "p002"]
        assert raw[0]["size"] == 2
        assert raw[0]["aliases"] == ["持久化"]

    def test_persists_multiple(self, team_service):
        team_service.create_team(TeamCreate(members=["p001"], aliases=["A"]))
        team_service.create_team(TeamCreate(members=["p002"], aliases=["B"]))
        assert len(team_service.list_teams()) == 2


class TestMemberKeyAndId:
    def test_make_member_key_sorts(self):
        assert make_member_key(["p003", "p001", "p002"]) == "p001|p002|p003"

    def test_next_id_sequential(self, team_service):
        """Team IDs should be sequential: t001, t002, ..."""
        t1 = team_service.create_team(
            TeamCreate(members=["p001"], aliases=["A"])
        )
        t2 = team_service.create_team(
            TeamCreate(members=["p002"], aliases=["B"])
        )
        t3 = team_service.create_team(
            TeamCreate(members=["p003"], aliases=["C"])
        )
        assert t1.id == "t001"
        assert t2.id == "t002"
        assert t3.id == "t003"

    def test_next_id_skips_existing(self, team_service):
        """next_id should scan existing IDs and find the next available."""
        team_service.create_team(
            TeamCreate(members=["p001"], aliases=["A"])
        )
        team_service.create_team(
            TeamCreate(members=["p002"], aliases=["B"], id="t005")
        )
        t3 = team_service.create_team(
            TeamCreate(members=["p003"], aliases=["C"])
        )
        assert t3.id == "t006"


class TestTeamApi:
    def test_api_delegates_to_service(self, temp_team_store):
        from team import api

        api.configure_store(temp_team_store)
        team = api.create_team(TeamCreate(members=["p001"], aliases=["API测试"]))
        assert team.aliases == ["API测试"]

        fetched = api.get_team(team.id)
        assert fetched.id == team.id

        found = api.find_by_members(["p001"])
        assert found is not None
        assert found.id == team.id

        updated = api.update_team(team.id, TeamUpdate(alias="新名"))
        assert updated.aliases == ["API测试", "新名"]

        teams = api.list_teams()
        assert len(teams) == 1

        api.delete_team(team.id)
        assert len(api.list_teams()) == 0

    def test_api_per_call_store_isolation(self, temp_team_store):
        from team import api

        api.create_team(TeamCreate(members=["p001"], aliases=["A"]), store=temp_team_store)
        teams = api.list_teams(store=temp_team_store)
        assert len(teams) == 1