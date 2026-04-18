from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Rental Sphere API"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:3000"

    mongodb_uri: str
    mongodb_db_name: str = "rental_sphere"

    jwt_access_secret: str
    jwt_refresh_secret: str
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    reset_token_expire_minutes: int = Field(default=30, ge=1)
    verification_code_expire_minutes: int = Field(default=10, ge=1)

    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str = "Rental Sphere"
    smtp_use_tls: bool = True

    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    cloudinary_folder: str = "rental-sphere/cars"

    seed_admin_email: str = "admin@rentalsphere.com"
    seed_admin_password: str = "Admin12345"
    seed_admin_name: str = "Rental Sphere Admin"
    seed_customer_email: str = "customer@rentalsphere.com"
    seed_customer_password: str = "Customer12345"
    seed_customer_name: str = "Rental Sphere Customer"

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8", extra="ignore")

    @property
    def access_token_delta(self) -> timedelta:
        return timedelta(minutes=self.access_token_expire_minutes)

    @property
    def refresh_token_delta(self) -> timedelta:
        return timedelta(days=self.refresh_token_expire_days)

    @property
    def reset_token_delta(self) -> timedelta:
        return timedelta(minutes=self.reset_token_expire_minutes)

    @property
    def verification_code_delta(self) -> timedelta:
        return timedelta(minutes=self.verification_code_expire_minutes)


settings = Settings()
