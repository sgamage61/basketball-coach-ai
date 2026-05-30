from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["root"])


class RootResponse(BaseModel):
    message: str


@router.get("/", response_model=RootResponse, summary="Root")
async def root() -> RootResponse:
    return RootResponse(message="API is running")
