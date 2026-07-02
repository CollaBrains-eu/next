import httpx

from api.config import settings


async def embed_text(text: str) -> list[float]:
    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=60.0) as client:
        response = await client.post(
            "/api/embeddings",
            json={"model": settings.embedding_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]
