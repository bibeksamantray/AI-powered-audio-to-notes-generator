import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware

from . import db
from .config import settings
from .routers import lectures
from .utils.logging_config import setup_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    setup_logging()

    app = FastAPI(
        title="AI-Powered Lecture Voice-to-Notes Generator",
        version="1.0.0",
        description=(
            "Local, open-source system for converting lecture audio into "
            "transcripts and AI-generated study notes."
        ),
    )

    # CORS for local frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Sessions (cookie-based)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        session_cookie="session",
        same_site="lax",
    )

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    pages_dir = frontend_dir / "pages"

    # Routers
    app.include_router(lectures.router)

    users_col = db.get_users_collection()

    # Helpers
    async def get_user(email: str):
        return await users_col.find_one({"email": email.lower()})

    def sanitize_email_for_folder(email: str) -> str:
        # Keep it filesystem-safe
        return re.sub(r"[^a-zA-Z0-9_-]", "_", email.lower())

    def hash_password(password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return pwd_context.hash(password)

    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return pwd_context.verify(password, password_hash)
        except Exception:
            return False

    def ensure_user_folder(email: str) -> Path:
        folder = settings.USERS_DIR / sanitize_email_for_folder(email)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def require_auth(request: Request):
        email = request.session.get("user")
        if not email:
            return None
        return email

    # Frontend static assets
    app.mount("/ui/css", StaticFiles(directory=frontend_dir / "css"), name="ui-css")
    app.mount(
        "/ui/javascript",
        StaticFiles(directory=frontend_dir / "javascript"),
        name="ui-js",
    )

    @app.get("/ui/", include_in_schema=False)
    async def serve_home():
        home_path = pages_dir / "Home.html"
        if not home_path.exists():
            raise HTTPException(status_code=500, detail="Frontend home not found")
        return FileResponse(home_path)

    @app.get("/login", include_in_schema=False)
    async def serve_login():
        login_path = pages_dir / "login.html"
        if not login_path.exists():
            raise HTTPException(status_code=500, detail="Login page not found")
        return FileResponse(login_path)

    @app.get("/registration", include_in_schema=False)
    async def serve_registration():
        registration_path = pages_dir / "registration.html"
        if not registration_path.exists():
            raise HTTPException(status_code=500, detail="Registration page not found")
        return FileResponse(registration_path)

    @app.post("/registration", include_in_schema=False)
    async def register_user(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
    ):
        email = email.strip().lower()
        password = password.strip()

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        if "@" not in email:
            raise HTTPException(status_code=400, detail="Enter a valid email")
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        if len(password) > 20:
            raise HTTPException(status_code=400, detail="Password must be at most 20 characters")

        existing = await get_user(email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        user_folder = ensure_user_folder(email)

        await users_col.insert_one(
            {
                "email": email,
                "password_hash": password_hash,
                "created_at": datetime.utcnow(),
                "file_folder": str(user_folder),
            }
        )

        # Do not auto-login; prompt the user to log in
        request.session.clear()
        return {"message": "Registration successful. Please log in."}

    @app.post("/login", include_in_schema=False)
    async def login_user(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
    ):
        email = email.strip().lower()
        password = password.strip()

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")

        user_doc = await get_user(email)
        if not user_doc or not verify_password(password, user_doc.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        request.session["user"] = email
        request.session["user_folder"] = user_doc.get("file_folder")
        return {"message": "Login successful", "redirect": "/index.html"}

    @app.get("/logout", include_in_schema=False)
    async def logout_user(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/index.html", include_in_schema=False)
    async def serve_index(request: Request):
        username = require_auth(request)
        if not username:
            return RedirectResponse(url="/login", status_code=302)

        index_path = pages_dir / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=500, detail="Frontend not found")
        return FileResponse(index_path)

    return app


app = create_app()

