import asyncio

import httpx

from api.config import settings


class PaperlessError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.paperless_url,
        auth=(settings.paperless_admin_user, settings.paperless_admin_password),
        timeout=30.0,
    )


async def submit_document(filename: str, content: bytes, mime_type: str) -> str:
    """Upload a file to Paperless for OCR/consumption. Returns the task ID."""
    async with _client() as client:
        response = await client.post(
            "/api/documents/post_document/",
            files={"document": (filename, content, mime_type)},
        )
        response.raise_for_status()
        # Paperless returns the task UUID as a bare JSON string.
        return response.json()


async def wait_for_paperless_id(task_id: str, *, timeout_seconds: float = 120.0, poll_interval: float = 2.0) -> int:
    """Poll Paperless's task status until the submitted document is consumed.

    Returns the resulting Paperless document ID, or raises PaperlessError on
    failure/timeout.
    """
    async with _client() as client:
        elapsed = 0.0
        while elapsed < timeout_seconds:
            response = await client.get("/api/tasks/", params={"task_id": task_id})
            response.raise_for_status()
            tasks = response.json()
            if tasks:
                task = tasks[0]
                status = task.get("status")
                if status == "SUCCESS":
                    document_id = task.get("related_document")
                    if document_id is None:
                        raise PaperlessError(f"task {task_id} succeeded but has no related_document")
                    return int(document_id)
                if status == "FAILURE":
                    raise PaperlessError(f"paperless task {task_id} failed: {task.get('result')}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
    raise PaperlessError(f"timed out waiting for paperless task {task_id}")


async def fetch_document_text(paperless_id: int) -> str:
    async with _client() as client:
        response = await client.get(f"/api/documents/{paperless_id}/")
        response.raise_for_status()
        return response.json().get("content", "")


async def delete_document(paperless_id: int) -> None:
    async with _client() as client:
        response = await client.delete(f"/api/documents/{paperless_id}/")
        if response.status_code not in (204, 404):
            response.raise_for_status()
