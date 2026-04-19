from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.bookings import router as bookings_router
from app.api.routes.cars import router as cars_router
from app.api.routes.customers import router as customers_router
from app.api.routes.customer_settings import router as customer_settings_router
from app.api.routes.favorites import router as favorites_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.overview import router as overview_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.settings import router as settings_router
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
app.include_router(bookings_router)
app.include_router(customers_router)
app.include_router(customer_settings_router)
app.include_router(favorites_router)
app.include_router(notifications_router)
app.include_router(overview_router)
app.include_router(reviews_router)
app.include_router(settings_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "rental-sphere-backend"}
