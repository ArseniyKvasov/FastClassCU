import httpx
from fastapi import HTTPException


async def upstream_request(base_url: str, method: str, path: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
            return await client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail={"code": "upstream_unavailable", "message": str(exc)}
        ) from exc


def raise_for_upstream_error(response: httpx.Response) -> None:
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = {"code": "upstream_error"}
        # Every upstream service wraps its own errors as {"error": {...}} (see
        # each service's own HTTPException handler); unwrap that one level
        # here so main.py's handler doesn't double-wrap it into
        # {"error": {"error": {...}}} when it re-raises this HTTPException.
        detail = body.get("error", body) if isinstance(body, dict) else body
        raise HTTPException(status_code=response.status_code, detail=detail)
