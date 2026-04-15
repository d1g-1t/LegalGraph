from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4


SAMPLE_DOCS_DIR = Path(__file__).parent.parent / "data" / "sample_docs"


async def main() -> None:
    from src.infrastructure.database import build_session_factory
    from src.infrastructure.database.models import KnowledgeDocumentModel
    from src.infrastructure.queue.tasks import ingest_knowledge_document_task

    session_factory = build_session_factory()

    if not SAMPLE_DOCS_DIR.exists():
        print(f"⚠️  Directory {SAMPLE_DOCS_DIR} not found. Creating...")
        SAMPLE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(SAMPLE_DOCS_DIR.glob("*.txt"))
    if not files:
        print("  No .txt files found in data/sample_docs/")
        print("  Place .txt/.pdf/.docx files and re-run.")
        return

    async with session_factory() as session:
        for fpath in files:
            content = fpath.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()

            doc = KnowledgeDocumentModel(
                id=uuid4(),
                document_name=fpath.name,
                document_type="TXT",
                source_path=str(fpath),
                checksum=checksum,
                is_global=True,
                metadata_={"source": "seed_script"},
            )
            session.add(doc)
            await session.flush()

            ingest_knowledge_document_task.apply_async(
                args=[str(doc.id), str(fpath)],
                queue="legalops.ingest",
            )
            print(f"  [+] {fpath.name} ({len(content)} bytes) → queued")

        await session.commit()

    print(f"\n✅ {len(files)} documents queued for ingestion!")


if __name__ == "__main__":
    asyncio.run(main())
