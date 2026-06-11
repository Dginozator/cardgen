"""Seed Directus schema: create collections (templates, generation_tasks) and seed SVG templates.

Usage:
  python -m worker.seed_directus

Requires env vars: DIRECTUS_URL, DIRECTUS_TOKEN (admin token).
"""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE_URL = os.environ.get("DIRECTUS_URL", "http://localhost:8055").rstrip("/")
TOKEN = os.environ.get("DIRECTUS_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ── API helpers ──────────────────────────────────────────────────────

def api(method: str, path: str, *, json_data: dict | None = None, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    resp = httpx.request(method, url, headers=HEADERS, json=json_data, params=params, timeout=30)
    if resp.status_code >= 400:
        print(f"  API {method} {path} → {resp.status_code}: {resp.text[:500]}")
        return {}
    data = resp.json()
    return data.get("data", data)


def collection_exists(name: str) -> bool:
    resp = api("GET", f"/collections/{name}")
    return bool(resp)


def field_exists(collection: str, field_name: str) -> bool:
    resp = api("GET", f"/fields/{collection}/{field_name}")
    return bool(resp)


def create_collection(name: str, fields: list[dict], *, icon: str = "box", sort_field: str | None = "sort") -> None:
    if collection_exists(name):
        print(f"  Collection '{name}' already exists, skipping.")
        return
    print(f"  Creating collection '{name}'...")
    api("POST", "/collections", json_data={
        "collection": name,
        "meta": {
            "icon": icon,
            "display_template": None,
            "hidden": False,
            "singleton": False,
            "sort_field": sort_field,
        },
        "schema": {},
    })
    for field in fields:
        api("POST", f"/fields/{name}", json_data=field)
    print(f"  ✓ Collection '{name}' created with {len(fields)} fields.")


# ── Schema ───────────────────────────────────────────────────────────

def create_templates_collection() -> None:
    create_collection("templates", [
        {
            "field": "id",
            "type": "uuid",
            "meta": {"interface": "input", "special": ["uuid"], "readonly": True, "hidden": True},
            "schema": {"is_primary_key": True, "has_auto_increment": False},
        },
        {
            "field": "name",
            "type": "string",
            "meta": {"interface": "input", "options": {"placeholder": "Название шаблона"}},
            "schema": {"is_nullable": False},
        },
        {
            "field": "slug",
            "type": "string",
            "meta": {"interface": "input", "options": {"placeholder": "ozon-main-3x4"}},
            "schema": {"is_nullable": False},
        },
        {
            "field": "svg_file",
            "type": "uuid",
            "meta": {
                "interface": "file-image",
                "special": ["file"],
                "options": {"accept": "image/svg+xml"},
            },
            "schema": {
                "is_nullable": True,
                "foreign_key_table": "directus_files",
                "foreign_key_column": "id",
            },
        },
        {
            "field": "preview_image",
            "type": "uuid",
            "meta": {
                "interface": "file-image",
                "special": ["file"],
            },
            "schema": {
                "is_nullable": True,
                "foreign_key_table": "directus_files",
                "foreign_key_column": "id",
            },
        },
        {
            "field": "width",
            "type": "integer",
            "meta": {"interface": "input", "special": ["cast-integer"]},
            "schema": {"default_value": 900, "is_nullable": False},
        },
        {
            "field": "height",
            "type": "integer",
            "meta": {"interface": "input", "special": ["cast-integer"]},
            "schema": {"default_value": 1200, "is_nullable": False},
        },
        {
            "field": "output_format",
            "type": "string",
            "meta": {"interface": "select-dropdown", "options": {"choices": [
                {"text": "PNG", "value": "PNG"},
                {"text": "JPEG", "value": "JPEG"},
                {"text": "WEBP", "value": "WEBP"},
            ]}},
            "schema": {"default_value": "PNG", "is_nullable": True},
        },
        {
            "field": "style_hints",
            "type": "text",
            "meta": {"interface": "input-textarea"},
            "schema": {"is_nullable": True},
        },
        {
            "field": "is_active",
            "type": "boolean",
            "meta": {"interface": "boolean", "special": ["cast-boolean"]},
            "schema": {"default_value": True, "is_nullable": False},
        },
        {
            "field": "sort",
            "type": "integer",
            "meta": {"interface": "input", "special": ["cast-integer"]},
            "schema": {"default_value": 0, "is_nullable": True},
        },
    ], icon="art_track")


def create_tasks_collection() -> None:
    create_collection("generation_tasks", [
        {
            "field": "id",
            "type": "uuid",
            "meta": {"interface": "input", "special": ["uuid"], "readonly": True},
            "schema": {"is_primary_key": True},
        },
        {
            "field": "user_id",
            "type": "uuid",
            "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"], "options": {"template": "{{id}}"}},
            "schema": {"is_nullable": True, "foreign_key_table": "directus_users", "foreign_key_column": "id"},
        },
        {
            "field": "status",
            "type": "string",
            "meta": {"interface": "select-dropdown", "options": {"choices": [
                {"text": "Pending", "value": "pending"},
                {"text": "Processing", "value": "processing"},
                {"text": "Completed", "value": "completed"},
                {"text": "Failed", "value": "failed"},
            ]}},
            "schema": {"default_value": "pending", "is_nullable": False},
        },
        {
            "field": "template",
            "type": "integer",
            "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"], "options": {"template": "{{name}}"}},
            "schema": {"is_nullable": False, "foreign_key_table": "templates", "foreign_key_column": "id"},
        },
        {
            "field": "input_data",
            "type": "json",
            "meta": {"interface": "input-code", "options": {"language": "json"}},
            "schema": {"is_nullable": True},
        },
        {
            "field": "result_image",
            "type": "uuid",
            "meta": {"interface": "file-image", "special": ["file"]},
            "schema": {"is_nullable": True},
        },
        {
            "field": "enhanced_prompt",
            "type": "text",
            "meta": {"interface": "input-textarea"},
            "schema": {"is_nullable": True},
        },
        {
            "field": "error_message",
            "type": "text",
            "meta": {"interface": "input-textarea"},
            "schema": {"is_nullable": True},
        },
        {
            "field": "date_created",
            "type": "timestamp",
            "meta": {"interface": "datetime", "special": ["date-created"], "readonly": True},
            "schema": {"is_nullable": True},
        },
        {
            "field": "date_updated",
            "type": "timestamp",
            "meta": {"interface": "datetime", "special": ["date-updated"], "readonly": True},
            "schema": {"is_nullable": True},
        },
    ], icon="assignment", sort_field=None)


