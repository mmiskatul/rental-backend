from pydantic import BaseModel


class TrendPoint(BaseModel):
    month: str
    revenue: float
    bookings: int


class FleetUtilizationPoint(BaseModel):
    name: str
    value: int


class StatusDistributionPoint(BaseModel):
    name: str
    value: int


class TopCarPoint(BaseModel):
    name: str
    bookings: int
    revenue: float
    utilization: int


class AdminOverview(BaseModel):
    total_cars: int
    available_cars: int
    booked_cars: int
    total_customers: int
    total_bookings: int
    active_bookings: int
    pending_requests: int
    monthly_revenue: float
    fleet_utilization: int
    revenue_trend: list[TrendPoint]
    fleet_distribution: list[FleetUtilizationPoint]


class AdminReports(BaseModel):
    total_revenue: float
    total_bookings: int
    average_booking: float
    average_rating: float
    revenue_trend: list[TrendPoint]
    status_distribution: list[StatusDistributionPoint]
    top_cars: list[TopCarPoint]
