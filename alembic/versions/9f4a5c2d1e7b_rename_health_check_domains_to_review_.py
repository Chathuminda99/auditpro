"""rename health check domains to review scopes

Revision ID: 9f4a5c2d1e7b
Revises: b429d6e5dea0
Create Date: 2026-03-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9f4a5c2d1e7b"
down_revision: Union[str, None] = "b429d6e5dea0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(
    inspector: sa.Inspector, table_name: str, column_name: str
) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def _has_constraint(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = :table_name
                  AND c.conname = :constraint_name
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_old_types = _has_table(inspector, "audit_domain_types")
    has_old_scopes = _has_table(inspector, "audit_domains")
    has_old_mappings = _has_table(inspector, "control_to_domain_mappings")
    has_new_types = _has_table(inspector, "review_scope_types")
    has_new_scopes = _has_table(inspector, "review_scopes")
    has_new_mappings = _has_table(inspector, "control_to_review_scope_mappings")

    if has_old_types and not has_new_types:
        op.rename_table("audit_domain_types", "review_scope_types")
        has_old_types = False
        has_new_types = True

    if has_old_scopes and not has_new_scopes:
        op.rename_table("audit_domains", "review_scopes")
        has_old_scopes = False
        has_new_scopes = True

    if has_old_mappings and not has_new_mappings:
        op.rename_table(
            "control_to_domain_mappings", "control_to_review_scope_mappings"
        )
        has_old_mappings = False
        has_new_mappings = True

    inspector = sa.inspect(bind)

    if has_new_mappings and _has_column(
        inspector,
        "control_to_review_scope_mappings",
        "audit_domain_type_id",
    ):
        op.alter_column(
            "control_to_review_scope_mappings",
            "audit_domain_type_id",
            new_column_name="review_scope_type_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    if has_new_scopes and _has_column(
        inspector,
        "review_scopes",
        "audit_domain_type_id",
    ):
        op.alter_column(
            "review_scopes",
            "audit_domain_type_id",
            new_column_name="review_scope_type_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    inspector = sa.inspect(bind)

    if has_old_types and has_new_types:
        op.execute(
            sa.text(
                """
                INSERT INTO review_scope_types (
                    id,
                    framework_id,
                    name,
                    description,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    audit_domain_types.id,
                    audit_domain_types.framework_id,
                    audit_domain_types.name,
                    audit_domain_types.description,
                    audit_domain_types.sort_order,
                    audit_domain_types.created_at,
                    audit_domain_types.updated_at
                FROM audit_domain_types
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM review_scope_types
                    WHERE review_scope_types.framework_id = audit_domain_types.framework_id
                      AND review_scope_types.name = audit_domain_types.name
                )
                """
            )
        )

    if has_old_mappings and has_new_mappings and has_old_types and has_new_types:
        op.execute(
            sa.text(
                """
                INSERT INTO control_to_review_scope_mappings (
                    id,
                    review_scope_type_id,
                    framework_control_id,
                    created_at,
                    updated_at
                )
                SELECT
                    ctdm.id,
                    rst.id,
                    ctdm.framework_control_id,
                    ctdm.created_at,
                    ctdm.updated_at
                FROM control_to_domain_mappings AS ctdm
                JOIN audit_domain_types AS adt
                  ON adt.id = ctdm.audit_domain_type_id
                JOIN review_scope_types AS rst
                  ON rst.framework_id = adt.framework_id
                 AND rst.name = adt.name
                ON CONFLICT ON CONSTRAINT uq_review_scope_mapping DO NOTHING
                """
            )
        )

    if has_old_scopes and has_new_scopes and has_old_types and has_new_types:
        op.execute(
            sa.text(
                """
                INSERT INTO review_scopes (
                    id,
                    project_id,
                    review_scope_type_id,
                    label,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    ad.id,
                    ad.project_id,
                    rst.id,
                    ad.label,
                    ad.sort_order,
                    ad.created_at,
                    ad.updated_at
                FROM audit_domains AS ad
                JOIN audit_domain_types AS adt
                  ON adt.id = ad.audit_domain_type_id
                JOIN review_scope_types AS rst
                  ON rst.framework_id = adt.framework_id
                 AND rst.name = adt.name
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "audit_sessions") and _has_column(
        inspector, "audit_sessions", "audit_domain_id"
    ):
        if _has_constraint("audit_sessions", "audit_sessions_audit_domain_id_fkey"):
            op.drop_constraint(
                "audit_sessions_audit_domain_id_fkey",
                "audit_sessions",
                type_="foreignkey",
            )

        op.alter_column(
            "audit_sessions",
            "audit_domain_id",
            new_column_name="review_scope_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "audit_sessions") and _has_column(
        inspector, "audit_sessions", "review_scope_id"
    ) and not _has_constraint(
        "audit_sessions", "audit_sessions_review_scope_id_fkey"
    ):
        op.create_foreign_key(
            "audit_sessions_review_scope_id_fkey",
            "audit_sessions",
            "review_scopes",
            ["review_scope_id"],
            ["id"],
        )

    if has_new_mappings and _has_constraint(
        "control_to_review_scope_mappings", "uq_domain_control_mapping"
    ):
        op.execute(
            sa.text(
                "ALTER TABLE control_to_review_scope_mappings "
                "RENAME CONSTRAINT uq_domain_control_mapping TO uq_review_scope_mapping"
            )
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "control_to_domain_mappings"):
        op.drop_table("control_to_domain_mappings")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "audit_domains"):
        op.drop_table("audit_domains")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "audit_domain_types"):
        op.drop_table("audit_domain_types")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "audit_sessions") and _has_column(
        inspector, "audit_sessions", "review_scope_id"
    ):
        if _has_constraint("audit_sessions", "audit_sessions_review_scope_id_fkey"):
            op.drop_constraint(
                "audit_sessions_review_scope_id_fkey",
                "audit_sessions",
                type_="foreignkey",
            )

        op.alter_column(
            "audit_sessions",
            "review_scope_id",
            new_column_name="audit_domain_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "review_scope_types") and not _has_table(
        inspector, "audit_domain_types"
    ):
        op.rename_table("review_scope_types", "audit_domain_types")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "review_scopes") and not _has_table(
        inspector, "audit_domains"
    ):
        op.rename_table("review_scopes", "audit_domains")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "control_to_review_scope_mappings") and not _has_table(
        inspector, "control_to_domain_mappings"
    ):
        if _has_constraint(
            "control_to_review_scope_mappings", "uq_review_scope_mapping"
        ):
            op.execute(
                sa.text(
                    "ALTER TABLE control_to_review_scope_mappings "
                    "RENAME CONSTRAINT uq_review_scope_mapping TO uq_domain_control_mapping"
                )
            )

        op.rename_table(
            "control_to_review_scope_mappings", "control_to_domain_mappings"
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "control_to_domain_mappings") and _has_column(
        inspector, "control_to_domain_mappings", "review_scope_type_id"
    ):
        op.alter_column(
            "control_to_domain_mappings",
            "review_scope_type_id",
            new_column_name="audit_domain_type_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    if _has_table(inspector, "audit_domains") and _has_column(
        inspector, "audit_domains", "review_scope_type_id"
    ):
        op.alter_column(
            "audit_domains",
            "review_scope_type_id",
            new_column_name="audit_domain_type_id",
            existing_type=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
        )

    if _has_table(inspector, "audit_sessions") and _has_column(
        inspector, "audit_sessions", "audit_domain_id"
    ) and not _has_constraint(
        "audit_sessions", "audit_sessions_audit_domain_id_fkey"
    ):
        op.create_foreign_key(
            "audit_sessions_audit_domain_id_fkey",
            "audit_sessions",
            "audit_domains",
            ["audit_domain_id"],
            ["id"],
        )
