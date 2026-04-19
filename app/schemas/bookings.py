from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

BookingStatus = Literal[
    "pending",
    "approved",
    "pickup_requested",
    "rejected",
    "active",
    "return_requested",
    "completed",
    "cancelled",
]
PaymentStatus = Literal["paid", "pending", "refunded"]


class BookingCreate(BaseModel):
    car_id: str
    start_date: date
    end_date: date
    pickup_location: str = Field(min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)


class BookingStatusUpdate(BaseModel):
    status: BookingStatus
    notes: str | None = Field(default=None, max_length=1000)


class BookingPublic(BaseModel):
    id: str
    car_id: str
    car_title: str
    car_image_url: str | None = None
    customer_id: str
    customer_name: str
    customer_email: str
    customer_phone: str | None = None
    start_date: date
    end_date: date
    days: int
    pickup_location: str
    total: float
    status: BookingStatus
    payment_status: PaymentStatus
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