# ── Schema migrations for existing collections ──────────────────────

def migrate_templates_collection() -> None:
    """Add svg_file and preview_image fields to existing templates collection."""
    if not collection_exists("templates"):
        return

    # Add svg_file if missing
    if not field_exists("templates", "svg_file"):
        print("  Adding svg_file field to templates...")
        api("POST", "/fields/templates", json_data={
            "field": "svg_file",
            "type": "uuid",
            "meta": {
                "interface": "file-image",
                "special": ["file"],
                "options": {"accept": "image/svg+xml"},
            },
            "schema": {
                "is_nullable": True,
                "foreign_key_table": "directus_files",
                "foreign_key_column": "id",
            },
        })
        print("  ✓ Added svg_file.")

    # Add preview_image if missing
    if not field_exists("templates", "preview_image"):
        print("  Adding preview_image field to templates...")
        api("POST", "/fields/templates", json_data={
            "field": "preview_image",
            "type": "uuid",
            "meta": {
                "interface": "file-image",
                "special": ["file"],
            },
            "schema": {
                "is_nullable": True,
                "foreign_key_table": "directus_files",
                "foreign_key_column": "id",
            },
        })
        print("  ✓ Added preview_image.")

    # Remove old layout field if it exists
    if field_exists("templates", "layout"):
        print("  Removing old layout field from templates...")
        api("DELETE", "/fields/templates/layout")
        print("  ✓ Removed layout.")

    # Remove old category field if it exists
    if field_exists("templates", "category"):
        print("  Removing old category field from templates...")
        api("DELETE", "/fields/templates/category")
        print("  ✓ Removed category.")


