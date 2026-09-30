"""rating algorithm bump to atcoder_v1

Revision ID: 0004_atcoder_v1
Revises: 0003_unify_contest
Create Date: 2026-10-01

P-U2 榜单切换 AtCoder 式重放引擎：meta.rating_algorithm 由 placeholder_v0
升版为 atcoder_v1（纯数据更新，无 DDL 变更）。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0004_atcoder_v1'
down_revision = '0003_unify_contest'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE meta SET rating_algorithm = 'atcoder_v1' WHERE rating_algorithm = 'placeholder_v0'")


def downgrade() -> None:
    op.execute("UPDATE meta SET rating_algorithm = 'placeholder_v0' WHERE rating_algorithm = 'atcoder_v1'")
