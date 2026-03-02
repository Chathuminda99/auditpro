"""add project_type and health check models

Revision ID: 8273559e2bc1
Revises: e0c18c7a7514
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8273559e2bc1'
down_revision: Union[str, None] = 'e0c18c7a7514'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projecttype enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'projecttype') THEN
                CREATE TYPE projecttype AS ENUM ('standard_audit', 'pci_dss_health_check');
            END IF;
        END
        $$;
    """)

    # Add project_type column to projects
    op.add_column(
        'projects',
        sa.Column('project_type', sa.Enum('standard_audit', 'pci_dss_health_check', name='projecttype'), server_default='standard_audit', nullable=False)
    )

    # Create audit_domain_types table
    op.create_table(
        'audit_domain_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('framework_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['framework_id'], ['frameworks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create control_to_domain_mappings table
    op.create_table(
        'control_to_domain_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_domain_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('framework_control_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_domain_type_id'], ['audit_domain_types.id'], ),
        sa.ForeignKeyConstraint(['framework_control_id'], ['framework_controls.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audit_domain_type_id', 'framework_control_id', name='uq_domain_control_mapping')
    )

    # Create audit_domains table
    op.create_table(
        'audit_domains',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_domain_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_domain_type_id'], ['audit_domain_types.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create audit_sessions table
    op.create_table(
        'audit_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_domain_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('asset_identifier', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_domain_id'], ['audit_domains.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create session_control_instances table
    op.create_table(
        'session_control_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('framework_control_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('control_id_snapshot', sa.String(length=50), nullable=False),
        sa.Column('control_title_snapshot', sa.String(length=255), nullable=False),
        sa.Column('control_description_snapshot', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('not_started', 'in_progress', 'pass', 'fail', 'na', name='controlinstancestatus'), server_default='not_started', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assessed_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['audit_session_id'], ['audit_sessions.id'], ),
        sa.ForeignKeyConstraint(['framework_control_id'], ['framework_controls.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create control_instance_evidence_files table
    op.create_table(
        'control_instance_evidence_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_control_instance_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('evidence_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_control_instance_id'], ['session_control_instances.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop control_instance_evidence_files table
    op.drop_table('control_instance_evidence_files')

    # Drop session_control_instances table
    op.drop_table('session_control_instances')

    # Drop controlinstancestatus enum
    op.execute("DROP TYPE IF EXISTS controlinstancestatus")

    # Drop audit_sessions table
    op.drop_table('audit_sessions')

    # Drop audit_domains table
    op.drop_table('audit_domains')

    # Drop control_to_domain_mappings table
    op.drop_table('control_to_domain_mappings')

    # Drop audit_domain_types table
    op.drop_table('audit_domain_types')

    # Remove project_type column from projects
    op.drop_column('projects', 'project_type')

    # Drop projecttype enum
    op.execute("DROP TYPE IF EXISTS projecttype")
