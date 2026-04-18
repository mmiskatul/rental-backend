from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import settings

client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global client, database

    client = AsyncIOMotorClient(settings.mongodb_uri)
    database = client[settings.mongodb_db_name]
    await database.users.create_index("email", unique=True)
    await database.cars.create_index("owner_id")
    await database.cars.create_index("created_at")
    await database.bookings.create_index("customer_id")
    await database.bookings.create_index("car_id")
    await database.bookings.create_index("status")
    await database.bookings.create_index("created_at")


async def close_mongo_connection() -> None:
    if client:
        client.close()


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("MongoDB is not connected.")
    return database


def get_users_collection() -> AsyncIOMotorCollection:
    return get_database().users


def get_cars_collection() -> AsyncIOMotorCollection:
    return get_database().cars


def get_bookings_collection() -> AsyncIOMotorCollection:
    return get_database().bookings
