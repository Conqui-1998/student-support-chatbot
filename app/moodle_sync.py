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
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "")

DATA_MODULES_DIR = Path("data") / "modules"
MODULE_ACCESS_FILE = Path("data") / "module_access.json"
LAST_SYNC_STATE: dict[str, Any] = {}


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


def has_ingest_access() -> bool:
    return bool(INGEST_TOKEN)


def ingest_token_matches(token: str | None) -> bool:
    if not INGEST_TOKEN or not token:
        return False
    return secrets_compare(INGEST_TOKEN, token)


def secrets_compare(expected: str, provided: str) -> bool:
    try:
        import hmac

        return hmac.compare_digest(expected, provided)
    except Exception:
        return expected == provided


def list_available_modules() -> list[str]:
    if not DATA_MODULES_DIR.exists():
        return []
    modules = []
    for path in sorted(DATA_MODULES_DIR.iterdir()):
        if path.is_dir():
            key = sanitize_module_key(path.name)
            if key:
                modules.append(key)
    return sorted(set(modules))


def load_module_access() -> dict[str, Any]:
    if not MODULE_ACCESS_FILE.exists():
        return {"enabled": []}
    try:
        data = json.loads(MODULE_ACCESS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            enabled = data.get("enabled", [])
            if isinstance(enabled, list):
                return {"enabled": [sanitize_module_key(x) for x in enabled if sanitize_module_key(x)]}
    except Exception:
        pass
    return {"enabled": []}


def save_module_access(enabled_modules: list[str]) -> dict[str, Any]:
    MODULE_ACCESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    enabled = sorted({sanitize_module_key(x) for x in enabled_modules if sanitize_module_key(x)})
    payload = {"enabled": enabled}
    MODULE_ACCESS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def is_module_enabled(module_key: str | None) -> bool:
    safe_key = sanitize_module_key(module_key)
    if not safe_key:
        return False
    access = load_module_access()
    enabled = access.get("enabled", [])
    if not enabled:
        return True
    return safe_key in enabled


def set_module_enabled(module_key: str | None, enabled: bool) -> dict[str, Any]:
    safe_key = sanitize_module_key(module_key)
    access = load_module_access()
    current = set(access.get("enabled", []))
    if not safe_key:
        return access
    if enabled:
        current.add(safe_key)
    else:
        current.discard(safe_key)
    return save_module_access(list(current))


def get_module_access_rows(module_key: str | None = None) -> list[dict[str, Any]]:
    access = load_module_access()
    enabled = set(access.get("enabled", []))
    rows = []
    module_keys = list_available_modules()
    if module_key:
        safe_key = sanitize_module_key(module_key)
        module_keys = [safe_key] if safe_key in module_keys else [safe_key]
    for key in module_keys:
        if not key:
            continue
        module_dir = DATA_MODULES_DIR / key
        files = [path for path in module_dir.glob("*") if path.is_file() and path.suffix.lower() in {".md", ".pdf", ".docx", ".pptx"}]
        rows.append({
            "module_key": key,
            "enabled": key in enabled if enabled else True,
            "file_count": len(files),
            "module_dir": str(module_dir),
        })
    return rows


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


def write_module_markdown(
    module_key: str | None,
    markdown: str,
    *,
    source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global LAST_SYNC_STATE
    module_key = sanitize_module_key(module_key)
    if not module_key:
        LAST_SYNC_STATE = {
            "module_key": module_key,
            "ok": False,
            "message": "Invalid module key.",
            "source": source,
        }
        return LAST_SYNC_STATE

    cleaned_markdown = (markdown or "").strip()
    if not cleaned_markdown:
        LAST_SYNC_STATE = {
            "module_key": module_key,
            "ok": False,
            "message": "No markdown content provided.",
            "source": source,
        }
        return LAST_SYNC_STATE

    module_dir = DATA_MODULES_DIR / module_key
    module_dir.mkdir(parents=True, exist_ok=True)
    output_path = module_dir / "moodle-course.md"

    header_lines = [
        f"Title: {metadata.get('title', f'Moodle module {module_key}') if metadata else f'Moodle module {module_key}'}",
        f"URL: {metadata.get('url', MOODLE_BASE_URL) if metadata else MOODLE_BASE_URL}",
        "Category: moodle-module",
        f"Source: {source}",
    ]
    if metadata:
        for key in ("course_id", "section_count", "content_count", "version", "updated_at"):
            if metadata.get(key) is not None:
                header_lines.append(f"{key.replace('_', ' ').title()}: {metadata.get(key)}")
    header_lines.append("")
    header_lines.append(cleaned_markdown)

    final_markdown = "\n".join(header_lines).strip() + "\n"
    output_path.write_text(final_markdown, encoding="utf-8")

    LAST_SYNC_STATE = {
        "module_key": module_key,
        "ok": True,
        "source": source,
        "message": f"Wrote {output_path.name}",
        "path": str(output_path),
        "size": len(final_markdown.encode("utf-8")),
        "metadata": metadata or {},
    }
    return LAST_SYNC_STATE


def sync_module_from_moodle(module_key: str | None) -> bool:
    global LAST_SYNC_STATE
    module_key = sanitize_module_key(module_key)
    course_id = resolve_course_id(module_key)
    if not module_key or course_id is None or not has_moodle_access():
        LAST_SYNC_STATE = {
            "module_key": module_key,
            "course_id": course_id,
            "ok": False,
            "message": "Missing Moodle configuration or course mapping.",
        }
        return False

    url = f"{MOODLE_BASE_URL}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": course_id,
    }

    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        LAST_SYNC_STATE = {
            "module_key": module_key,
            "course_id": course_id,
            "ok": False,
            "message": f"Request failed: {exc}",
        }
        raise

    if isinstance(payload, dict) and payload.get("exception"):
        message = payload.get("message") or "Moodle sync failed"
        LAST_SYNC_STATE = {
            "module_key": module_key,
            "course_id": course_id,
            "ok": False,
            "message": message,
        }
        raise RuntimeError(message)

    course = {
        "fullname": f"Course {course_id}",
        "shortname": module_key,
        "sections": payload if isinstance(payload, list) else [],
    }

    module_dir = DATA_MODULES_DIR / module_key
    module_dir.mkdir(parents=True, exist_ok=True)
    output_path = module_dir / "moodle-course.md"
    markdown = _course_content_to_markdown(course)
    output_path.write_text(markdown, encoding="utf-8")
    LAST_SYNC_STATE = {
        "module_key": module_key,
        "course_id": course_id,
        "ok": True,
        "message": f"Wrote {output_path.name}",
        "path": str(output_path),
        "size": len(markdown.encode("utf-8")),
        "section_count": len(course.get("sections", [])),
        "source_count": sum(len((section.get("modules") or [])) for section in course.get("sections", [])),
    }
    return True


def debug_sync_module_from_moodle(module_key: str | None) -> dict[str, Any]:
    global LAST_SYNC_STATE
    module_key = sanitize_module_key(module_key)
    course_id = resolve_course_id(module_key)

    result: dict[str, Any] = {
        "module_key": module_key,
        "course_id": course_id,
        "moodle_access": has_moodle_access(),
        "ok": False,
    }

    if not module_key or course_id is None or not has_moodle_access():
        message = "Missing Moodle configuration or course mapping."
        LAST_SYNC_STATE = {
            **result,
            "message": message,
        }
        result["message"] = message
        return result

    url = f"{MOODLE_BASE_URL}/webservice/rest/server.php"
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": course_id,
    }

    try:
        response = httpx.get(url, params=params, timeout=30)
        result["http_status"] = response.status_code
        response.raise_for_status()
        payload = response.json()
        result["payload_type"] = type(payload).__name__
        if isinstance(payload, list):
            result["section_count"] = len(payload)
            result["module_count"] = sum(len((section.get("modules") or [])) for section in payload if isinstance(section, dict))
            result["sample_keys"] = list(payload[0].keys())[:10] if payload and isinstance(payload[0], dict) else []
        elif isinstance(payload, dict):
            result["payload_keys"] = list(payload.keys())[:20]
            if payload.get("exception"):
                message = payload.get("message") or "Moodle sync failed"
                result["message"] = message
                LAST_SYNC_STATE = {**result, "ok": False}
                return LAST_SYNC_STATE

        course = {
            "fullname": f"Course {course_id}",
            "shortname": module_key,
            "sections": payload if isinstance(payload, list) else [],
        }
        module_dir = DATA_MODULES_DIR / module_key
        module_dir.mkdir(parents=True, exist_ok=True)
        output_path = module_dir / "moodle-course.md"
        markdown = _course_content_to_markdown(course)
        output_path.write_text(markdown, encoding="utf-8")
        result.update({
            "ok": True,
            "message": f"Wrote {output_path.name}",
            "path": str(output_path),
            "size": len(markdown.encode("utf-8")),
        })
        LAST_SYNC_STATE = dict(result)
        return result
    except Exception as exc:
        result["message"] = f"Request failed: {exc}"
        LAST_SYNC_STATE = dict(result)
        return result
