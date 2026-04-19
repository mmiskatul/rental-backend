from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NotificationType = Literal["approval", "rejected", "reminder", "system", "booking", "pickup", "return", "review"]


class NotificationPublic(BaseModel):
    id: str
    user_id: str | None = None
    role: str | None = None
    type: NotificationType
    title: str
    description: str
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationPublic]
    unread_count: int
