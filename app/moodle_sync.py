from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx


MOODLE_BASE_URL = os.getenv("MOODLE_BASE_URL", "").rstrip("/")
MOODLE_TOKEN = os.getenv("MOODLE_TOKEN", "")
MOODLE_MODULE_MAP_JSON = os.getenv("MOODLE_MODULE_MAP_JSON", "{}")

DATA_MODULES_DIR = Path("data") / "modules"


def sanitize_module_key(module_key: str | None) -> str | None:
    if not module_key:
        return None
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", module_key.strip()).strip("-")
    return safe.lower() or None


def load_module_map() -> dict[str, Any]:
    try:
        data = json.loads(MOODLE_MODULE_MAP_JSON or "{}")
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}


def resolve_course_id(module_key: str | None) -> int | None:
    module_key = sanitize_module_key(module_key)
    if not module_key:
        return None

    if module_key.isdigit():
        return int(module_key)

    module_map = load_module_map()
    value = module_map.get(module_key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def has_moodle_access() -> bool:
    return bool(MOODLE_BASE_URL and MOODLE_TOKEN)


def _strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", "", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _module_text(section_name: str, mod: dict[str, Any]) -> str:
    parts = []
    name = mod.get("name")
    modname = mod.get("modname")
    if section_name:
        parts.append(f"Section: {section_name}")
    if name:
        parts.append(f"Item: {name}")
    if modname:
        parts.append(f"Type: {modname}")

    summary = mod.get("description") or mod.get("summary") or ""
    summary_text = _strip_html(summary)
    if summary_text:
        parts.append(summary_text)

    contents = mod.get("contents") or []
    for content in contents:
        filename = content.get("filename")
        fileurl = content.get("fileurl")
        if filename and fileurl:
            parts.append(f"File: {filename} ({fileurl})")

    return "\n".join(parts).strip()


def _course_content_to_markdown(course: dict[str, Any]) -> str:
    lines = []
    lines.append(f"Title: {course.get('fullname') or course.get('shortname') or 'Moodle course'}")
    lines.append(f"URL: {MOODLE_BASE_URL}")
    lines.append("Category: moodle-module")
    lines.append("")

    for section in course.get("sections", []):
        section_name = section.get("name") or section.get("section") or ""
        section_summary = _strip_html(section.get("summary") or "")
        if section_name:
            lines.append(f"## {section_name}")
        elif section_summary:
            lines.append(f"## {section_summary[:80]}")

        for mod in section.get("modules", []):
            text = _module_text(section_name or section_summary, mod)
            if text:
                lines.append(text)
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def sync_module_from_moodle(module_key: str | None) -> bool:
    module_key = sanitize_module_key(module_key)
    course_id = resolve_course_id(module_key)
    if not module_key or course_id is None or not has_moodle_access():
        return False

    url = f"{MOODLE_BASE_URL}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": course_id,
    }

    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and payload.get("exception"):
        raise RuntimeError(payload.get("message") or "Moodle sync failed")

    course = {
        "fullname": f"Course {course_id}",
        "shortname": module_key,
        "sections": payload if isinstance(payload, list) else [],
    }

    module_dir = DATA_MODULES_DIR / module_key
    module_dir.mkdir(parents=True, exist_ok=True)
    output_path = module_dir / "moodle-course.md"
    output_path.write_text(_course_content_to_markdown(course), encoding="utf-8")
    return True
