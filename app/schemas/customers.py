from datetime import datetime

from pydantic import BaseModel


class CustomerPublic(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None = None
    joined_at: datetime
    total_bookings: int
    active_bookings: int
    total_spend: float
    status: str
