from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.cars import router as cars_router
from app.core.config import settings
from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.services.seed import seed_default_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await seed_default_users()
    yield
    await close_mongo_connection()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cars_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "rental-sphere-backend"}
