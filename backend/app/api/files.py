"""管理员：本站磁盘占用与安装根目录浏览。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.deps import require_admin
from app.models.user import User
from app.services import file_manager as files_svc

router = APIRouter(prefix="/settings/files", tags=["settings"])


class FileKindTotalOut(BaseModel):
    kind: str
    label: str
    size_bytes: int
    file_count: int


class FileBusinessTotalOut(BaseModel):
    business: str
    label: str
    size_bytes: int
    file_count: int


class FileVolumeOut(BaseModel):
    id: str
    label: str
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int


class FileBucketOut(BaseModel):
    id: str
    label: str
    description: str
    business: str
    business_label: str
    kind: str
    kind_label: str
    path: str
    exists: bool
    optional: bool = False
    size_bytes: int
    file_count: int
    browse_root_id: str | None = None
    browse_path: str = ""


class FileBrowseRootOut(BaseModel):
    id: str
    label: str
    path: str
    exists: bool


class FileSummaryOut(BaseModel):
    measured_at: str
    total_bytes: int
    total_files: int
    kind_totals: list[FileKindTotalOut] = Field(default_factory=list)
    business_totals: list[FileBusinessTotalOut] = Field(default_factory=list)
    volumes: list[FileVolumeOut] = Field(default_factory=list)
    buckets: list[FileBucketOut] = Field(default_factory=list)
    roots: list[FileBrowseRootOut] = Field(default_factory=list)


class FileBrowseEntryOut(BaseModel):
    name: str
    is_dir: bool
    size: int = 0
    modified_at: str | None = None
    sensitive: bool = False
    downloadable: bool = False


class FileBrowseOut(BaseModel):
    root_id: str
    root_label: str
    path: str
    abs_path: str
    entries: list[FileBrowseEntryOut] = Field(default_factory=list)


@router.get("/summary", response_model=FileSummaryOut)
def files_summary(
    _: User = Depends(require_admin),
    force: bool = Query(default=False, description="忽略占用缓存，重新扫描"),
) -> FileSummaryOut:
    if force:
        files_svc.clear_size_cache()
    summary = files_svc.build_summary()
    return FileSummaryOut(
        measured_at=summary.measured_at,
        total_bytes=summary.total_bytes,
        total_files=summary.total_files,
        kind_totals=[
            FileKindTotalOut(
                kind=row.kind,
                label=row.label,
                size_bytes=row.size_bytes,
                file_count=row.file_count,
            )
            for row in summary.kind_totals
        ],
        business_totals=[
            FileBusinessTotalOut(
                business=row.business,
                label=row.label,
                size_bytes=row.size_bytes,
                file_count=row.file_count,
            )
            for row in summary.business_totals
        ],
        volumes=[
            FileVolumeOut(
                id=row.id,
                label=row.label,
                path=row.path,
                total_bytes=row.total_bytes,
                used_bytes=row.used_bytes,
                free_bytes=row.free_bytes,
            )
            for row in summary.volumes
        ],
        buckets=[
            FileBucketOut(
                id=row.id,
                label=row.label,
                description=row.description,
                business=row.business,
                business_label=row.business_label,
                kind=row.kind,
                kind_label=row.kind_label,
                path=row.path,
                exists=row.exists,
                optional=row.optional,
                size_bytes=row.size_bytes,
                file_count=row.file_count,
                browse_root_id=row.browse_root_id,
                browse_path=row.browse_path,
            )
            for row in summary.buckets
        ],
        roots=[
            FileBrowseRootOut(
                id=row.id,
                label=row.label,
                path=files_svc.native_path(row.path),
                exists=row.exists,
            )
            for row in summary.roots
        ],
    )


@router.get("/browse", response_model=FileBrowseOut)
def files_browse(
    _: User = Depends(require_admin),
    root_id: str = Query(..., min_length=1, max_length=64),
    path: str = Query("", max_length=2048),
) -> FileBrowseOut:
    try:
        listing = files_svc.list_directory(root_id, path)
    except files_svc.FileManagerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileBrowseOut(
        root_id=listing.root_id,
        root_label=listing.root_label,
        path=listing.path,
        abs_path=listing.abs_path,
        entries=[
            FileBrowseEntryOut(
                name=row.name,
                is_dir=row.is_dir,
                size=row.size,
                modified_at=row.modified_at,
                sensitive=row.sensitive,
                downloadable=row.downloadable,
            )
            for row in listing.entries
        ],
    )


@router.get("/download")
def files_download(
    _: User = Depends(require_admin),
    root_id: str = Query(..., min_length=1, max_length=64),
    path: str = Query(..., min_length=1, max_length=2048),
) -> FileResponse:
    try:
        target = files_svc.resolve_download(root_id, path)
    except files_svc.FileManagerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    filename = target.name
    quoted = quote(filename)
    return FileResponse(
        target,
        media_type="application/octet-stream",
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
