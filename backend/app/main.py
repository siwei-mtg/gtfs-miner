from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.endpoints import auth, panel, projects
from .api.websockets import progress

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Mount Routers
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Auth"]
)

app.include_router(
    projects.router,
    prefix=f"{settings.API_V1_STR}/projects",
    tags=["Projects"]
)

# Mount compare-transit panel router (public, no auth — Plan 2 §8)
app.include_router(
    panel.router,
    prefix=f"{settings.API_V1_STR}/panel",
    tags=["Panel"],
)

# Mount WebSocket Router
app.include_router(
    progress.router,
    prefix=f"{settings.API_V1_STR}/projects",
    tags=["WebSockets"]
)

@app.get("/")
def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API. Access /docs for swagger UI."}
