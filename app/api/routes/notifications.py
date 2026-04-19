from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_notifications_collection
from app.schemas.cars import MessageResponse
from app.schemas.notifications import NotificationListResponse, NotificationPublic, NotificationType

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(current_user: Annotated[dict, Depends(get_current_user)]) -> NotificationListResponse:
    query = notification_query(current_user)
    cursor = get_notifications_collection().find(query).sort("created_at", -1)
    notifications = [serialize_notification(notification) async for notification in cursor]
    unread_count = await get_notifications_collection().count_documents({**query, "read": False})
    return NotificationListResponse(notifications=notifications, unread_count=unread_count)


@router.patch("/{notification_id}/read", response_model=NotificationPublic)
async def mark_notification_read(
    notification_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> NotificationPublic:
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    query = {"_id": ObjectId(notification_id), **notification_query(current_user)}
    result = await get_notifications_collection().update_one(query, {"$set": {"read": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    notification = await get_notifications_collection().find_one({"_id": ObjectId(notification_id)})
    return serialize_notification(notification)


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(current_user: Annotated[dict, Depends(get_current_user)]) -> MessageResponse:
    await get_notifications_collection().update_many(notification_query(current_user), {"$set": {"read": True}})
    return MessageResponse(message="Notifications marked as read.")


async def create_notification(
    *,
    notification_type: NotificationType,
    title: str,
    description: str,
    user_id: str | None = None,
    role: str | None = None,
) -> None:
    if not user_id and not role:
        raise ValueError("Notification must target a user_id or a role.")

    await get_notifications_collection().insert_one(
        {
            "user_id": user_id,
            "role": role,
            "type": notification_type,
            "title": title,
            "description": description,
            "read": False,
            "created_at": datetime.now(timezone.utc),
        }
    )


def notification_query(user: dict) -> dict:
    return {
        "$or": [
            {"user_id": str(user["_id"])},
            {"role": user.get("role")},
        ]
    }


def serialize_notification(notification: dict) -> NotificationPublic:
    return NotificationPublic(
        id=str(notification["_id"]),
        user_id=notification.get("user_id"),
        role=notification.get("role"),
        type=notification["type"],
        title=notification["title"],
        description=notification["description"],
        read=notification.get("read", False),
        created_at=notification["created_at"],
    )
