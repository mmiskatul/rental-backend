from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ReturnDocument

from app.api.routes.auth import get_current_user
from app.api.routes.cars import serialize_car
from app.db.mongodb import get_cars_collection, get_favorites_collection
from app.schemas.cars import CarPublic, MessageResponse

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=list[CarPublic])
async def list_favorites(current_user: Annotated[dict, Depends(get_current_user)]) -> list[CarPublic]:
    user_id = str(current_user["_id"])
    favorite_docs = [
        favorite async for favorite in get_favorites_collection().find({"user_id": user_id}).sort("created_at", -1)
    ]
    car_ids = [ObjectId(favorite["car_id"]) for favorite in favorite_docs if ObjectId.is_valid(favorite["car_id"])]
    if not car_ids:
        return []

    cars = [car async for car in get_cars_collection().find({"_id": {"$in": car_ids}})]
    cars_by_id = {str(car["_id"]): car for car in cars}
    return [serialize_car(cars_by_id[str(car_id)]) for car_id in car_ids if str(car_id) in cars_by_id]


@router.post("/{car_id}", response_model=CarPublic)
async def add_favorite(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CarPublic:
    object_id = parse_car_id(car_id)
    car = await get_cars_collection().find_one({"_id": object_id})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    now = datetime.now(timezone.utc)
    await get_favorites_collection().find_one_and_update(
        {"user_id": str(current_user["_id"]), "car_id": car_id},
        {
            "$setOnInsert": {
                "user_id": str(current_user["_id"]),
                "car_id": car_id,
                "created_at": now,
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return serialize_car(car)


@router.delete("/{car_id}", response_model=MessageResponse)
async def remove_favorite(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MessageResponse:
    parse_car_id(car_id)
    await get_favorites_collection().delete_one({"user_id": str(current_user["_id"]), "car_id": car_id})
    return MessageResponse(message="Favorite removed.")


def parse_car_id(car_id: str) -> ObjectId:
    if not ObjectId.is_valid(car_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return ObjectId(car_id)
