from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import FileAssetOut
from app.services import content as content_svc

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=FileAssetOut)
async def upload_file(file: UploadFile, db: AsyncSession = Depends(get_db)):
    data = await file.read()
    asset = await content_svc.create_file_asset(
        db,
        data=data,
        mime_type=file.content_type,
        original_filename=file.filename,
    )
    await db.commit()
    return asset
