from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="enterprise/templates")


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})


@router.get("/{page}", response_class=HTMLResponse, include_in_schema=False)
def page(request: Request, page: str):
    allowed = {"dashboard", "runs", "agents", "workspaces", "integrations", "audit", "billing", "admin"}
    if page not in allowed:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(f"{page}.html", {"request": request, "title": page.title()})

