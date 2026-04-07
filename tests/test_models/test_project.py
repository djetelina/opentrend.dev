from opentrend.models.project import (
    PackageMapping,
    Project,
)


def test_project_table_name() -> None:
    assert Project.__tablename__ == "projects"


def test_project_has_required_columns() -> None:
    columns = {c.name for c in Project.__table__.columns}
    assert columns == {
        "id",
        "user_id",
        "github_repo",
        "display_name",
        "description",
        "public",
        "created_at",
    }


def test_package_mapping_table_name() -> None:
    assert PackageMapping.__tablename__ == "package_mappings"


def test_package_mapping_has_required_columns() -> None:
    columns = {c.name for c in PackageMapping.__table__.columns}
    assert columns == {"id", "project_id", "source", "package_name"}
