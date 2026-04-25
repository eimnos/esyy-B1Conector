from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...deps import get_db
from ...services.source_db_metadata_service import (
    SourceDBMetadataError,
    get_effective_source_engine,
    list_columns,
    list_objects,
)

router = APIRouter(prefix="/api/query-builder", tags=["query-builder"])


@router.get("/context")
def query_builder_context(db: Session = Depends(get_db)) -> dict[str, str]:
    return {"engine": get_effective_source_engine(db)}


@router.get("/objects")
def query_builder_objects(
    db: Session = Depends(get_db),
    search: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    try:
        return list_objects(db, search=search, limit=limit)
    except SourceDBMetadataError as exc:
        raise HTTPException(status_code=400, detail=f"Errore lettura catalogo DB: {exc}") from exc


@router.get("/columns")
def query_builder_columns(
    db: Session = Depends(get_db),
    schema_name: str = Query(...),
    object_name: str = Query(...),
) -> dict:
    try:
        return list_columns(db, schema_name=schema_name, object_name=object_name)
    except SourceDBMetadataError as exc:
        raise HTTPException(status_code=400, detail=f"Errore lettura colonne: {exc}") from exc
