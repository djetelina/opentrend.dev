import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.models.project import PackageMapping, Project


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        github_repo: str,
        display_name: str,
        description: str,
        package_mappings: list[dict],
    ) -> Project:
        project = Project(
            user_id=user_id,
            github_repo=github_repo,
            display_name=display_name,
            description=description,
        )

        seen: set[tuple[str, str]] = set()
        deduped = []
        for m in package_mappings:
            key = (m["source"], m["package_name"].lower())
            if key not in seen:
                seen.add(key)
                deduped.append(
                    PackageMapping(source=m["source"], package_name=m["package_name"])
                )
        project.package_mappings = deduped

        self._session.add(project)
        await self._session.commit()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        result = await self._session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID) -> list[Project]:
        result = await self._session.execute(
            select(Project).where(Project.user_id == user_id)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Project]:
        result = await self._session.execute(select(Project))
        return list(result.scalars().all())

    async def delete(self, project: Project) -> None:
        await self._session.delete(project)
        await self._session.commit()
