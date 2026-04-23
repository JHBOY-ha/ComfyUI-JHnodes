import hashlib
import os

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".webm", ".avi", ".gif", ".m4v")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")
ALL_EXTENSIONS = VIDEO_EXTENSIONS + IMAGE_EXTENSIONS


def normalize_folder(folder: str) -> str:
    return folder.strip().strip('"').strip("'")


def list_folder_entries(folder: str) -> list:
    folder = normalize_folder(folder)
    if not os.path.isdir(folder):
        return []
    names = sorted(os.listdir(folder))
    paths = [os.path.join(folder, n) for n in names]
    paths = [p for p in paths if os.path.isfile(p)]
    return [p for p in paths if os.path.splitext(p)[1].lower() in ALL_EXTENSIONS]


def file_change_hash(path: str) -> str:
    h = hashlib.sha256()
    h.update(path.encode())
    try:
        h.update(str(os.path.getmtime(path)).encode())
    except OSError:
        h.update(b"missing")
    return h.hexdigest()
