import uuid
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ProjectType(str, Enum):
    """Project type enumeration."""

    STANDARD_AUDIT = "standard_audit"
    PCI_DSS_HEALTH_CHECK = "pci_dss_health_check"


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ResponseStatus(str, Enum):
    """Response status for controls."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class Project(BaseModel, TimestampMixin):
    """Assessment/audit project model."""

    __tablename__ = "projects"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id"), nullable=False
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frameworks.id"), nullable=False
    )
    parent_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus), nullable=False, default=ProjectStatus.DRAFT
    )
    project_type: Mapped[ProjectType] = mapped_column(
        SQLEnum(ProjectType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default="standard_audit",
    )

    # Relationships
    client: Mapped["Client"] = relationship()
    framework: Mapped["Framework"] = relationship()
    owner: Mapped["User | None"] = relationship("User", foreign_keys=[owner_id])
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", cascade="all, delete-orphan", back_populates="project"
    )
    responses: Mapped[list["ProjectResponse"]] = relationship(
        "ProjectResponse", cascade="all, delete-orphan"
    )
    segments: Mapped[list["Project"]] = relationship(
        "Project",
        foreign_keys=[parent_project_id],
        back_populates="parent_project",
        cascade="all, delete-orphan",
    )
    parent_project: Mapped["Project | None"] = relationship(
        "Project",
        foreign_keys=[parent_project_id],
        back_populates="segments",
        remote_side="Project.id",
    )


class ProjectMember(BaseModel, TimestampMixin):
    """Team member assignment to a project."""

    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="auditor")

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class ProjectResponse(BaseModel, TimestampMixin):
    """Response to a framework control within a project."""

    __tablename__ = "project_responses"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    framework_control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("framework_controls.id"), nullable=False
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=True)
    finding: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    auditor_notes: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ResponseStatus] = mapped_column(
        SQLEnum(ResponseStatus), nullable=False, default=ResponseStatus.NOT_STARTED
    )
    assigned_to_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    control: Mapped["FrameworkControl"] = relationship()


class ProjectObservation(BaseModel, TimestampMixin):
    """Observation with recommendation for a specific control in a project."""

    __tablename__ = "project_observations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    framework_control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("framework_controls.id"), nullable=False
    )
    observation_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    evidence_files: Mapped[list["ProjectEvidenceFile"]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )


class ProjectEvidenceFile(BaseModel, TimestampMixin):
    """Evidence file or text note attachment for an observation."""

    __tablename__ = "project_evidence_files"

    project_observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_observations.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'text_note' or 'image'
    content: Mapped[str] = mapped_column(Text, nullable=True)  # For text notes
    filename: Mapped[str] = mapped_column(String(255), nullable=True)  # For images
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)  # For images
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # For images

    # Relationships
    observation: Mapped["ProjectObservation"] = relationship(
        back_populates="evidence_files"
    )
