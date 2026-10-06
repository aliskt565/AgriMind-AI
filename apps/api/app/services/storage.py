"""
Object storage abstraction. `STORAGE_BACKEND=local` writes to a local
directory outside the web root; `STORAGE_BACKEND=s3` is the future real
implementation. Application code depends only on `save_upload`, never on
disk paths or S3 SDK calls directly, so the storage backend can change
without touching endpoints.
"""
import os
import uuid

from app.core.config import get_settings


def save_upload(content: bytes, content_type: str, subfolder: str = "plant-vision") -> str:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "local":
        raise NotImplementedError("Only the local storage backend is implemented in this phase.")

    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(content_type, "bin")
    directory = os.path.join(settings.STORAGE_LOCAL_DIR, subfolder)
    os.makedirs(directory, exist_ok=True)

    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(directory, filename)
    with open(path, "wb") as f:
        f.write(content)

    return path
