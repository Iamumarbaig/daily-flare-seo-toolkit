from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}


def filename_from_url(url: str) -> str:
    return PurePosixPath(unquote(urlparse(url).path)).name


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", text)


def suggested_filename(page_title: str, image_alt: str | None, image_url: str) -> str:
    base = slugify(image_alt or page_title or "daily-flare-image")
    ext = PurePosixPath(filename_from_url(image_url)).suffix.lower() or ".jpg"
    if ext not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"{base[:90].rstrip('-')}{ext}"


def suggest_alt(page_title: str, existing_alt: str | None, image_url: str) -> str:
    if existing_alt and existing_alt.strip():
        return existing_alt.strip()
    name = PurePosixPath(filename_from_url(image_url)).stem
    name = re.sub(r"[-_]+", " ", name)
    name = re.sub(r"\b(file|image|img|photo|picture|wp|dsc|pxl)\b", " ", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()
    return name or page_title.strip()


def media_recommendation(page_title: str, image: dict) -> dict:
    src = image.get("src") or ""
    current_alt = image.get("alt")
    current_name = filename_from_url(src)
    recommended_alt = suggest_alt(page_title, current_alt, src)
    recommended_filename = suggested_filename(page_title, recommended_alt, src)
    return {
        "current_filename": current_name,
        "current_alt": current_alt,
        "recommended_filename": recommended_filename,
        "recommended_alt": recommended_alt,
        "needs_alt": not bool(current_alt and current_alt.strip()),
        "needs_filename": bool(image.get("filename_issue")),
        "write_allowed": False,
    }
