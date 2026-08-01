class ContestError(Exception):
    """比赛模块基础异常。"""


class ContestNotFoundError(ContestError):
    def __init__(self, contest_id: str) -> None:
        super().__init__(f"比赛不存在: {contest_id}")
        self.contest_id = contest_id


class ContestValidationError(ContestError):
    pass
