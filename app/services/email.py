from email.message import EmailMessage
import smtplib

from starlette.concurrency import run_in_threadpool

from app.core.config import settings


async def send_password_reset_email(email: str, reset_code: str) -> None:
    await send_email(
        email,
        "Reset your Rental Sphere password",
        "\n".join(
            [
                "Use this code to reset your Rental Sphere password:",
                reset_code,
                "",
                f"This code expires in {settings.reset_token_expire_minutes} minutes.",
            ]
        ),
    )


async def send_verification_email(email: str, code: str) -> None:
    await send_email(
        email,
        "Verify your Rental Sphere account",
        "\n".join(
            [
                "Use this code to verify your Rental Sphere account:",
                code,
                "",
                f"This code expires in {settings.verification_code_expire_minutes} minutes.",
            ]
        ),
    )


async def send_email(email: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email
    message.set_content(body)

    await run_in_threadpool(send_smtp_message, message)


def send_smtp_message(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
