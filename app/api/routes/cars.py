from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_bookings_collection, get_cars_collection
from app.schemas.cars import CarCategoryPublic, CarPublic, MessageResponse, TrendingCarPublic
from app.services.cloudinary_upload import upload_car_image

router = APIRouter(prefix="/api/cars", tags=["cars"])


@router.post("", response_model=CarPublic, status_code=status.HTTP_201_CREATED)
async def create_car(
    current_user: Annotated[dict, Depends(get_current_user)],
    title: Annotated[str, Form(min_length=2, max_length=120)],
    brand: Annotated[str, Form(min_length=1, max_length=80)],
    model: Annotated[str, Form(min_length=1, max_length=80)],
    year: Annotated[int, Form(ge=1990, le=2100)],
    price_per_day: Annotated[float, Form(gt=0)],
    location: Annotated[str, Form(min_length=2, max_length=120)],
    image: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=1000)] = None,
    seats: Annotated[int | None, Form(ge=1, le=20)] = None,
    transmission: Annotated[str | None, Form(max_length=40)] = None,
    fuel_type: Annotated[str | None, Form(max_length=40)] = None,
) -> CarPublic:
    require_admin(current_user)
    require_image_upload(image)

    upload_result = await upload_car_image(image)
    now = datetime.now(timezone.utc)
    car = {
        "owner_id": str(current_user["_id"]),
        "title": title,
        "brand": brand,
        "model": model,
        "year": year,
        "price_per_day": price_per_day,
        "location": location,
        "description": description,
        "seats": seats,
        "transmission": transmission,
        "fuel_type": fuel_type,
        "image_url": upload_result["secure_url"],
        "image_public_id": upload_result["public_id"],
        "created_at": now,
        "updated_at": now,
    }

    result = await get_cars_collection().insert_one(car)
    car["_id"] = result.inserted_id
    return serialize_car(car)


