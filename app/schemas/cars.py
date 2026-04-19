from datetime import datetime

from pydantic import BaseModel, Field


class CarPublic(BaseModel):
    id: str
    owner_id: str
    title: str
    brand: str
    model: str
    year: int
    price_per_day: float = Field(gt=0)
    location: str
    description: str | None = None
    seats: int | None = None
    transmission: str | None = None
    fuel_type: str | None = None
    image_url: str
    image_public_id: str
    created_at: datetime
    updated_at: datetime


class TrendingCarPublic(CarPublic):
    booking_count: int = 0
    completed_count: int = 0


class CarCategoryPublic(BaseModel):
    type: str
    count: int


class MessageResponse(BaseModel):
    message: str
