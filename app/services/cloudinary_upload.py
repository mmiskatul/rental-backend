from fastapi import HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

import cloudinary
import cloudinary.uploader

from app.core.config import settings


cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


async def upload_car_image(image: UploadFile) -> dict:
    try:
        image.file.seek(0)
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            image.file,
            folder=settings.cloudinary_folder,
            resource_type="image",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to upload image to Cloudinary.",
        ) from exc

    secure_url = result.get("secure_url")
    public_id = result.get("public_id")
    if not secure_url or not public_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary did not return an image URL.",
        )

    return {"secure_url": secure_url, "public_id": public_id}
