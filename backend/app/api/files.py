"""管理员：本站磁盘占用与安装根目录浏览。"""

from __future__ import annotations

from typing import NoReturn
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

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
    editable: bool = False


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
                editable=row.editable,
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


class FileOkOut(BaseModel):
    ok: bool = True
    root_id: str = ""
    path: str = ""
    name: str = ""
    kept_sensitive: bool = False


class FileContentsOut(BaseModel):
    root_id: str
    path: str
    name: str = ""
    content: str = ""


class FileDirOpIn(BaseModel):
    root_id: str = Field(..., min_length=1, max_length=64)
    path: str = Field("", max_length=2048)
    name: str = Field(..., min_length=1, max_length=255)


class FileCreateFileIn(FileDirOpIn):
    content: str = Field("", max_length=files_svc.MAX_EDIT_BYTES)


class FileRenameIn(BaseModel):
    root_id: str = Field(..., min_length=1, max_length=64)
    path: str = Field("", max_length=2048)
    src: str = Field(..., min_length=1, max_length=255)
    dest: str = Field(..., min_length=1, max_length=255)


class FileDeleteIn(BaseModel):
    root_id: str = Field(..., min_length=1, max_length=64)
    path: str = Field("", max_length=2048)
    names: list[str] = Field(min_length=1, max_length=files_svc.MAX_DELETE_NAMES)

    @field_validator("names")
    @classmethod
    def _names_not_blank(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if (item or "").strip()]
        if not cleaned:
            raise ValueError("请选择要删除的文件")
        return cleaned


class FileWriteIn(BaseModel):
    root_id: str = Field(..., min_length=1, max_length=64)
    path: str = Field(..., min_length=1, max_length=2048)
    content: str = Field("", max_length=files_svc.MAX_EDIT_BYTES)


def _ok(result: files_svc.MutateResult) -> FileOkOut:
    return FileOkOut(
        ok=True,
        root_id=result.root_id,
        path=result.path,
        name=result.name,
        kept_sensitive=result.kept_sensitive,
    )


def _raise_fm(exc: files_svc.FileManagerError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contents", response_model=FileContentsOut)
def files_contents(
    _: User = Depends(require_admin),
    root_id: str = Query(..., min_length=1, max_length=64),
    path: str = Query(..., min_length=1, max_length=2048),
) -> FileContentsOut:
    try:
        result = files_svc.read_text(root_id, path)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return FileContentsOut(
        root_id=result.root_id,
        path=result.path,
        name=result.name,
        content=result.content,
    )


@router.put("/contents", response_model=FileOkOut)
def files_write(
    body: FileWriteIn,
    _: User = Depends(require_admin),
) -> FileOkOut:
    try:
        result = files_svc.write_text(body.root_id, body.path, body.content)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)


@router.post("/upload", response_model=FileOkOut)
async def files_upload(
    _: User = Depends(require_admin),
    root_id: str = Form(..., min_length=1, max_length=64),
    path: str = Form("", max_length=2048),
    file: UploadFile = File(...),
) -> FileOkOut:
    raw = await file.read()
    filename = file.filename or "upload.bin"
    try:
        result = files_svc.upload_file(root_id, path, filename, raw)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)


@router.post("/create-folder", response_model=FileOkOut)
def files_create_folder(
    body: FileDirOpIn,
    _: User = Depends(require_admin),
) -> FileOkOut:
    try:
        result = files_svc.create_folder(body.root_id, body.path, body.name)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)


@router.post("/create-file", response_model=FileOkOut)
def files_create_file(
    body: FileCreateFileIn,
    _: User = Depends(require_admin),
) -> FileOkOut:
    try:
        result = files_svc.create_file(
            body.root_id, body.path, body.name, body.content
        )
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)


@router.post("/rename", response_model=FileOkOut)
def files_rename(
    body: FileRenameIn,
    _: User = Depends(require_admin),
) -> FileOkOut:
    try:
        result = files_svc.rename_entry(body.root_id, body.path, body.src, body.dest)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)


@router.post("/delete", response_model=FileOkOut)
def files_delete(
    body: FileDeleteIn,
    _: User = Depends(require_admin),
) -> FileOkOut:
    try:
        result = files_svc.delete_entries(body.root_id, body.path, body.names)
    except files_svc.FileManagerError as exc:
        _raise_fm(exc)
    return _ok(result)

