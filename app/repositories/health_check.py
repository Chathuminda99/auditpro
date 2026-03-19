"""Health check repository for review scopes and review scope types."""

from typing import List
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, not_, func
from app.models.health_check import (
    ReviewScope,
    ReviewScopeType,
    AuditSession,
    SessionControlInstance,
    ControlInstanceEvidenceFile,
    SessionControlObservation,
    SessionControlObservationEvidence,
    ControlToReviewScopeMapping,
    ControlInstanceStatus,
)
from app.repositories.base import BaseRepository


class HealthCheckRepository(BaseRepository[ReviewScope]):
    """Repository for ReviewScope with review-scope-aware queries."""

    model = ReviewScope

    def __init__(self, db: Session):
        """Initialize health check repository."""
        super().__init__(db)

    def get_review_scope_types_for_framework(
        self, framework_id: UUID
    ) -> List[ReviewScopeType]:
        """Get all review scope types for a framework, sorted by sort_order."""
        return self.db.query(ReviewScopeType).filter(
            ReviewScopeType.framework_id == framework_id
        ).order_by(ReviewScopeType.sort_order).all()

    def get_unadded_review_scope_types(
        self, project_id: UUID, framework_id: UUID
    ) -> List[ReviewScopeType]:
        """Get review scope types not yet added to the project."""
        # Subquery: review scope type IDs already added to this project
        added_review_scope_type_ids = self.db.query(ReviewScope.review_scope_type_id).filter(
            ReviewScope.project_id == project_id
        ).all()
        added_ids = [row[0] for row in added_review_scope_type_ids]

        # Query review scope types not in the added list
        return self.db.query(ReviewScopeType).filter(
            and_(
                ReviewScopeType.framework_id == framework_id,
                not_(ReviewScopeType.id.in_(added_ids)) if added_ids else True
            )
        ).order_by(ReviewScopeType.sort_order).all()

    def get_review_scopes_for_project(self, project_id: UUID) -> List[ReviewScope]:
        """Get all review scopes for a project with eager-loaded related data."""
        return self.db.query(ReviewScope).filter(
            ReviewScope.project_id == project_id
        ).options(
            joinedload(ReviewScope.review_scope_type),
            joinedload(ReviewScope.sessions).joinedload(AuditSession.control_instances)
        ).order_by(ReviewScope.sort_order).all()

    def get_review_scope_by_id(self, review_scope_id: UUID) -> ReviewScope | None:
        """Get a review scope by ID with its type eagerly loaded."""
        return self.db.query(ReviewScope).filter(
            ReviewScope.id == review_scope_id
        ).options(
            joinedload(ReviewScope.review_scope_type)
        ).first()

    def add_review_scope_to_project(
        self,
        project_id: UUID,
        review_scope_type_id: UUID,
        label: str | None = None,
        sort_order: int = 0,
    ) -> ReviewScope:
        """Add a review scope to a project and return it with relationships loaded."""
        review_scope = ReviewScope(
            project_id=project_id,
            review_scope_type_id=review_scope_type_id,
            label=label,
            sort_order=sort_order,
        )
        self.db.add(review_scope)
        self.db.commit()
        self.db.refresh(review_scope, ["review_scope_type", "sessions"])
        return review_scope

    def remove_review_scope(self, review_scope_id: UUID) -> bool:
        """Delete a review scope and cascade to its sessions."""
        review_scope = self.db.query(ReviewScope).filter(
            ReviewScope.id == review_scope_id
        ).first()
        if not review_scope:
            return False
        self.db.delete(review_scope)
        self.db.commit()
        return True

    # === Review Scope Detail ===

    def get_review_scope_with_sessions(self, review_scope_id: UUID) -> ReviewScope | None:
        """Load a review scope with sessions for the detail page."""
        return self.db.query(ReviewScope).filter(
            ReviewScope.id == review_scope_id
        ).options(
            joinedload(ReviewScope.review_scope_type),
            joinedload(ReviewScope.sessions),
        ).first()

    # === Session CRUD ===

    def create_session(
        self,
        review_scope_id: UUID,
        project_id: UUID,
        name: str,
        asset_identifier: str | None = None,
        description: str | None = None,
    ) -> AuditSession:
        """Create a new audit session."""
        session = AuditSession(
            review_scope_id=review_scope_id,
            project_id=project_id,
            name=name,
            asset_identifier=asset_identifier,
            description=description,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session, ["review_scope", "control_instances"])
        return session

    def get_session_by_id(self, session_id: UUID) -> AuditSession | None:
        """Get a session by ID with its review scope and type."""
        return self.db.query(AuditSession).filter(
            AuditSession.id == session_id
        ).options(
            joinedload(AuditSession.review_scope).joinedload(ReviewScope.review_scope_type)
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

    def seed_control_instances(self, session: AuditSession, review_scope_type_id: UUID) -> int:
        """Create SessionControlInstance rows for all controls mapped to this review scope type.
        Returns count of instances created."""
        mappings = self.db.query(ControlToReviewScopeMapping).filter(
            ControlToReviewScopeMapping.review_scope_type_id == review_scope_type_id
        ).options(joinedload(ControlToReviewScopeMapping.framework_control)).all()

        for mapping in mappings:
            ctrl = mapping.framework_control
            instance = SessionControlInstance(
                audit_session_id=session.id,
                framework_control_id=ctrl.id,
                control_id_snapshot=ctrl.control_id,
                control_title_snapshot=ctrl.name,
                control_description_snapshot=ctrl.description,
                requirements_text_snapshot=ctrl.requirements_text,
                testing_procedures_text_snapshot=ctrl.testing_procedures_text,
                check_points_text_snapshot=ctrl.check_points_text,
                assessment_checklist_snapshot=ctrl.assessment_checklist,
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

    # === Observations ===

    def get_control_instance_with_observations(
        self, instance_id: UUID
    ) -> SessionControlInstance | None:
        """Load control instance with observations and their evidence files."""
        return self.db.query(SessionControlInstance).filter(
            SessionControlInstance.id == instance_id
        ).options(
            joinedload(SessionControlInstance.observations).joinedload(
                SessionControlObservation.evidence_files
            ),
            joinedload(SessionControlInstance.evidence_files),
        ).first()

    def create_observation(
        self,
        instance_id: UUID,
        observation_text: str,
        recommendation_text: str | None = None,
    ) -> SessionControlObservation:
        """Create a new observation for a control instance."""
        obs = SessionControlObservation(
            session_control_instance_id=instance_id,
            observation_text=observation_text,
            recommendation_text=recommendation_text,
        )
        self.db.add(obs)
        self.db.commit()
        self.db.refresh(obs, ["evidence_files"])
        return obs

    def update_observation_recommendation(self, observation_id: UUID, recommendation_text: str | None) -> bool:
        """Update the recommendation text of an existing observation."""
        obs = self.db.query(SessionControlObservation).filter(
            SessionControlObservation.id == observation_id
        ).first()
        if not obs:
            return False
        obs.recommendation_text = recommendation_text
        self.db.commit()
        return True

    def delete_observation(self, observation_id: UUID) -> bool:
        """Delete an observation (cascades to evidence)."""
        obs = self.db.query(SessionControlObservation).filter(
            SessionControlObservation.id == observation_id
        ).first()
        if not obs:
            return False
        self.db.delete(obs)
        self.db.commit()
        return True

    def get_observation_by_id(
        self, observation_id: UUID
    ) -> SessionControlObservation | None:
        """Get an observation by ID with evidence files."""
        return self.db.query(SessionControlObservation).filter(
            SessionControlObservation.id == observation_id
        ).options(
            joinedload(SessionControlObservation.evidence_files)
        ).first()

    def add_observation_text_note(
        self, observation_id: UUID, content: str
    ) -> SessionControlObservationEvidence:
        """Add a text note as evidence to an observation."""
        ev = SessionControlObservationEvidence(
            session_control_observation_id=observation_id,
            evidence_type="text_note",
            content=content,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def add_observation_image(
        self,
        observation_id: UUID,
        filename: str,
        file_path: str,
        file_size: int,
    ) -> SessionControlObservationEvidence:
        """Add an image as evidence to an observation."""
        ev = SessionControlObservationEvidence(
            session_control_observation_id=observation_id,
            evidence_type="image",
            filename=filename,
            file_path=file_path,
            file_size=file_size,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def delete_observation_evidence(self, evidence_id: UUID) -> bool:
        """Delete observation evidence."""
        ev = self.db.query(SessionControlObservationEvidence).filter(
            SessionControlObservationEvidence.id == evidence_id
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
