import reflex as rx

from xcpc_web.pages.index import index
from xcpc_web.states.board import BoardState

app = rx.App()
app.add_page(index, on_load=BoardState.on_load)
