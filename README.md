# Rental Sphere Backend

FastAPI backend for Rental Sphere authentication using Pydantic, MongoDB Atlas, JWT tokens, and SMTP password reset emails.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with your MongoDB Atlas URI, JWT secrets, and SMTP account.

Run from the project root:

```bash
npm run backend:dev
```

Or run directly from `backend`:

```bash
python -m uvicorn app.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /api/auth/register`
- `POST /api/auth/verify-email`
- `POST /api/auth/resend-verification`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/change-password`
- `PATCH /api/auth/profile`
- `POST /api/cars`
- `GET /api/cars`
- `GET /api/cars/{car_id}`

Protected endpoints require:

```http
Authorization: Bearer <accessToken>
```

## Add Car Upload

`POST /api/cars` is protected and expects `multipart/form-data`.

Required fields:

- `title`
- `brand`
- `model`
- `year`
- `price_per_day`
- `location`
- `image`

Optional fields:

- `description`
- `seats`
- `transmission`
- `fuel_type`

The backend uploads `image` to Cloudinary, receives `secure_url` and `public_id`, then saves those values with the car document in MongoDB.

## Authentication Flow

Registration creates an inactive login session and sends a 6-digit verification code by SMTP.

1. `POST /api/auth/register`
2. Redirect the user to `/verify-email`
3. `POST /api/auth/verify-email` with `email` and `code`
4. Backend returns tokens and also sets HTTP-only cookies:
   - `access_token`
   - `refresh_token`

Use `POST /api/auth/refresh` when the access token expires. The backend reads the refresh token from the HTTP-only cookie, rotates tokens, and sets fresh cookies.

First backend startup seeds one verified admin and one verified customer from `.env`:

- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`
- `SEED_CUSTOMER_EMAIL`
- `SEED_CUSTOMER_PASSWORD`
