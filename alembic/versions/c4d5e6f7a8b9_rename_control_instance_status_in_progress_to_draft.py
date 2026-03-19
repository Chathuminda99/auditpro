"""rename control instance status in_progress to draft

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-19 00:01:00.000000

- controlinstancestatus: IN_PROGRESS → DRAFT
"""
from alembic import op


revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    # Add DRAFT value — requires committed transaction
    op.execute("COMMIT")
    op.execute("ALTER TYPE controlinstancestatus ADD VALUE IF NOT EXISTS 'draft'")
    op.execute("BEGIN")

    # Migrate existing IN_PROGRESS rows to DRAFT
    op.execute(
        "UPDATE session_control_instances SET status = 'draft'::controlinstancestatus "
        "WHERE status::text = 'in_progress'"
    )
    op.execute("COMMIT")
    op.execute("BEGIN")

    # Recreate enum without in_progress
    op.execute(
        "CREATE TYPE controlinstancestatus_new AS ENUM ('not_started', 'draft', 'pass', 'fail', 'na')"
    )
    op.execute(
        "ALTER TABLE session_control_instances ALTER COLUMN status DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE session_control_instances ALTER COLUMN status TYPE controlinstancestatus_new "
        "USING status::text::controlinstancestatus_new"
    )
    op.execute(
        "ALTER TABLE session_control_instances ALTER COLUMN status SET DEFAULT 'not_started'::controlinstancestatus_new"
    )
    op.execute("DROP TYPE controlinstancestatus")
    op.execute("ALTER TYPE controlinstancestatus_new RENAME TO controlinstancestatus")


def downgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE controlinstancestatus ADD VALUE IF NOT EXISTS 'in_progress'")
    op.execute("BEGIN")
    op.execute(
        "CREATE TYPE controlinstancestatus_old AS ENUM ('not_started', 'in_progress', 'pass', 'fail', 'na')"
    )
    op.execute(
        "ALTER TABLE session_control_instances ALTER COLUMN status TYPE controlinstancestatus_old "
        "USING CASE WHEN status::text = 'draft' THEN 'in_progress' ELSE status::text END::controlinstancestatus_old"
    )
    op.execute("DROP TYPE controlinstancestatus")
    op.execute("ALTER TYPE controlinstancestatus_old RENAME TO controlinstancestatus")
