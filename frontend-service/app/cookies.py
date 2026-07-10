from fastapi import Response

from app.config import settings


def set_session_cookies(response: Response, *, access_token: str, refresh_token: str | None, max_age: int) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        access_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )
    if refresh_token is not None:
        response.set_cookie(
            settings.refresh_cookie_name,
            refresh_token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/auth",
        )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(settings.refresh_cookie_name, path="/auth", domain=settings.cookie_domain)
