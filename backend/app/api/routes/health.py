from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return a static payload indicating the API is up."""

    return {"status": "ok"}
