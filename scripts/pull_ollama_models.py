from __future__ import annotations

import asyncio
import sys

import httpx


MODELS = [
    "llama3.1:8b",
    "nomic-embed-text",
]


async def main() -> None:
    from src.core.config import get_settings

    settings = get_settings()
    base_url = settings.ollama_base_url

    print(f"🤖 Pulling models from Ollama at {base_url}...")
    print(f"   Models: {', '.join(MODELS)}\n")

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            existing = {m["name"] for m in resp.json().get("models", [])}
            print(f"   Existing models: {existing or 'none'}\n")
        except Exception as exc:
            print(f"❌ Cannot connect to Ollama: {exc}")
            sys.exit(1)

        for model in MODELS:
            if model in existing:
                print(f"  [skip] {model} already pulled")
                continue

            print(f"  [pull] {model} ... ", end="", flush=True)
            try:
                resp = await client.post(
                    f"{base_url}/api/pull",
                    json={"name": model},
                    timeout=600.0,
                )
                if resp.status_code == 200:
                    print("✅")
                else:
                    print(f"⚠️  status={resp.status_code}")
            except Exception as exc:
                print(f"❌ {exc}")

    print("\n✅ Model pull complete!")


if __name__ == "__main__":
    asyncio.run(main())
