"""Authentication domain (Supabase Auth behind FastAPI; React never talks to Supabase).

    router.py           /api/auth routes (HTTP only)
    service.py          signup / login / logout / refresh / current user + error translation
    models.py           request/response models (no tokens in responses)
    dependencies.py     get_current_user / require_authenticated_user for other APIs
    cookies.py          HttpOnly session cookies
    supabase_client.py  the only Supabase-aware module
"""

from fastapi import FastAPI

from .router import auth_error_handler, router
from .service import AuthError


def register(app: FastAPI) -> None:
    app.include_router(router)
    app.add_exception_handler(AuthError, auth_error_handler)
