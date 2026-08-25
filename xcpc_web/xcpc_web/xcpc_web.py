import reflex as rx
import reflex_local_auth

from xcpc_web.pages.admin.audit import admin_audit
from xcpc_web.pages.admin.contests import admin_contests
from xcpc_web.pages.admin.imports import admin_import
from xcpc_web.pages.admin.overview import admin_overview
from xcpc_web.pages.admin.players import admin_players
from xcpc_web.pages.admin.teams import admin_teams
from xcpc_web.pages.admin.users import admin_users
from xcpc_web.pages.index import index
from xcpc_web.pages.login import login
from xcpc_web.pages.profile import profile
from xcpc_web.pages.register import register
from xcpc_web.states.admin.audit import AdminAuditState
from xcpc_web.states.admin.contests import AdminContestsState
from xcpc_web.states.admin.imports import AdminImportState
from xcpc_web.states.admin.overview import AdminOverviewState
from xcpc_web.states.admin.players import AdminPlayersState
from xcpc_web.states.admin.teams import AdminTeamsState
from xcpc_web.states.admin.users import AdminUsersState
from xcpc_web.states.board import BoardState
from xcpc_web.states.profile import ProfileState

app = rx.App()
app.add_page(index, route="/", on_load=BoardState.on_load)
app.add_page(login, route=reflex_local_auth.routes.LOGIN_ROUTE, title="登录")
app.add_page(register, route=reflex_local_auth.routes.REGISTER_ROUTE, title="注册")
app.add_page(profile, route="/profile", title="个人资料", on_load=ProfileState.on_load)
app.add_page(
    reflex_local_auth.require_login(admin_overview),
    route="/admin",
    title="后台概览",
    on_load=AdminOverviewState.on_load,
)
app.add_page(
    reflex_local_auth.require_login(admin_users),
    route="/admin/users",
    title="用户与绑定审批",
    on_load=AdminUsersState.on_load,
)
app.add_page(
    reflex_local_auth.require_login(admin_players),
    route="/admin/players",
    title="选手管理",
    on_load=AdminPlayersState.on_load,
)

app.add_page(
    reflex_local_auth.require_login(admin_teams),
    route="/admin/teams",
    title="队伍管理",
    on_load=AdminTeamsState.on_load,
)

app.add_page(
    reflex_local_auth.require_login(admin_contests),
    route="/admin/contests",
    title="比赛管理",
    on_load=AdminContestsState.on_load,
)
app.add_page(
    reflex_local_auth.require_login(admin_audit),
    route="/admin/audit",
    title="审计日志",
    on_load=AdminAuditState.on_load,
)

app.add_page(
    reflex_local_auth.require_login(admin_import),
    route="/admin/import",
    title="在线正式赛导入",
    on_load=AdminImportState.on_load,
)
