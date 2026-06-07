"""Generation pipeline: Directus → RouterAI → Compositor → Directus."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from .compositor import UserData, compose
from .directus_client import DirectusClient
from .routerai_client import enhance_bg_prompt, generate_background, make_client

logger = logging.getLogger(__name__)


async def run_generation(task_id: str, directus: DirectusClient) -> None:
    """
    Full generation pipeline for a single task.

    1. Load task + template from Directus
    2. Download product image
    3. Generate AI background via RouterAI
    4. Compose final image via Pillow
    5. Upload result to Directus, update task status
    """
    t0 = time.perf_counter()

    # 1. Load task
    logger.info("pipeline[%s]: loading task", task_id)
    task = await directus.get_task(task_id)
    template_id = task.get("template")
    input_data = task.get("input_data", {})
    status = task.get("status")

    if status != "pending":
        logger.warning("pipeline[%s]: task status is '%s', skipping", task_id, status)
        return

    # Update status to processing
    await directus.update_task(task_id, {"status": "processing"})

    try:
        # 2. Load template
        logger.info("pipeline[%s]: loading template %s", task_id, template_id)
        template = await directus.get_template(template_id)
        layout = template.get("layout", {})
        style_hints = template.get("style_hints", "")

        # 3. Download product image
        product_file_id = input_data.get("product_image_file_id", "")
        if not product_file_id:
            raise ValueError("product_image_file_id is required in input_data")

        logger.info("pipeline[%s]: downloading product image %s", task_id, product_file_id)
        product_bytes = await directus.download_file(product_file_id)

        # 4. Build user data
        user_data = UserData(
            title=input_data.get("title", ""),
            bullets=input_data.get("bullets", []),
            product_image=product_bytes,
            extra=input_data.get("extra", {}),
        )

        # 5. Generate AI background
        bg_data: bytes | None = None
        bg_type = layout.get("background", {}).get("type", "gradient")

        if bg_type == "ai":
            logger.info("pipeline[%s]: generating AI background", task_id)
            client = make_client()
            bg_prompt = enhance_bg_prompt(
                client,
                product_bytes,
                user_data.title,
                user_data.bullets,
                style_hints=style_hints,
            )
            canvas = layout.get("canvas", {})
            bg_data = generate_background(
                client,
                bg_prompt,
                width=canvas.get("width", 900),
                height=canvas.get("height", 1200),
            )
            # Update enhanced_prompt in task
            await directus.update_task(task_id, {"enhanced_prompt": bg_prompt})

        # 6. Determine output format
        output_format = template.get("output_format", "PNG")

        # 7. Compose
        logger.info("pipeline[%s]: composing image", task_id)
        result_bytes = compose(
            layout=layout,
            user_data=user_data,
            bg_image_data=bg_data,
            output_format=output_format,
        )

        # 8. Upload result
        filename = f"cardgen_{task_id[:8]}.{output_format.lower()}"
        logger.info("pipeline[%s]: uploading result %s (%d bytes)", task_id, filename, len(result_bytes))
        content_type_map = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        file_record = await directus.upload_file(
            result_bytes,
            filename,
            content_type=content_type_map.get(output_format.upper(), "image/png"),
        )
        file_id = file_record.get("id", "")

        # 9. Update task
        await directus.update_task(task_id, {
            "status": "completed",
            "result_image": file_id,
        })

        elapsed = time.perf_counter() - t0
        logger.info("pipeline[%s]: done in %.2fs, result_file=%s", task_id, elapsed, file_id)

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.exception("pipeline[%s]: FAILED in %.2fs: %s", task_id, elapsed, e)
        try:
            await directus.update_task(task_id, {
                "status": "failed",
                "error_message": str(e)[:2000],
            })
        except Exception:
            logger.exception("pipeline[%s]: failed to update error status", task_id)
        raise