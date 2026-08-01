class TeamError(Exception):
    """队伍模块基础异常。"""


class TeamNotFoundError(TeamError):
    def __init__(self, team_id: str) -> None:
        super().__init__(f"队伍不存在: {team_id}")
        self.team_id = team_id


class TeamAlreadyExistsError(TeamError):
    def __init__(self, member_key: str) -> None:
        super().__init__(f"队员组合已存在: {member_key}")
        self.member_key = member_key


class TeamValidationError(TeamError):
    pass