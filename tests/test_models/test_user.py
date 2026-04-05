from opentrend.models.user import User


def test_user_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_has_required_columns() -> None:
    columns = {c.name for c in User.__table__.columns}
    assert columns == {
        "id",
        "github_id",
        "github_username",
        "avatar_url",
        "github_access_token",
        "created_at",
    }
