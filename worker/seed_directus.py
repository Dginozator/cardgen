"""Seed Directus schema: create collections (templates, generation_tasks) and seed MVP templates.

Usage:
  python -m worker.seed_directus

Requires env vars: DIRECTUS_URL, DIRECTUS_TOKEN (admin token).
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import httpx

BASE_URL = os.environ.get("DIRECTUS_URL", "http://localhost:8055").rstrip("/")
TOKEN = os.environ.get("DIRECTUS_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ── Layout definitions ──────────────────────────────────────────────

MAIN_SLIDE_3_4 = {
    "canvas": {"width": 900, "height": 1200},
    "background": {
        "type": "ai",
        "style": "gradient",
    },
    "zones": [
        {
            "type": "product_image",
            "x": 50, "y": 50, "w": 800, "h": 1100,
            "fit": "contain",
            "padding": 40,
        },
    ],
}

INFOGRAPHIC_3_4 = {
    "canvas": {"width": 900, "height": 1200},
    "background": {
        "type": "gradient",
        "colors": ["#0f0c29", "#302b63", "#24243e"],
    },
    "zones": [
        {
            "type": "product_image",
            "x": 100, "y": 50, "w": 700, "h": 600,
            "fit": "contain",
            "padding": 30,
        },
        {
            "type": "text",
            "x": 50, "y": 680, "w": 800, "h": 120,
            "field": "title",
            "font_size": 44,
            "font_weight": "bold",
            "color": "#FFFFFF",
            "align": "center",
            "vertical_align": "middle",
        },
        {
            "type": "bullets",
            "x": 80, "y": 830, "w": 740, "h": 330,
            "field": "bullets",
            "font_size": 30,
            "color": "#E0E0E0",
            "bullet_char": "✓",
            "line_spacing": 16,
            "icon_color": "#4FC3F7",
        },
    ],
}

INFOGRAPHIC_1_1 = {
    "canvas": {"width": 900, "height": 900},
    "background": {
        "type": "gradient",
        "colors": ["#1a1a2e", "#16213e", "#0f3460"],
    },
    "zones": [
        {
            "type": "product_image",
            "x": 100, "y": 50, "w": 700, "h": 450,
            "fit": "contain",
            "padding": 20,
        },
        {
            "type": "text",
            "x": 50, "y": 520, "w": 800, "h": 100,
            "field": "title",
            "font_size": 38,
            "font_weight": "bold",
            "color": "#FFFFFF",
            "align": "center",
            "vertical_align": "middle",
        },
        {
            "type": "bullets",
            "x": 80, "y": 640, "w": 740, "h": 230,
            "field": "bullets",
            "font_size": 26,
            "color": "#E0E0E0",
            "bullet_char": "✓",
            "line_spacing": 12,
            "icon_color": "#4FC3F7",
        },
    ],
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


def create_collection(name: str, fields: list[dict], *, icon: str = "box") -> None:
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
            "sort_field": "sort",
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
            "field": "category",
            "type": "string",
            "meta": {"interface": "input", "options": {"placeholder": "electronics"}},
            "schema": {"is_nullable": True},
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
            "field": "layout",
            "type": "json",
            "meta": {"interface": "input-code", "options": {"language": "json"}},
            "schema": {"is_nullable": False},
        },
        {
            "field": "preview",
            "type": "uuid",
            "meta": {"interface": "file-image", "special": ["file"]},
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
            "type": "uuid",
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
    ], icon="assignment")


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
        # Skip admin role (it already has full access)
        if role.get("admin_access") or role_name.lower() == "administrator":
            continue

        print(f"  Setting permissions for role '{role_name}' ({role_id})...")

        # Templates: read
        existing = api("GET", f"/permissions?filter[role][_eq]={role_id}&filter[collection][_eq]=templates&filter[action][_eq]=read")
        if not existing:
            api("POST", "/permissions", json_data={
                "role": role_id,
                "collection": "templates",
                "action": "read",
                "permissions": {},
                "fields": ["*"],
            })
            print(f"    ✓ Added templates:read for {role_name}")
        else:
            print(f"    templates:read already exists for {role_name}")

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
            else:
                print(f"    generation_tasks:{action} already exists for {role_name}")

    # Also grant public/system access to directus_files for image uploads
    # (users need to upload files via Directus)
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


# ── Seed templates ───────────────────────────────────────────────────

SEED_TEMPLATES = [
    {
        "name": "Главный слайд 3:4",
        "slug": "ozon-main-3x4",
        "category": "general",
        "width": 900,
        "height": 1200,
        "layout": MAIN_SLIDE_3_4,
        "is_active": True,
        "sort": 1,
        "output_format": "PNG",
        "style_hints": "чистый фон, без текста, товар по центру, минимализм",
    },
    {
        "name": "Инфографика 3:4",
        "slug": "ozon-infographic-3x4",
        "category": "general",
        "width": 900,
        "height": 1200,
        "layout": INFOGRAPHIC_3_4,
        "is_active": True,
        "sort": 2,
        "output_format": "PNG",
        "style_hints": "тёмный градиент, белый текст, голубые акценты, товар сверху",
    },
    {
        "name": "Инфографика 1:1",
        "slug": "ozon-infographic-1x1",
        "category": "general",
        "width": 900,
        "height": 900,
        "layout": INFOGRAPHIC_1_1,
        "is_active": True,
        "sort": 3,
        "output_format": "PNG",
        "style_hints": "тёмный градиент, компактная раскладка, белый текст",
    },
]


def seed_templates() -> None:
    existing = api("GET", "/items/templates", params={"limit": -1})
    existing_slugs = {t.get("slug") for t in (existing or [])}

    for tmpl in SEED_TEMPLATES:
        if tmpl["slug"] in existing_slugs:
            print(f"  Template '{tmpl['slug']}' already exists, skipping.")
            continue
        print(f"  Creating template '{tmpl['slug']}'...")
        payload = {**tmpl, "layout": json.dumps(tmpl["layout"])}
        api("POST", "/items/templates", json_data=payload)
        print(f"  ✓ Template '{tmpl['slug']}' created.")


# ── Main ─────────────────────────────────────────────────────────────

def auto_seed() -> None:
    """Auto-seed on worker startup: create collections, set permissions, seed templates."""
    if not TOKEN:
        print("  [seed] No DIRECTUS_TOKEN, skipping auto-seed.")
        return
    try:
        print("[seed] Checking Directus schema...")
        create_templates_collection()
        create_tasks_collection()
        set_permissions()
        seed_templates()
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
    set_permissions()
    seed_templates()
    print("Done!")


if __name__ == "__main__":
    main()