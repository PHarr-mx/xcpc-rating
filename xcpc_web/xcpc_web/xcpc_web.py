import reflex as rx
import reflex_local_auth

from xcpc_web.pages.index import index
from xcpc_web.pages.login import login
from xcpc_web.pages.register import register
from xcpc_web.states.board import BoardState

app = rx.App()
app.add_page(index, route="/", on_load=BoardState.on_load)
app.add_page(login, route=reflex_local_auth.routes.LOGIN_ROUTE, title="登录")
app.add_page(register, route=reflex_local_auth.routes.REGISTER_ROUTE, title="注册")
