import uuid
from sqlalchemy.orm import Session
from app.models.project import ProjectObservation, ProjectEvidenceFile
from app.repositories.base import BaseRepository


class ProjectObservationRepository(BaseRepository[ProjectObservation]):
    """Repository for ProjectObservation model."""

    model = ProjectObservation

    def __init__(self, db: Session):
        super().__init__(db)

    def get_for_control(
        self, project_id: uuid.UUID, control_id: uuid.UUID
    ) -> list[ProjectObservation]:
        """Get all observations for a specific control in a project."""
        return (
            self.db.query(ProjectObservation)
            .filter(
                ProjectObservation.project_id == project_id,
                ProjectObservation.framework_control_id == control_id,
            )
            .all()
        )

    def create_observation(
        self,
        project_id: uuid.UUID,
        control_id: uuid.UUID,
        observation_text: str,
        recommendation_text: str,
    ) -> ProjectObservation:
        """Create a new observation."""
        observation = ProjectObservation(
            id=uuid.uuid4(),
            project_id=project_id,
            framework_control_id=control_id,
            observation_text=observation_text,
            recommendation_text=recommendation_text,
        )
        self.db.add(observation)
        self.db.commit()
        return observation

    def update_observation(
        self,
        observation_id: uuid.UUID,
        observation_text: str,
        recommendation_text: str,
    ) -> ProjectObservation | None:
        """Update observation text and recommendation."""
        observation = self.db.query(ProjectObservation).filter(
            ProjectObservation.id == observation_id
        ).first()
        if observation:
            observation.observation_text = observation_text
            observation.recommendation_text = recommendation_text
            self.db.commit()
            self.db.refresh(observation)
        return observation

    def delete_observation(self, observation_id: uuid.UUID) -> bool:
        """Delete an observation and its evidence files."""
        observation = self.db.query(ProjectObservation).filter(
            ProjectObservation.id == observation_id
        ).first()
        if observation:
            self.db.delete(observation)
            self.db.commit()
            return True
        return False

    def get_observation(self, observation_id: uuid.UUID) -> ProjectObservation | None:
        return self.db.query(ProjectObservation).filter(
            ProjectObservation.id == observation_id
        ).first()

    def add_text_note(self, observation_id: uuid.UUID, content: str) -> ProjectEvidenceFile:
        evidence = ProjectEvidenceFile(
            id=uuid.uuid4(),
            project_observation_id=observation_id,
            evidence_type="text_note",
            content=content,
        )
        self.db.add(evidence)
        self.db.commit()
        return evidence

    def add_image(
        self, observation_id: uuid.UUID, filename: str, file_path: str, file_size: int
    ) -> ProjectEvidenceFile:
        evidence = ProjectEvidenceFile(
            id=uuid.uuid4(),
            project_observation_id=observation_id,
            evidence_type="image",
            filename=filename,
            file_path=file_path,
            file_size=file_size,
        )
        self.db.add(evidence)
        self.db.commit()
        return evidence

    def delete_evidence(self, evidence_id: uuid.UUID) -> bool:
        evidence = self.db.query(ProjectEvidenceFile).filter(
            ProjectEvidenceFile.id == evidence_id
        ).first()
        if evidence:
            self.db.delete(evidence)
            self.db.commit()
            return True
        return False
