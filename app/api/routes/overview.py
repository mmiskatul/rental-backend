from calendar import month_abbr
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_bookings_collection, get_cars_collection, get_reviews_collection, get_users_collection
from app.schemas.overview import AdminOverview, AdminReports, FleetUtilizationPoint, StatusDistributionPoint, TopCarPoint, TrendPoint

router = APIRouter(prefix="/api/admin", tags=["admin"])

ACTIVE_STATUSES = {"approved", "pickup_requested", "active", "return_requested"}
REVENUE_STATUSES = {"approved", "pickup_requested", "active", "return_requested", "completed"}


@router.get("/overview", response_model=AdminOverview)
async def get_admin_overview(current_user: Annotated[dict, Depends(get_current_user)]) -> AdminOverview:
    require_admin(current_user)

    cars = await get_cars_collection().find().to_list(length=None)
    bookings = await get_bookings_collection().find().to_list(length=None)
    total_customers = await get_users_collection().count_documents({"role": "customer"})

    total_cars = len(cars)
    booked_car_ids = {booking["car_id"] for booking in bookings if booking.get("status") in ACTIVE_STATUSES}
    booked_cars = len(booked_car_ids)
    available_cars = max(total_cars - booked_cars, 0)
    active_bookings = sum(1 for booking in bookings if booking.get("status") in ACTIVE_STATUSES)
    pending_requests = sum(1 for booking in bookings if booking.get("status") in {"pending", "return_requested"})
    monthly_revenue = calculate_current_month_revenue(bookings)
    fleet_utilization = round((booked_cars / total_cars) * 100) if total_cars else 0

    return AdminOverview(
        total_cars=total_cars,
        available_cars=available_cars,
        booked_cars=booked_cars,
        total_customers=total_customers,
        total_bookings=len(bookings),
        active_bookings=active_bookings,
        pending_requests=pending_requests,
        monthly_revenue=monthly_revenue,
        fleet_utilization=fleet_utilization,
        revenue_trend=build_revenue_trend(bookings),
        fleet_distribution=[
            FleetUtilizationPoint(name="Available", value=available_cars),
            FleetUtilizationPoint(name="Booked", value=booked_cars),
        ],
    )


@router.get("/reports", response_model=AdminReports)
async def get_admin_reports(current_user: Annotated[dict, Depends(get_current_user)]) -> AdminReports:
    require_admin(current_user)

    cars = await get_cars_collection().find().to_list(length=None)
    bookings = await get_bookings_collection().find().to_list(length=None)
    reviews = await get_reviews_collection().find().to_list(length=None)
    revenue_bookings = [booking for booking in bookings if booking.get("status") in REVENUE_STATUSES]
    total_revenue = round(sum(float(booking.get("total", 0)) for booking in revenue_bookings), 2)
    total_bookings = len(bookings)
    average_booking = round(total_revenue / len(revenue_bookings), 2) if revenue_bookings else 0
    average_rating = round(sum(int(review.get("rating", 0)) for review in reviews) / len(reviews), 1) if reviews else 0

    return AdminReports(
        total_revenue=total_revenue,
        total_bookings=total_bookings,
        average_booking=average_booking,
        average_rating=average_rating,
        revenue_trend=build_revenue_trend(bookings),
        status_distribution=build_status_distribution(bookings),
        top_cars=build_top_cars(cars, bookings),
    )


def calculate_current_month_revenue(bookings: list[dict]) -> float:
    now = datetime.now(timezone.utc)
    return round(
        sum(
            float(booking.get("total", 0))
            for booking in bookings
            if booking.get("status") in REVENUE_STATUSES and to_datetime(booking.get("created_at")).year == now.year and to_datetime(booking.get("created_at")).month == now.month
        ),
        2,
    )


def build_revenue_trend(bookings: list[dict]) -> list[TrendPoint]:
    now = datetime.now(timezone.utc)
    months = []
    for offset in range(5, -1, -1):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    points = []
    for year, month in months:
        month_bookings = [
            booking
            for booking in bookings
            if to_datetime(booking.get("created_at")).year == year and to_datetime(booking.get("created_at")).month == month
        ]
        revenue = sum(float(booking.get("total", 0)) for booking in month_bookings if booking.get("status") in REVENUE_STATUSES)
        points.append(TrendPoint(month=month_abbr[month], revenue=round(revenue, 2), bookings=len(month_bookings)))
    return points


def build_status_distribution(bookings: list[dict]) -> list[StatusDistributionPoint]:
    labels = {
        "pending": "Pending",
        "approved": "Approved",
        "pickup_requested": "Pickup Requested",
        "active": "Active",
        "return_requested": "Return Requested",
        "completed": "Completed",
        "rejected": "Rejected",
        "cancelled": "Cancelled",
    }
    counts: dict[str, int] = {}
    for booking in bookings:
        status_value = booking.get("status", "pending")
        counts[status_value] = counts.get(status_value, 0) + 1
    return [StatusDistributionPoint(name=labels.get(status_value, status_value.title()), value=count) for status_value, count in counts.items()]


def build_top_cars(cars: list[dict], bookings: list[dict]) -> list[TopCarPoint]:
    cars_by_id = {str(car["_id"]): car for car in cars}
    totals: dict[str, dict[str, float | int | str]] = {}
    for booking in bookings:
        car_id = booking.get("car_id")
        if not car_id:
            continue
        entry = totals.setdefault(
            car_id,
            {
                "name": cars_by_id.get(car_id, {}).get("title", booking.get("car_title", "Unknown car")),
                "bookings": 0,
                "revenue": 0.0,
            },
        )
        entry["bookings"] = int(entry["bookings"]) + 1
        if booking.get("status") in REVENUE_STATUSES:
            entry["revenue"] = float(entry["revenue"]) + float(booking.get("total", 0))

    max_bookings = max((int(entry["bookings"]) for entry in totals.values()), default=0)
    rows = [
        TopCarPoint(
            name=str(entry["name"]),
            bookings=int(entry["bookings"]),
            revenue=round(float(entry["revenue"]), 2),
            utilization=round((int(entry["bookings"]) / max_bookings) * 100) if max_bookings else 0,
        )
        for entry in totals.values()
    ]
    return sorted(rows, key=lambda item: (item.revenue, item.bookings), reverse=True)[:5]


def to_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.now(timezone.utc)


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")
