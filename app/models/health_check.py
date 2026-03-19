"""Models for PCI DSS Health Check audits and related structures."""

import uuid
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Enum as SQLEnum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TimestampMixin
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.models.framework import FrameworkControl
    from app.models.project import Project
    from app.models.user import User


class ControlInstanceStatus(str, Enum):
    """Status of a control instance in a health check session."""

    NOT_STARTED = "not_started"
    DRAFT = "draft"
    PASS = "pass"
    FAIL = "fail"
    NA = "na"


class ReviewScopeType(BaseModel, TimestampMixin):
    """Global review scope template for health checks, scoped to a framework.

    Example: "Application", "Database", "Network Devices" for PCI DSS.
    """

    __tablename__ = "review_scope_types"

    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frameworks.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    control_mappings: Mapped[list["ControlToReviewScopeMapping"]] = relationship(
        back_populates="review_scope_type", cascade="all, delete-orphan"
    )
    review_scopes: Mapped[list["ReviewScope"]] = relationship(
        back_populates="review_scope_type", cascade="all, delete-orphan"
    )


class ControlToReviewScopeMapping(BaseModel, TimestampMixin):
    """Many-to-many mapping: which controls apply to which review scopes.

    Example: Req 2.2.1 applies to "Application", "Database", and "Network Devices".
    """

    __tablename__ = "control_to_review_scope_mappings"

    review_scope_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_scope_types.id"), nullable=False
    )
    framework_control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("framework_controls.id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "review_scope_type_id",
            "framework_control_id",
            name="uq_review_scope_mapping",
        ),
    )

    # Relationships
    review_scope_type: Mapped["ReviewScopeType"] = relationship(
        back_populates="control_mappings"
    )
    framework_control: Mapped["FrameworkControl"] = relationship()


class ReviewScope(BaseModel, TimestampMixin):
    """A review scope added to a specific health-check project.

    Parent node in the hierarchy: Project → ReviewScope → AuditSession → SessionControlInstance.
    """

    __tablename__ = "review_scopes"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    review_scope_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_scope_types.id"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="review_scopes")
    review_scope_type: Mapped["ReviewScopeType"] = relationship(
        back_populates="review_scopes"
    )
    sessions: Mapped[list["AuditSession"]] = relationship(
        back_populates="review_scope", cascade="all, delete-orphan"
    )


class AuditSession(BaseModel, TimestampMixin):
    """A specific asset or instance under a review scope.

    Child node: ReviewScope → AuditSession → SessionControlInstance.
    Example: "ABC Application" or "10.0.0.1 — Web Server".
    """

    __tablename__ = "audit_sessions"

    review_scope_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_scopes.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    review_scope: Mapped["ReviewScope"] = relationship(back_populates="sessions")
    project: Mapped["Project"] = relationship(back_populates="audit_sessions")
    control_instances: Mapped[list["SessionControlInstance"]] = relationship(
        back_populates="audit_session", cascade="all, delete-orphan"
    )


class SessionControlInstance(BaseModel, TimestampMixin):
    """Snapshot of a control in an audit session.

    Captures the control's state at session creation time, plus assessment status.
    """

    __tablename__ = "session_control_instances"

    audit_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audit_sessions.id"), nullable=False
    )
    framework_control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("framework_controls.id"), nullable=False
    )
    control_id_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    control_title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    control_description_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
    requirements_text_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
    testing_procedures_text_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
    check_points_text_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
    assessment_checklist_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ControlInstanceStatus] = mapped_column(
        SQLEnum(ControlInstanceStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ControlInstanceStatus.NOT_STARTED,
    )
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    assessed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    audit_session: Mapped["AuditSession"] = relationship(back_populates="control_instances")
    framework_control: Mapped["FrameworkControl"] = relationship()
    assessed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assessed_by_id]
    )
    reviewed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by_id]
    )
    evidence_files: Mapped[list["ControlInstanceEvidenceFile"]] = relationship(
        back_populates="control_instance", cascade="all, delete-orphan"
    )
    observations: Mapped[list["SessionControlObservation"]] = relationship(
        back_populates="control_instance", cascade="all, delete-orphan"
    )


class ControlInstanceEvidenceFile(BaseModel, TimestampMixin):
    """Evidence (text note or file) attached to a control instance."""

    __tablename__ = "control_instance_evidence_files"

    session_control_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_control_instances.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'text_note' or 'file'
    content: Mapped[str] = mapped_column(Text, nullable=True)  # For text_note
    filename: Mapped[str] = mapped_column(String(255), nullable=True)  # For file
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)  # For file
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # For file

    # Relationships
    control_instance: Mapped["SessionControlInstance"] = relationship(
        back_populates="evidence_files"
    )


class SessionControlObservation(BaseModel, TimestampMixin):
    """Observation (finding) documented during control assessment."""

    __tablename__ = "session_control_observations"

    session_control_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_control_instances.id"), nullable=False
    )
    observation_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    control_instance: Mapped["SessionControlInstance"] = relationship(
        back_populates="observations"
    )
    evidence_files: Mapped[list["SessionControlObservationEvidence"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )


class SessionControlObservationEvidence(BaseModel, TimestampMixin):
    """Evidence (text note or file) attached to an observation."""

    __tablename__ = "session_control_observation_evidence"

    session_control_observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_control_observations.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'text_note' or 'image'
    content: Mapped[str] = mapped_column(Text, nullable=True)  # For text_note
    filename: Mapped[str] = mapped_column(String(255), nullable=True)  # For image
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)  # For image
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # For image

    # Relationships
    observation: Mapped["SessionControlObservation"] = relationship(
        back_populates="evidence_files"
    )
