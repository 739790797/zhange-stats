"""Minecraft 服内文件管理（管理员，经 Pelican）。"""

from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services import minecraft_files as files_svc
from app.services import pelican_client as pelican

router = APIRouter(prefix="/files", tags=["minecraft"])
_FEATURE = Depends(require_feature("guides.minecraft"))


class MinecraftFileEntryOut(BaseModel):
    name: str
    is_file: bool
    is_symlink: bool = False
    size: int = 0
    mode: str = ""
    mode_bits: str = ""
    mimetype: str = ""
    created_at: str | None = None
    modified_at: str | None = None


class MinecraftFileListOut(BaseModel):
    directory: str
    entries: list[MinecraftFileEntryOut] = Field(default_factory=list)


class MinecraftFileContentsOut(BaseModel):
    path: str
    content: str


class MinecraftFileWriteIn(BaseModel):
    path: str
    content: str = ""


class MinecraftFileOkOut(BaseModel):
    ok: bool = True
    path: str = ""
    name: str = ""


class MinecraftFileDownloadOut(BaseModel):
    path: str
    url: str


class MinecraftFileCreateFolderIn(BaseModel):
    directory: str = "/"
    name: str


class MinecraftFileCreateFileIn(BaseModel):
    directory: str = "/"
    name: str
    content: str = ""


class MinecraftFileRenameIn(BaseModel):
    directory: str = "/"
    src: str
    dest: str


class MinecraftFileCopyIn(BaseModel):
    path: str


class MinecraftFileDeleteIn(BaseModel):
    directory: str = "/"
    names: list[str] = Field(min_length=1)


class MinecraftFileCompressIn(BaseModel):
    directory: str = "/"
    names: list[str] = Field(min_length=1)
    archive_name: str | None = None
    extension: Literal["zip", "tar.gz", "tgz", "tar.xz", "txz", "tar.bz2", "tbz2"] = "zip"


class MinecraftFileDecompressIn(BaseModel):
    directory: str = "/"
    name: str


class MinecraftFileChmodIn(BaseModel):
    directory: str = "/"
    names: list[str] = Field(min_length=1)
    mode: str


class MinecraftFilePullIn(BaseModel):
    directory: str = "/"
    url: str
    filename: str = ""


def _map_err(exc: Exception) -> NoReturn:
    if isinstance(exc, files_svc.MinecraftFilesError):
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    if isinstance(exc, pelican.PelicanError):
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message) from exc
    raise exc


@router.get("", response_model=MinecraftFileListOut, dependencies=[_FEATURE])
def minecraft_files_list(
    directory: str = Query("/"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileListOut:
    try:
        data = files_svc.list_directory(db, directory)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileListOut.model_validate(data)


@router.get("/contents", response_model=MinecraftFileContentsOut, dependencies=[_FEATURE])
def minecraft_files_contents(
    path: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileContentsOut:
    try:
        data = files_svc.read_file(db, path)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileContentsOut.model_validate(data)


@router.put("/contents", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_write(
    body: MinecraftFileWriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.write_file(db, body.path, body.content)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, path=body.path)


@router.get("/download", response_model=MinecraftFileDownloadOut, dependencies=[_FEATURE])
def minecraft_files_download(
    path: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileDownloadOut:
    try:
        data = files_svc.download_url(db, path)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileDownloadOut.model_validate(data)


@router.post("/upload", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
async def minecraft_files_upload(
    directory: str = Form("/"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    raw = await file.read()
    filename = file.filename or "upload.bin"
    try:
        data = files_svc.upload_file(db, directory, filename, raw)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, path=data["path"], name=data["name"])


@router.post("/create-folder", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_create_folder(
    body: MinecraftFileCreateFolderIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.create_folder(db, body.directory, body.name)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, name=body.name)


@router.post("/create-file", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_create_file(
    body: MinecraftFileCreateFileIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        data = files_svc.create_file(db, body.directory, body.name, body.content)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, path=data["path"], name=body.name)


@router.post("/rename", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_rename(
    body: MinecraftFileRenameIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.rename_entry(db, body.directory, body.src, body.dest)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, name=body.dest)


@router.post("/copy", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_copy(
    body: MinecraftFileCopyIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.copy_entry(db, body.path)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, path=body.path)


@router.post("/delete", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_delete(
    body: MinecraftFileDeleteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.delete_entries(db, body.directory, body.names)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True)


@router.post("/compress", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_compress(
    body: MinecraftFileCompressIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        created = files_svc.compress_entries(
            db,
            body.directory,
            body.names,
            archive_name=body.archive_name,
            extension=body.extension,
        )
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    name = str((created or {}).get("name") or "")
    return MinecraftFileOkOut(ok=True, name=name)


@router.post("/decompress", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_decompress(
    body: MinecraftFileDecompressIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.decompress_entry(db, body.directory, body.name)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, name=body.name)


@router.post("/chmod", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_chmod(
    body: MinecraftFileChmodIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.chmod_entries(db, body.directory, body.names, body.mode)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True)


@router.post("/pull", response_model=MinecraftFileOkOut, dependencies=[_FEATURE])
def minecraft_files_pull(
    body: MinecraftFilePullIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftFileOkOut:
    try:
        files_svc.pull_remote(db, body.directory, body.url, body.filename)
    except (files_svc.MinecraftFilesError, pelican.PelicanError) as exc:
        _map_err(exc)
    return MinecraftFileOkOut(ok=True, name=body.filename)
