"""rbac_owner_and_role_cleanup

Revision ID: e0c18c7a7514
Revises: 63934f31f78a
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e0c18c7a7514'
down_revision: Union[str, None] = '63934f31f78a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create new enum with only admin/auditor values
    op.execute("CREATE TYPE userrole_new AS ENUM ('admin', 'auditor')")

    # 2. Alter column to use new enum (map all non-admin roles → auditor)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole_new
        USING (CASE role::text WHEN 'admin' THEN 'admin'::userrole_new ELSE 'auditor'::userrole_new END)
    """)

    # 3. Drop old enum and rename new one
    op.execute("DROP TYPE userrole")
    op.execute("ALTER TYPE userrole_new RENAME TO userrole")

    # 4. Add owner_id to projects (nullable)
    op.add_column(
        'projects',
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True)
    )

    # 5. Back-fill owner_id with the first admin user
    op.execute("""
        UPDATE projects
        SET owner_id = (SELECT id FROM users WHERE role = 'admin' LIMIT 1)
        WHERE owner_id IS NULL
    """)

    # 6. Add unique constraint on project_members(project_id, user_id)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'project_members'
                AND constraint_name = 'uq_project_members_project_user'
            ) THEN
                ALTER TABLE project_members
                ADD CONSTRAINT uq_project_members_project_user UNIQUE (project_id, user_id);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Remove unique constraint on project_members
    op.execute("""
        ALTER TABLE project_members
        DROP CONSTRAINT IF EXISTS uq_project_members_project_user
    """)

    # Remove owner_id from projects
    op.drop_column('projects', 'owner_id')

    # Restore original 4-value enum
    op.execute("CREATE TYPE userrole_old AS ENUM ('admin', 'assessor', 'client', 'viewer')")
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole_old
        USING (CASE role::text WHEN 'admin' THEN 'admin'::userrole_old ELSE 'assessor'::userrole_old END)
    """)
    op.execute("DROP TYPE userrole")
    op.execute("ALTER TYPE userrole_old RENAME TO userrole")