def fix_tasks_sort_field() -> None:
    """Fix generation_tasks collection: remove sort_field if collection already exists."""
    if not collection_exists("generation_tasks"):
        return
    coll = api("GET", "/collections/generation_tasks")
    if coll and coll.get("meta", {}).get("sort_field") == "sort":
        print("  Fixing generation_tasks sort_field → null...")
        api("PATCH", "/collections/generation_tasks", json_data={
            "meta": {**coll.get("meta", {}), "sort_field": None},
        })
        print("  ✓ Fixed.")


def fix_tasks_template_type() -> None:
    """Fix generation_tasks.template field: change from uuid to integer to match templates PK."""
    if not collection_exists("generation_tasks"):
        return
    field = api("GET", "/fields/generation_tasks/template")
    if field and field.get("type") == "uuid":
        print("  Fixing generation_tasks.template type: uuid → integer...")
        api("PATCH", "/fields/generation_tasks/template", json_data={
            "type": "integer",
            "schema": {
                "is_nullable": False,
                "foreign_key_table": "templates",
                "foreign_key_column": "id",
            },
        })
        print("  ✓ Fixed template field type.")


# ── Permissions ──────────────────────────────────────────────────────

def set_permissions() -> None:
    """Grant read/write permissions for templates and generation_tasks to non-admin roles."""
    roles = api("GET", "/roles")
    if not roles:
        print("  No roles found, skipping permissions.")
        return

    for role in roles:
        role_id = role.get("id", "")
        role_name = role.get("name", "")
        if role.get("admin_access") or role_name.lower() == "administrator":
            continue

        print(f"  Setting permissions for role '{role_name}' ({role_id})...")

        # Templates: read
        for action in ["read"]:
            existing = api("GET", f"/permissions?filter[role][_eq]={role_id}&filter[collection][_eq]=templates&filter[action][_eq]={action}")
            if not existing:
                api("POST", "/permissions", json_data={
                    "role": role_id,
                    "collection": "templates",
                    "action": action,
                    "permissions": {},
                    "fields": ["*"],
                })
                print(f"    ✓ Added templates:{action} for {role_name}")

        # Generation tasks: read, create, update
        for action in ["read", "create", "update"]:
            existing = api("GET", f"/permissions?filter[role][_eq]={role_id}&filter[collection][_eq]=generation_tasks&filter[action][_eq]={action}")
            if not existing:
                api("POST", "/permissions", json_data={
                    "role": role_id,
                    "collection": "generation_tasks",
                    "action": action,
                    "permissions": {},
                    "fields": ["*"],
                })
                print(f"    ✓ Added generation_tasks:{action} for {role_name}")

    # Also grant access to directus_files for image uploads
    for role in roles:
        role_id = role.get("id", "")
        role_name = role.get("name", "")
        if role.get("admin_access") or role_name.lower() == "administrator":
            continue

        for action in ["read", "create"]:
            existing = api("GET", f"/permissions?filter[role][_eq]={role_id}&filter[collection][_eq]=directus_files&filter[action][_eq]={action}")
            if not existing:
                api("POST", "/permissions", json_data={
                    "role": role_id,
                    "collection": "directus_files",
                    "action": action,
                    "permissions": {},
                    "fields": ["*"],
                })
                print(f"    ✓ Added directus_files:{action} for {role_name}")


# ── Main ─────────────────────────────────────────────────────────────

def auto_seed() -> None:
    """Auto-seed on worker startup: create/migrate collections, set permissions."""
    if not TOKEN:
        print("  [seed] No DIRECTUS_TOKEN, skipping auto-seed.")
        return
    try:
        print("[seed] Checking Directus schema...")
        create_templates_collection()
        create_tasks_collection()
        migrate_templates_collection()
        fix_tasks_sort_field()
        fix_tasks_template_type()
        set_permissions()
        print("[seed] Done.")
    except Exception as e:
        print(f"[seed] Error: {e}")


def main() -> None:
    if not TOKEN:
        print("Error: DIRECTUS_TOKEN env var is required.")
        sys.exit(1)

    print("Seeding Directus schema...")
    create_templates_collection()
    create_tasks_collection()
    migrate_templates_collection()
    set_permissions()
    print("Done!")


if __name__ == "__main__":
    main()