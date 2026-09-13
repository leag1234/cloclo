"""Opaque local image references keep binary data out of model history."""

import base64
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import Response
from packages.images import image_info

router = APIRouter()


def directory() -> Path:
    return Path(os.environ.get("ATLAS_IMAGE_DIR", "BRAIN/generated-images"))


def store(url: str) -> str:
    image_info(url)
    root = directory()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = uuid4().hex
    with (root / (key + ".png")).open("xb") as output:
        output.write(base64.b64decode(url.split(",", 1)[1], validate=True))
    return (
        os.environ.get("ATLAS_PUBLIC_URL", "http://localhost:8020").rstrip("/")
        + "/images/"
        + key
    )


@router.get("/images/{key}")
def generated_image(key: str) -> Response:
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        return Response(status_code=404)
    path = directory() / (key + ".png")
    if path.is_symlink():
        return Response(status_code=404)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Response(status_code=404)
    return Response(
        raw,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=86400",
        },
    )