@router.patch("/{car_id}", response_model=CarPublic)
async def update_car(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    title: Annotated[str | None, Form(min_length=2, max_length=120)] = None,
    brand: Annotated[str | None, Form(min_length=1, max_length=80)] = None,
    model: Annotated[str | None, Form(min_length=1, max_length=80)] = None,
    year: Annotated[int | None, Form(ge=1990, le=2100)] = None,
    price_per_day: Annotated[float | None, Form(gt=0)] = None,
    location: Annotated[str | None, Form(min_length=2, max_length=120)] = None,
    image: UploadFile | None = File(default=None),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    seats: Annotated[int | None, Form(ge=1, le=20)] = None,
    transmission: Annotated[str | None, Form(max_length=40)] = None,
    fuel_type: Annotated[str | None, Form(max_length=40)] = None,
) -> CarPublic:
    require_admin(current_user)
    object_id = parse_car_id(car_id)
    updates = {
        "title": title,
        "brand": brand,
        "model": model,
        "year": year,
        "price_per_day": price_per_day,
        "location": location,
        "description": description,
        "seats": seats,
        "transmission": transmission,
        "fuel_type": fuel_type,
    }
    updates = {key: value for key, value in updates.items() if value is not None}

    if image:
        require_image_upload(image)
        upload_result = await upload_car_image(image)
        updates["image_url"] = upload_result["secure_url"]
        updates["image_public_id"] = upload_result["public_id"]

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        result = await get_cars_collection().update_one({"_id": object_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    car = await get_cars_collection().find_one({"_id": object_id})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return serialize_car(car)


@router.delete("/{car_id}", response_model=MessageResponse)
async def delete_car(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MessageResponse:
    require_admin(current_user)
    result = await get_cars_collection().delete_one({"_id": parse_car_id(car_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return MessageResponse(message="Car deleted successfully.")


@router.get("", response_model=list[CarPublic])
async def list_cars() -> list[CarPublic]:
    cars = get_cars_collection().find().sort("created_at", -1)
    return [serialize_car(car) async for car in cars]


@router.get("/trending", response_model=list[TrendingCarPublic])
async def list_trending_cars(limit: int = 3) -> list[TrendingCarPublic]:
    safe_limit = min(max(limit, 1), 12)
    pipeline = [
        {
            "$group": {
                "_id": "$car_id",
                "booking_count": {"$sum": 1},
                "completed_count": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "completed"]}, 1, 0],
                    },
                },
            },
        },
        {"$sort": {"booking_count": -1, "completed_count": -1}},
        {"$limit": safe_limit},
    ]
    stats = [item async for item in get_bookings_collection().aggregate(pipeline)]
    stats_by_car_id = {item["_id"]: item for item in stats if ObjectId.is_valid(item["_id"])}
    object_ids = [ObjectId(car_id) for car_id in stats_by_car_id]

    if object_ids:
        car_docs = [car async for car in get_cars_collection().find({"_id": {"$in": object_ids}})]
        cars_by_id = {str(car["_id"]): car for car in car_docs}
        ordered = [
            serialize_trending_car(cars_by_id[car_id], stats_by_car_id[car_id])
            for car_id in stats_by_car_id
            if car_id in cars_by_id
        ]
        if ordered:
            return ordered

    fallback = get_cars_collection().find().sort("created_at", -1).limit(safe_limit)
    return [serialize_trending_car(car, {"booking_count": 0, "completed_count": 0}) async for car in fallback]


@router.get("/categories", response_model=list[CarCategoryPublic])
async def list_car_categories() -> list[CarCategoryPublic]:
    counts = {car_type: 0 for car_type in ["Luxury", "SUV", "Electric", "Sports", "Sedan", "Compact"]}
    async for car in get_cars_collection().find():
        car_type = infer_car_type(car)
        counts[car_type] = counts.get(car_type, 0) + 1

    return [
        CarCategoryPublic(type=car_type, count=count)
        for car_type, count in counts.items()
        if count > 0
    ]


@router.get("/recommended", response_model=list[CarPublic])
async def list_recommended_cars(
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = 3,
) -> list[CarPublic]:
    safe_limit = min(max(limit, 1), 12)
    user_id = str(current_user["_id"])
    booking_docs = [
        booking async for booking in get_bookings_collection().find({"customer_id": user_id}).sort("created_at", -1).limit(20)
    ]
    booked_car_ids = [booking["car_id"] for booking in booking_docs if ObjectId.is_valid(booking.get("car_id", ""))]

    if booked_car_ids:
        booked_cars = [
            car async for car in get_cars_collection().find({"_id": {"$in": [ObjectId(car_id) for car_id in booked_car_ids]}})
        ]
        preferred_brands = {car["brand"] for car in booked_cars}
        preferred_types = {infer_car_type(car) for car in booked_cars}

        candidates = [
            car async for car in get_cars_collection().find({"_id": {"$nin": [ObjectId(car_id) for car_id in booked_car_ids]}})
        ]
        ranked = sorted(
            candidates,
            key=lambda car: (
                car["brand"] in preferred_brands,
                infer_car_type(car) in preferred_types,
                car.get("created_at", datetime.min.replace(tzinfo=timezone.utc)),
            ),
            reverse=True,
        )
        recommendations = ranked[:safe_limit]
        if recommendations:
            return [serialize_car(car) for car in recommendations]

    fallback = get_cars_collection().find().sort("created_at", -1).limit(safe_limit)
    return [serialize_car(car) async for car in fallback]


@router.get("/{car_id}", response_model=CarPublic)
async def get_car(car_id: str) -> CarPublic:
    car = await get_cars_collection().find_one({"_id": parse_car_id(car_id)})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    return serialize_car(car)


def parse_car_id(car_id: str) -> ObjectId:
    if not ObjectId.is_valid(car_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return ObjectId(car_id)


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")


def require_image_upload(image: UploadFile) -> None:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload an image file.",
        )


def serialize_car(car: dict) -> CarPublic:
    return CarPublic(
        id=str(car["_id"]),
        owner_id=car["owner_id"],
        title=car["title"],
        brand=car["brand"],
        model=car["model"],
        year=car["year"],
        price_per_day=car["price_per_day"],
        location=car["location"],
        description=car.get("description"),
        seats=car.get("seats"),
        transmission=car.get("transmission"),
        fuel_type=car.get("fuel_type"),
        image_url=car["image_url"],
        image_public_id=car["image_public_id"],
        created_at=car["created_at"],
        updated_at=car["updated_at"],
    )


def serialize_trending_car(car: dict, stats: dict) -> TrendingCarPublic:
    return TrendingCarPublic(
        **serialize_car(car).model_dump(),
        booking_count=stats.get("booking_count", 0),
        completed_count=stats.get("completed_count", 0),
    )


def infer_car_type(car: dict) -> str:
    value = f"{car.get('title', '')} {car.get('model', '')}".lower()
    fuel_type = (car.get("fuel_type") or "").lower()
    if "suv" in value or "x5" in value or "rav4" in value:
        return "SUV"
    if "tesla" in value or fuel_type == "electric":
        return "Electric"
    if "porsche" in value or "sport" in value:
        return "Sports"
    if "luxury" in value or "class" in value:
        return "Luxury"
    if "civic" in value or "compact" in value:
        return "Compact"
    return "Sedan"
