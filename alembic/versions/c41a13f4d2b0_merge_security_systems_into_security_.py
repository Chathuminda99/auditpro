"""merge security systems into security tools

Revision ID: c41a13f4d2b0
Revises: 9f4a5c2d1e7b
Create Date: 2026-03-19 00:00:01.000000

"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c41a13f4d2b0"
down_revision: Union[str, None] = "9f4a5c2d1e7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOURCE_NAME = "Security Systems"
TARGET_NAME = "Security Tools"
TARGET_DESCRIPTION = "Firewalls, IDS/IPS, WAF and security appliances"
TARGET_SORT_ORDER = 5


def _find_scope_type_id(bind, framework_id, name):
    return bind.execute(
        sa.text(
            """
            SELECT id
            FROM review_scope_types
            WHERE framework_id = :framework_id
              AND name = :name
            ORDER BY created_at NULLS FIRST, id
            LIMIT 1
            """
        ),
        {"framework_id": framework_id, "name": name},
    ).scalar()


def upgrade() -> None:
    bind = op.get_bind()

    source_rows = bind.execute(
        sa.text(
            """
            SELECT id, framework_id
            FROM review_scope_types
            WHERE name = :source_name
            ORDER BY framework_id, created_at NULLS FIRST, id
            """
        ),
        {"source_name": SOURCE_NAME},
    ).mappings().all()

    for row in source_rows:
        source_id = row["id"]
        framework_id = row["framework_id"]

        source_exists = bind.execute(
            sa.text("SELECT 1 FROM review_scope_types WHERE id = :id"),
            {"id": source_id},
        ).scalar()
        if not source_exists:
            continue

        target_id = _find_scope_type_id(bind, framework_id, TARGET_NAME)

        if target_id is None:
            bind.execute(
                sa.text(
                    """
                    UPDATE review_scope_types
                    SET name = :target_name,
                        description = COALESCE(description, :target_description),
                        sort_order = CASE
                            WHEN sort_order = 0 THEN :target_sort_order
                            ELSE sort_order
                        END
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": source_id,
                    "target_name": TARGET_NAME,
                    "target_description": TARGET_DESCRIPTION,
                    "target_sort_order": TARGET_SORT_ORDER,
                },
            )
            continue

        if target_id == source_id:
            continue

        source_mappings = bind.execute(
            sa.text(
                """
                SELECT framework_control_id, created_at, updated_at
                FROM control_to_review_scope_mappings AS source_map
                WHERE source_map.review_scope_type_id = :source_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM control_to_review_scope_mappings AS target_map
                      WHERE target_map.review_scope_type_id = :target_id
                        AND target_map.framework_control_id = source_map.framework_control_id
                  )
                """
            ),
            {"source_id": source_id, "target_id": target_id},
        ).mappings().all()

        for mapping in source_mappings:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO control_to_review_scope_mappings (
                        id,
                        review_scope_type_id,
                        framework_control_id,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :review_scope_type_id,
                        :framework_control_id,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "review_scope_type_id": target_id,
                    "framework_control_id": mapping["framework_control_id"],
                    "created_at": mapping["created_at"],
                    "updated_at": mapping["updated_at"],
                },
            )

        source_scopes = bind.execute(
            sa.text(
                """
                SELECT id, project_id, label, sort_order
                FROM review_scopes
                WHERE review_scope_type_id = :source_id
                ORDER BY created_at NULLS FIRST, id
                """
            ),
            {"source_id": source_id},
        ).mappings().all()

        for source_scope in source_scopes:
            target_scope = bind.execute(
                sa.text(
                    """
                    SELECT id, label, sort_order
                    FROM review_scopes
                    WHERE project_id = :project_id
                      AND review_scope_type_id = :target_id
                    ORDER BY created_at NULLS FIRST, id
                    LIMIT 1
                    """
                ),
                {
                    "project_id": source_scope["project_id"],
                    "target_id": target_id,
                },
            ).mappings().first()

            if target_scope:
                bind.execute(
                    sa.text(
                        """
                        UPDATE review_scopes
                        SET label = COALESCE(label, :source_label),
                            sort_order = LEAST(sort_order, :source_sort_order)
                        WHERE id = :target_scope_id
                        """
                    ),
                    {
                        "target_scope_id": target_scope["id"],
                        "source_label": source_scope["label"],
                        "source_sort_order": source_scope["sort_order"],
                    },
                )
                bind.execute(
                    sa.text(
                        """
                        UPDATE audit_sessions
                        SET review_scope_id = :target_scope_id
                        WHERE review_scope_id = :source_scope_id
                        """
                    ),
                    {
                        "target_scope_id": target_scope["id"],
                        "source_scope_id": source_scope["id"],
                    },
                )
                bind.execute(
                    sa.text("DELETE FROM review_scopes WHERE id = :source_scope_id"),
                    {"source_scope_id": source_scope["id"]},
                )
            else:
                bind.execute(
                    sa.text(
                        """
                        UPDATE review_scopes
                        SET review_scope_type_id = :target_id
                        WHERE id = :source_scope_id
                        """
                    ),
                    {
                        "target_id": target_id,
                        "source_scope_id": source_scope["id"],
                    },
                )

        bind.execute(
            sa.text(
                """
                DELETE FROM control_to_review_scope_mappings
                WHERE review_scope_type_id = :source_id
                """
            ),
            {"source_id": source_id},
        )
        bind.execute(
            sa.text("DELETE FROM review_scope_types WHERE id = :source_id"),
            {"source_id": source_id},
        )


def downgrade() -> None:
    raise NotImplementedError(
        "This migration merges duplicate review scope types and cannot be reversed safely."
    )
