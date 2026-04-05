import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opentrend.models.base import Base

if TYPE_CHECKING:
    from opentrend.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    github_repo: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="projects", lazy="selectin")
    package_mappings: Mapped[list[PackageMapping]] = relationship(
        back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )


class PackageMapping(Base):
    __tablename__ = "package_mappings"
    __table_args__ = (UniqueConstraint("project_id", "source", "package_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(50))
    package_name: Mapped[str] = mapped_column(String(255))

    project: Mapped[Project] = relationship(back_populates="package_mappings")
