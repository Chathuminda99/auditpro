"""Access control helpers."""

from app.models.user import UserRole


def can_access_project(user, project) -> bool:
    """Return True if the user may view/edit this project.

    Admins can access all projects. Auditors can only access projects they
    own or have been added to as a member.
    """
    if user.role == UserRole.ADMIN:
        return True
    if project.owner_id == user.id:
        return True
    return any(m.user_id == user.id for m in project.members)
