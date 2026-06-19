from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from routers.auth import verify_api_key
from services.ingestion_service import ingest_csv
from services.smart_ingestion_service import smart_ingest

router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.post("/import")
async def import_connections(
    member_name: str = Form(...),
    file: UploadFile = File(...),
    _key: str = Depends(verify_api_key),
):
    csv_text = (await file.read()).decode("utf-8-sig")
    result = await ingest_csv(member_name, csv_text)
    return result


@router.post("/import-smart")
async def import_smart(
    member_name: str = Form(...),
    files: list[UploadFile] = File(...),
    _key: str = Depends(verify_api_key),
):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed per upload.")
    if not member_name.strip():
        raise HTTPException(status_code=400, detail="member_name is required.")

    file_pairs: list[tuple[str, bytes]] = []
    for f in files:
        raw = await f.read()
        file_pairs.append((f.filename or "unknown", raw))

    result = await smart_ingest(member_name.strip(), file_pairs)
    return result
