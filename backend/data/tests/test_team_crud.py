from __future__ import annotations

import json

import pytest

from team.exceptions import (
    TeamAlreadyExistsError,
    TeamNotFoundError,
    TeamValidationError,
)
from team.models import TeamCreate, TeamUpdate
from team.store import make_member_key, make_team_id


class TestTeamCreate:
    def test_create_and_get(self, team_service):
        team = team_service.create_team(
            TeamCreate(
                members=["p001", "p002", "p003"],
                display_name="测试队",
            )
        )
        assert team.id.startswith("t_")
        assert len(team.id) == 10  # t_ + 8 hex
        assert team.member_key == "p001|p002|p003"
        assert team.size == 3
        assert team.names == ["测试队"]
        assert team.display_name == "测试队"
        assert team.is_school_team is True
        assert team.first_seen is not None
        assert team.last_seen is not None

        fetched = team_service.get_team(team.id)
        assert fetched.id == team.id
        assert fetched.members == ["p001", "p002", "p003"]

    def test_create_duplicate_member_key_rejected(self, team_service):
        team_service.create_team(
            TeamCreate(members=["p001", "p002"], display_name="队A")
        )
        with pytest.raises(TeamAlreadyExistsError):
            team_service.create_team(
                TeamCreate(members=["p002", "p001"], display_name="队B")
            )

    def test_create_duplicate_members_rejected(self, team_service):
        with pytest.raises(ValueError, match="重复"):
            TeamCreate(members=["p001", "p001", "p002"], display_name="重复队")

    def test_member_order_independent(self, team_service):
        t1 = team_service.create_team(
            TeamCreate(members=["p003", "p001", "p002"], display_name="任意顺序")
        )
        assert t1.member_key == "p001|p002|p003"

    def test_single_member(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001"], display_name="单挑")
        )
        assert team.size == 1
        assert team.member_key == "p001"

    def test_two_members(self, team_service):
        team = team_service.create_team(
            TeamCreate(members=["p001", "p002"], display_name="双打")
        )
        assert team.size == 2
        assert team.member_key == "p001|p002"

    def test_four_members_rejected(self):
        with pytest.raises(ValueError):
            TeamCreate(members=["p001", "p002", "p003", "p004"], display_name="四人队")


class TestTeamQuery:
    def test_list_all(self, team_service):
        team_service.create_team(TeamCreate(members=["p001"], display_name="A"))
        team_service.create_team(TeamCreate(members=["p002"], display_name="B"))
        assert len(team_service.list_teams()) == 2

    def test_list_school_only(self, team_service):
        team_service.create_team(TeamCreate(members=["p001"], display_name="校内", is_school_team=True))
        team_service.create_team(TeamCreate(members=["p002"], display_name="校外", is_school_team=False))
        school = team_service.list_teams(is_school_team=True)
        assert len(school) == 1
        assert school[0].display_name == "校内"
        non_school = team_service.list_teams(is_school_team=False)
        assert len(non_school) == 1
        assert non_school[0].display_name == "校外"

    def test_get_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.get_team("t_nonexistent")

    def test_find_by_members(self, team_service):
        team_service.create_team(TeamCreate(members=["p001", "p002"], display_name="测试"))
        found = team_service.find_by_members(["p002", "p001"])
        assert found is not None
        assert found.display_name == "测试"

    def test_find_by_members_not_found(self, team_service):
        assert team_service.find_by_members(["p999"]) is None


class TestTeamUpdate:
    def test_add_name(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], display_name="初始名"))
        updated = team_service.update_team(team.id, TeamUpdate(name="新队名"))
        assert "初始名" in updated.names
        assert "新队名" in updated.names
        assert updated.display_name == "初始名"  # unchanged

    def test_change_display_name(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], display_name="旧"))
        updated = team_service.update_team(team.id, TeamUpdate(display_name="新"))
        assert updated.display_name == "新"

    def test_duplicate_name_not_added(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], display_name="唯一"))
        updated = team_service.update_team(team.id, TeamUpdate(name="唯一"))
        assert updated.names == ["唯一"]

    def test_update_not_found(self, team_service):
        with pytest.raises(TeamNotFoundError):
            team_service.update_team("t_nonexistent", TeamUpdate(display_name="x"))

    def test_update_no_fields(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], display_name="x"))
        from team.models import TeamUpdate
        with pytest.raises(ValueError, match="至少提供"):
            TeamUpdate()


class TestTeamDelete:
    def test_delete(self, team_service):
        team = team_service.create_team(TeamCreate(members=["p001"], display_name="待删除"))
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
        team = team_service.create_team(TeamCreate(members=["p001", "p002"], display_name="持久化"))
        raw = json.loads(temp_team_store.raw_path.read_text(encoding="utf-8"))
        assert len(raw) == 1
        assert raw[0]["id"] == team.id
        assert raw[0]["member_key"] == "p001|p002"
        assert raw[0]["members"] == ["p001", "p002"]
        assert raw[0]["size"] == 2

    def test_persists_multiple(self, team_service):
        team_service.create_team(TeamCreate(members=["p001"], display_name="A"))
        team_service.create_team(TeamCreate(members=["p002"], display_name="B"))
        assert len(team_service.list_teams()) == 2


class TestMemberKeyAndId:
    def test_make_member_key_sorts(self):
        assert make_member_key(["p003", "p001", "p002"]) == "p001|p002|p003"

    def test_make_team_id_deterministic(self):
        key = "p001|p002|p003"
        assert make_team_id(key) == make_team_id(key)

    def test_make_team_id_different_for_different_members(self):
        id1 = make_team_id("p001|p002")
        id2 = make_team_id("p001|p003")
        assert id1 != id2

    def test_team_id_format(self):
        team = TeamCreate(members=["p001"], display_name="x")
        tid = make_team_id(make_member_key(team.members))
        assert tid.startswith("t_")
        assert len(tid) == 10


class TestTeamApi:
    def test_api_delegates_to_service(self, temp_team_store):
        from team import api

        api.configure_store(temp_team_store)
        team = api.create_team(TeamCreate(members=["p001"], display_name="API测试"))
        assert team.display_name == "API测试"

        fetched = api.get_team(team.id)
        assert fetched.id == team.id

        found = api.find_by_members(["p001"])
        assert found is not None
        assert found.id == team.id

        updated = api.update_team(team.id, TeamUpdate(display_name="新名"))
        assert updated.display_name == "新名"

        teams = api.list_teams()
        assert len(teams) == 1

        api.delete_team(team.id)
        assert len(api.list_teams()) == 0

    def test_api_per_call_store_isolation(self, temp_team_store):
        from team import api

        api.create_team(TeamCreate(members=["p001"], display_name="A"), store=temp_team_store)
        teams = api.list_teams(store=temp_team_store)
        assert len(teams) == 1