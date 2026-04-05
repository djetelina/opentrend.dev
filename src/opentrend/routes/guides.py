from pathlib import Path

import frontmatter
import markdown
from litestar import Controller, get
from litestar.connection import Request
from litestar.exceptions import NotFoundException
from litestar.response import Template

from opentrend.models.user import User
from opentrend.routes import safe_redirect_url

GUIDES_DIR = Path(__file__).parent.parent / "guides" / "packaging"


def _load_guide(ecosystem: str) -> dict | None:
    path = (GUIDES_DIR / f"{ecosystem}.md").resolve()
    if not path.is_relative_to(GUIDES_DIR.resolve()) or not path.exists():
        return None

    post = frontmatter.load(str(path))
    md = markdown.Markdown(extensions=["fenced_code", "codehilite", "tables"])
    html = md.convert(post.content.strip())

    return {**post.metadata, "html": html}


def _list_guides() -> list[dict]:
    guides = []
    for path in sorted(GUIDES_DIR.glob("*.md")):
        post = frontmatter.load(str(path))
        if post.metadata:
            meta = {**post.metadata, "slug": path.stem}
            guides.append(meta)
    return guides


class GuidesController(Controller):
    path = "/guides"

    @get("/packaging/{ecosystem:str}", name="guides:packaging")
    async def packaging_guide(
        self, request: Request, ecosystem: str, user: User | None
    ) -> Template:
        guide = _load_guide(ecosystem)
        if guide is None:
            raise NotFoundException(f"No packaging guide for '{ecosystem}'")

        all_guides = _list_guides()
        back_url = safe_redirect_url(request.query_params.get("from", ""), fallback="")

        return Template(
            template_name="guides/packaging.html",
            context={
                "guide": guide,
                "ecosystem": ecosystem,
                "all_guides": all_guides,
                "back_url": back_url,
                "user": user,
            },
        )
