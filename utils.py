import os
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from werkzeug.exceptions import BadRequest, NotFound

from config import AppConfig

def human_size(num_bytes: float) -> str:
    """Convert bytes to a human-readable string (e.g., '1.5 MB')."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"

def detect_type(mimetype: Optional[str]) -> str:
    """Detect the general type of a file based on its mimetype."""
    if not mimetype:
        return "other"
    if mimetype.startswith("video"):
        return "video"
    if mimetype.startswith("image"):
        return "image"
    if mimetype.startswith("audio"):
        return "audio"
    return "other"

def safe_rel_path(rel: str) -> Path:
    """
    Sanitize a relative path string and return a Path object.
    Prevents directory traversal attacks (..).
    """
    rel = rel.strip().replace("\\", "/")
    if rel in ("", ".", "/"):
        return Path(".")
    p = Path(rel)
    if ".." in p.parts:
        raise BadRequest("Invalid path: Directory traversal detected.")
    return p

def get_dir_safe(config: AppConfig, rel: str) -> Path:
    """
    Get a safe absolute path to a directory within the base directory.
    Raises BadRequest or NotFound if invalid.
    """
    base = config.base_dir.resolve()
    try:
        rel_path = safe_rel_path(rel)
    except BadRequest:
        raise

    full = (base / rel_path).resolve()
    
    # Security check: Ensure path is inside base directory
    if not str(full).startswith(str(base)):
        raise BadRequest("Access denied: Path outside base directory.")
    
    if not full.exists():
        raise NotFound("Directory not found.")
    if not full.is_dir():
        raise BadRequest("Path is not a directory.")
        
    return full

def get_file_safe(config: AppConfig, rel: str) -> Path:
    """
    Get a safe absolute path to a file within the base directory.
    Prevents access to the pending uploads directory.
    """
    base = config.base_dir.resolve()
    try:
        rel_path = safe_rel_path(rel)
    except BadRequest:
        raise

    full = (base / rel_path).resolve()

    # Security check: Ensure path is inside base directory
    if not str(full).startswith(str(base)):
        raise BadRequest("Access denied: Path outside base directory.")

    # Security check: Do not allow access to pending files as regular files
    pending_dir = config.get_pending_dir()
    if str(full).startswith(str(pending_dir)):
        raise NotFound("File not found (pending).")
        
    return full

def get_pending_file_safe(config: AppConfig, rel: str) -> Path:
    """
    Get a safe absolute path to a file within the pending uploads directory.
    """
    base = config.get_pending_dir()
    try:
        rel_path = safe_rel_path(rel)
    except BadRequest:
        raise

    full = (base / rel_path).resolve()
    
    # Security check: Ensure path is inside pending directory
    if not str(full).startswith(str(base)):
        raise BadRequest("Access denied: Path outside pending directory.")
        
    return full

def list_dir(config: AppConfig, current_dir: Path) -> Tuple[List[Dict], List[Dict]]:
    """
    List folders and files in the given directory.
    Returns a tuple of (folders_list, files_list).
    """
    folders = []
    files = []
    base_dir = config.base_dir.resolve()

    try:
        for entry in sorted(current_dir.iterdir(), key=lambda p: p.name.lower()):
            # Skip pending directory
            if entry.is_dir() and entry.name == config.pending_dir_name:
                continue

            try:
                rel = entry.relative_to(base_dir)
                rel_str = str(rel).replace("\\", "/")
            except ValueError:
                continue # Should not happen if logic is correct

            if entry.is_dir():
                try:
                    items = sum(1 for _ in entry.iterdir())
                except PermissionError:
                    items = 0
                folders.append({
                    "name": entry.name,
                    "relpath": rel_str,
                    "items_count": items,
                })
            else:
                stat = entry.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                mimetype, _ = mimetypes.guess_type(str(entry))
                ext = entry.suffix.lower().lstrip(".")
                ftype = detect_type(mimetype or "application/octet-stream")
                
                files.append({
                    "name": entry.name,
                    "relpath": rel_str,
                    "size": size,
                    "size_human": human_size(size),
                    "mimetype": mimetype or "application/octet-stream",
                    "ext": ext,
                    "is_video": ftype == "video",
                    "is_image": ftype == "image",
                    "type": ftype,
                    "mtime": mtime,
                    "mtime_str": mtime_str,
                })
    except PermissionError:
        pass # Handle directory permission errors gracefully

    return folders, files

def filter_sort_files(files: List[Dict], q: str, file_type: str, sort_by: str, order: str) -> List[Dict]:
    """Filter and sort the list of files."""
    if q:
        q_lower = q.lower()
        files = [f for f in files if q_lower in f["name"].lower()]
    
    if file_type != "all":
        files = [f for f in files if f["type"] == file_type]

    reverse = order == "desc"
    if sort_by == "size":
        key = lambda f: f["size"]
    elif sort_by == "mtime":
        key = lambda f: f["mtime"]
    else:
        key = lambda f: f["name"].lower()
    
    files.sort(key=key, reverse=reverse)
    return files

def list_pending_files(config: AppConfig) -> List[Dict]:
    """List all files in the pending uploads directory recursively."""
    pending_dir = config.get_pending_dir()
    files = []
    
    if not pending_dir.exists():
        return []

    for root, _, filenames in os.walk(pending_dir):
        for name in filenames:
            full = Path(root) / name
            try:
                rel = full.relative_to(pending_dir)
                stat = full.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                mimetype, _ = mimetypes.guess_type(str(full))
                ftype = detect_type(mimetype or "application/octet-stream")
                
                files.append({
                    "relpath": str(rel).replace("\\", "/"),
                    "size_human": human_size(size),
                    "mtime": mtime,
                    "mtime_str": mtime_str,
                    "type": ftype,
                })
            except (ValueError, OSError):
                continue
                
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files

def iter_file(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    """Generator to read a file in chunks for streaming."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
