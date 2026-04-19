from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    booking_id: str
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=1000)


class ReviewPublic(BaseModel):
    id: str
    booking_id: str
    car_id: str
    car_title: str
    customer_id: str
    customer_name: str
    customer_email: str
    rating: int
    comment: str
    created_at: datetime
    updated_at: datetime
