class PlayerError(Exception):
    """选手模块基础异常。"""


class PlayerNotFoundError(PlayerError):
    def __init__(self, player_id: str) -> None:
        super().__init__(f"选手不存在: {player_id}")
        self.player_id = player_id


class PlayerAlreadyExistsError(PlayerError):
    def __init__(self, player_id: str) -> None:
        super().__init__(f"选手 ID 已存在: {player_id}")
        self.player_id = player_id


class PlayerValidationError(PlayerError):
    pass
