"""Health check repository for audit domains and domain types."""

from typing import List
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, not_, func
from app.models.health_check import (
    AuditDomain,
    AuditDomainType,
    AuditSession,
    SessionControlInstance,
    ControlInstanceEvidenceFile,
    ControlToDomainMapping,
    ControlInstanceStatus,
)
from app.repositories.base import BaseRepository


class HealthCheckRepository(BaseRepository[AuditDomain]):
    """Repository for AuditDomain model with domain type relationships."""

    model = AuditDomain

    def __init__(self, db: Session):
        """Initialize health check repository."""
        super().__init__(db)

    def get_domain_types_for_framework(
        self, framework_id: UUID
    ) -> List[AuditDomainType]:
        """Get all domain types for a framework, sorted by sort_order."""
        return self.db.query(AuditDomainType).filter(
            AuditDomainType.framework_id == framework_id
        ).order_by(AuditDomainType.sort_order).all()

    def get_unadded_domain_types(
        self, project_id: UUID, framework_id: UUID
    ) -> List[AuditDomainType]:
        """Get domain types not yet added to the project."""
        # Subquery: domain type IDs already added to this project
        added_domain_type_ids = self.db.query(AuditDomain.audit_domain_type_id).filter(
            AuditDomain.project_id == project_id
        ).all()
        added_ids = [row[0] for row in added_domain_type_ids]

        # Query domain types not in the added list
        return self.db.query(AuditDomainType).filter(
            and_(
                AuditDomainType.framework_id == framework_id,
                not_(AuditDomainType.id.in_(added_ids)) if added_ids else True
            )
        ).order_by(AuditDomainType.sort_order).all()

    def get_domains_for_project(self, project_id: UUID) -> List[AuditDomain]:
        """Get all domains for a project with eager-loaded domain types, sessions, and control instances."""
        return self.db.query(AuditDomain).filter(
            AuditDomain.project_id == project_id
        ).options(
            joinedload(AuditDomain.audit_domain_type),
            joinedload(AuditDomain.sessions).joinedload(AuditSession.control_instances)
        ).order_by(AuditDomain.sort_order).all()

    def get_domain_by_id(self, domain_id: UUID) -> AuditDomain | None:
        """Get a domain by ID with eager-loaded domain type."""
        return self.db.query(AuditDomain).filter(
            AuditDomain.id == domain_id
        ).options(
            joinedload(AuditDomain.audit_domain_type)
        ).first()

    def add_domain_to_project(
        self,
        project_id: UUID,
        domain_type_id: UUID,
        label: str | None = None,
        sort_order: int = 0,
    ) -> AuditDomain:
        """Add a domain to a project and return it with relationships loaded."""
        domain = AuditDomain(
            project_id=project_id,
            audit_domain_type_id=domain_type_id,
            label=label,
            sort_order=sort_order,
        )
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain, ["audit_domain_type", "sessions"])
        return domain

    def remove_domain(self, domain_id: UUID) -> bool:
        """Delete a domain (cascades to sessions via relationship)."""
        domain = self.db.query(AuditDomain).filter(
            AuditDomain.id == domain_id
        ).first()
        if not domain:
            return False
        self.db.delete(domain)
        self.db.commit()
        return True

    # === Domain Detail ===

    def get_domain_with_sessions(self, domain_id: UUID) -> AuditDomain | None:
        """Load domain with sessions (no control instances) for domain detail page."""
        return self.db.query(AuditDomain).filter(
            AuditDomain.id == domain_id
        ).options(
            joinedload(AuditDomain.audit_domain_type),
            joinedload(AuditDomain.sessions),
        ).first()

    # === Session CRUD ===

    def create_session(
        self,
        domain_id: UUID,
        project_id: UUID,
        name: str,
        asset_identifier: str | None = None,
        description: str | None = None,
    ) -> AuditSession:
        """Create a new audit session."""
        session = AuditSession(
            audit_domain_id=domain_id,
            project_id=project_id,
            name=name,
            asset_identifier=asset_identifier,
            description=description,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session, ["audit_domain", "control_instances"])
        return session

    def get_session_by_id(self, session_id: UUID) -> AuditSession | None:
        """Get a session by ID with eager-loaded domain type."""
        return self.db.query(AuditSession).filter(
            AuditSession.id == session_id
        ).options(
            joinedload(AuditSession.audit_domain).joinedload(AuditDomain.audit_domain_type)
        ).first()

    def delete_session(self, session_id: UUID) -> bool:
        """Delete a session (cascades to control instances via model relationship)."""
        session = self.db.query(AuditSession).filter(
            AuditSession.id == session_id
        ).first()
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    # === Control Instance Seeding ===

    def seed_control_instances(self, session: AuditSession, domain_type_id: UUID) -> int:
        """Create SessionControlInstance rows for all controls mapped to this domain type.
        Returns count of instances created."""
        mappings = self.db.query(ControlToDomainMapping).filter(
            ControlToDomainMapping.audit_domain_type_id == domain_type_id
        ).options(joinedload(ControlToDomainMapping.framework_control)).all()

        for mapping in mappings:
            ctrl = mapping.framework_control
            instance = SessionControlInstance(
                audit_session_id=session.id,
                framework_control_id=ctrl.id,
                control_id_snapshot=ctrl.control_id,
                control_title_snapshot=ctrl.name,
                control_description_snapshot=ctrl.description,
                status=ControlInstanceStatus.NOT_STARTED,
            )
            self.db.add(instance)
        self.db.commit()
        return len(mappings)

    # === Control Instance Queries ===

    def get_control_instances_for_session(
        self, session_id: UUID
    ) -> List[SessionControlInstance]:
        """All instances ordered by control_id_snapshot, with evidence_files eager-loaded."""
        return self.db.query(SessionControlInstance).filter(
            SessionControlInstance.audit_session_id == session_id
        ).options(
            joinedload(SessionControlInstance.evidence_files)
        ).order_by(SessionControlInstance.control_id_snapshot).all()

    def get_control_instance_by_id(self, instance_id: UUID) -> SessionControlInstance | None:
        """Single instance with evidence_files."""
        return self.db.query(SessionControlInstance).filter(
            SessionControlInstance.id == instance_id
        ).options(
            joinedload(SessionControlInstance.evidence_files)
        ).first()

    def update_control_instance(
        self,
        instance_id: UUID,
        status: ControlInstanceStatus,
        notes: str | None,
        assessed_by_id: UUID | None,
    ) -> SessionControlInstance | None:
        """Update control instance status and notes."""
        instance = self.get_control_instance_by_id(instance_id)
        if not instance:
            return None
        instance.status = status
        instance.notes = notes
        instance.assessed_by_id = assessed_by_id
        self.db.commit()
        self.db.refresh(instance, ["evidence_files"])
        return instance

    # === Evidence CRUD ===

    def add_text_evidence(
        self, instance_id: UUID, content: str
    ) -> ControlInstanceEvidenceFile:
        """Add a text note as evidence."""
        ev = ControlInstanceEvidenceFile(
            session_control_instance_id=instance_id,
            evidence_type="text_note",
            content=content,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def add_file_evidence(
        self,
        instance_id: UUID,
        filename: str,
        file_path: str,
        file_size: int,
    ) -> ControlInstanceEvidenceFile:
        """Add a file as evidence."""
        ev = ControlInstanceEvidenceFile(
            session_control_instance_id=instance_id,
            evidence_type="file",
            filename=filename,
            file_path=file_path,
            file_size=file_size,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def get_evidence_by_id(self, evidence_id: UUID) -> ControlInstanceEvidenceFile | None:
        """Get evidence by ID."""
        return self.db.query(ControlInstanceEvidenceFile).filter(
            ControlInstanceEvidenceFile.id == evidence_id
        ).options(
            joinedload(ControlInstanceEvidenceFile.control_instance)
        ).first()

    def delete_evidence(self, evidence_id: UUID) -> bool:
        """Delete evidence item."""
        ev = self.db.query(ControlInstanceEvidenceFile).filter(
            ControlInstanceEvidenceFile.id == evidence_id
        ).first()
        if not ev:
            return False
        self.db.delete(ev)
        self.db.commit()
        return True

    # === Stats ===

    def get_session_stats(self, session_id: UUID) -> dict:
        """Return count by status for a session's control instances."""
        rows = self.db.query(
            SessionControlInstance.status, func.count()
        ).filter(
            SessionControlInstance.audit_session_id == session_id
        ).group_by(SessionControlInstance.status).all()
        stats = {s.value: 0 for s in ControlInstanceStatus}
        for status, count in rows:
            stats[status] = count
        return stats
