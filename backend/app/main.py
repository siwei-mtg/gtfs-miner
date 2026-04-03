from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.database import Base, engine
from .api.endpoints import projects
from .api.websockets import progress

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(
    projects.router,
    prefix=f"{settings.API_V1_STR}/projects",
    tags=["Projects"]
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
