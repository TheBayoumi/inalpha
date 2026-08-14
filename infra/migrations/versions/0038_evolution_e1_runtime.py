from alembic import op

from evolution_e1_candidate_sql import CANDIDATE_DOWN, CANDIDATE_UP
from evolution_e1_run_sql import RUN_DOWN, RUN_UP

revision = "0038"
down_revision = "0037"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(RUN_UP)
    op.execute(CANDIDATE_UP)


def downgrade() -> None:
    op.execute(CANDIDATE_DOWN)
    op.execute(RUN_DOWN)
