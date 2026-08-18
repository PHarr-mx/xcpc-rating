"""Board table component."""

import reflex as rx
from ..states.board import BoardState


def board_table() -> rx.Component:
    return rx.vstack(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Rank"),
                    rx.table.column_header_cell("Player ID"),
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Grade"),
                    rx.table.column_header_cell("Rating"),
                    rx.table.column_header_cell("Events"),
                    rx.table.column_header_cell("Recent Delta"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    BoardState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(row["rank"]),
                        rx.table.cell(row["player_id"]),
                        rx.table.cell(row["name"]),
                        rx.table.cell(row["grade_label"]),
                        rx.table.cell(f'{row["rating"]:.1f}'),
                        rx.table.cell(row["event_count"]),
                        rx.table.cell(f'{row["delta_recent"]:.1f}'),
                    ),
                ),
            ),
            width="100%",
        ),
        rx.cond(
            BoardState.meta,
            rx.text(
                f'Algorithm: {BoardState.meta["algorithm"]} · Data Version: {BoardState.meta["data_version"]} · Generated: {BoardState.meta["generated_at"]}',
                size="1",
                color=rx.color("gray", 10),
            ),
        ),
        spacing="4",
        width="100%",
    )
