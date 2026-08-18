import reflex as rx

from xcpc_web.components.layout import page_shell
from xcpc_web.components.period_selector import period_selector
from xcpc_web.components.board_table import board_table
from xcpc_web.states.board import BoardState


def index() -> rx.Component:
    return page_shell(
        rx.vstack(
            rx.heading("XCPC Rating 榜单", size="7"),
            period_selector(),
            board_table(),
            spacing="6",
            width="100%",
        ),
    )
