from app.api.routes.health import router as health_router
from app.api.routes.batch import router as batch_router
from app.api.routes.settings import router as settings_router
from app.api.routes.issues import router as issues_router

__all__ = [
    "health_router",
    "batch_router",
    "settings_router",
    "issues_router",
]