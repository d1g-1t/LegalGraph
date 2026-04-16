"""RAG service — document ingestion, chunking, embedding, and search.

Supports PDF, DOCX, TXT, MD with legal-domain–aware chunking strategies.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

import structlog

from src.core.config import get_settings
from src.domain.entities import KnowledgeChunk, KnowledgeDocument, RetrievedChunk
from src.domain.repositories import IKnowledgeChunkRepository, IKnowledgeDocumentRepository
from src.infrastructure.llm import OllamaLLMService

logger = structlog.get_logger(__name__)


# ── Text extractors ─────────────────────────────────────


def extract_text_pdf(path: str) -> str:
    """Extract text from PDF using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text_docx(path: str) -> str:
    """Extract text from DOCX."""
    import docx
    doc = docx.Document(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_plain(path: str) -> str:
    """Extract text from TXT/MD."""
    return Path(path).read_text(encoding="utf-8")


EXTRACTORS = {
    "pdf": extract_text_pdf,
    "docx": extract_text_docx,
    "txt": extract_text_plain,
    "md": extract_text_plain,
}


# ── Chunking strategies ────────────────────────────────


def chunk_by_articles(text: str, max_size: int = 1000) -> list[dict]:
    """Split legal text by article / clause pattern (Статья N)."""
    pattern = r"(Статья\s+\d+[^.]*\.)"
    parts = re.split(pattern, text)
    chunks = []
    current = ""
    header = None
    for part in parts:
        if re.match(pattern, part.strip()):
            if current.strip():
                chunks.append({"content": current.strip(), "header": header})
            header = part.strip()
            current = part
        else:
            current += part
            if len(current) >= max_size:
                chunks.append({"content": current.strip(), "header": header})
                current = ""
                header = None
    if current.strip():
        chunks.append({"content": current.strip(), "header": header})
    return chunks


def chunk_by_sections(text: str, max_size: int = 1000) -> list[dict]:
    """Split by numbered section headings (contracts)."""
    pattern = r"(\d+(?:\.\d+)*\.\s+[^\n]+)"
    parts = re.split(pattern, text)
    chunks = []
    current = ""
    header = None
    for part in parts:
        if re.match(r"\d+(?:\.\d+)*\.\s+", part.strip()):
            if current.strip():
                chunks.append({"content": current.strip(), "header": header})
            header = part.strip()
            current = part
        else:
            current += part
            if len(current) >= max_size:
                chunks.append({"content": current.strip(), "header": header})
                current = ""
                header = None
    if current.strip():
        chunks.append({"content": current.strip(), "header": header})
    return chunks


def chunk_recursive(text: str, max_size: int = 1000, overlap: int = 200) -> list[dict]:
    """Recursive splitter with overlap — fallback strategy."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_size, len(text))
        chunk_text = text[start:end]
        chunks.append({"content": chunk_text.strip(), "header": None})
        start += max_size - overlap
    return chunks


def select_chunking_strategy(doc_type: str, category: str | None) -> str:
    """Pick chunking strategy based on document metadata."""
    if category and category.upper() in ("LAW", "REGULATION", "KODEX"):
        return "articles"
    if doc_type.lower() in ("contract", "agreement"):
        return "sections"
    return "recursive"


# ── RAG service ─────────────────────────────────────────


class RAGService:
    """End-to-end RAG: ingest, chunk, embed, search."""

    def __init__(
        self,
        doc_repo: IKnowledgeDocumentRepository,
        chunk_repo: IKnowledgeChunkRepository,
        llm_service: OllamaLLMService,
    ) -> None:
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._llm = llm_service
        self._settings = get_settings()

    async def ingest_document(
        self,
        doc: KnowledgeDocument,
        file_path: str,
    ) -> int:
        """Extract, chunk, embed, and store a document. Returns chunk count."""
        ext = Path(file_path).suffix.lstrip(".").lower()
        extractor = EXTRACTORS.get(ext)
        if not extractor:
            raise ValueError(f"Unsupported file type: {ext}")

        text = extractor(file_path)
        if not text.strip():
            logger.warning("empty_document", document_name=doc.document_name)
            return 0

        # Select chunking
        strategy = select_chunking_strategy(doc.document_type, doc.category)
        if strategy == "articles":
            raw_chunks = chunk_by_articles(text, self._settings.rag_chunk_size)
        elif strategy == "sections":
            raw_chunks = chunk_by_sections(text, self._settings.rag_chunk_size)
        else:
            raw_chunks = chunk_recursive(text, self._settings.rag_chunk_size, self._settings.rag_chunk_overlap)

        # Build chunk entities
        total = len(raw_chunks)
        chunks_to_store: list[KnowledgeChunk] = []
        contents_to_embed: list[str] = []

        for idx, raw in enumerate(raw_chunks):
            content = raw["content"]
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            chunk = KnowledgeChunk(
                id=uuid4(),
                document_id=doc.id,
                legal_entity_id=doc.legal_entity_id,
                is_global=doc.is_global,
                document_name=doc.document_name,
                document_type=doc.document_type,
                category=doc.category,
                chunk_index=idx,
                total_chunks=total,
                section_header=raw.get("header"),
                content=content,
                content_hash=content_hash,
                metadata={"strategy": strategy},
            )
            chunks_to_store.append(chunk)
            contents_to_embed.append(content)

        # Batch embed
        batch_size = self._settings.embedding_batch_size
        all_embeddings: list[list[float]] = []
        for i in range(0, len(contents_to_embed), batch_size):
            batch = contents_to_embed[i : i + batch_size]
            embs = await self._llm.embed(batch)
            all_embeddings.extend(embs)

        for chunk, emb in zip(chunks_to_store, all_embeddings, strict=True):
            chunk.embedding = emb

        # Store
        created = await self._chunk_repo.bulk_create(chunks_to_store)
        await self._doc_repo.update_chunk_count(doc.id, created)

        logger.info("document_ingested", document_id=str(doc.id), chunks=created)
        return created

    async def search(
        self,
        query: str,
        *,
        legal_entity_id: UUID | None = None,
        category: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Semantic search with MMR reranking + optional hybrid fallback."""
        top_k = top_k or self._settings.rag_rerank_top_n
        initial_k = self._settings.rag_top_k

        # Embed query
        embeddings = await self._llm.embed([query])
        query_embedding = embeddings[0]

        # Semantic search
        candidates = await self._chunk_repo.semantic_search(
            query_embedding,
            legal_entity_id=legal_entity_id,
            category=category,
            top_k=initial_k,
        )

        # Hybrid fallback if low semantic scores
        if (
            self._settings.rag_hybrid_search
            and (not candidates or candidates[0].score < self._settings.rag_similarity_threshold)
        ):
            fts_results = await self._chunk_repo.fulltext_search(
                query, legal_entity_id=legal_entity_id, top_k=initial_k
            )
            seen_ids = {c.chunk_id for c in candidates}
            for fts in fts_results:
                if fts.chunk_id not in seen_ids:
                    candidates.append(fts)

        # MMR reranking (simplified — diversity selection)
        reranked = self._mmr_rerank(list(candidates), top_k)
        return reranked

    def _mmr_rerank(
        self,
        chunks: list[RetrievedChunk],
        top_n: int,
        lambda_param: float = 0.7,
    ) -> list[RetrievedChunk]:
        """Maximal Marginal Relevance reranking for diversity."""
        if len(chunks) <= top_n:
            return sorted(chunks, key=lambda c: c.score, reverse=True)

        selected: list[RetrievedChunk] = []
        remaining = list(chunks)

        # Pick highest score first
        remaining.sort(key=lambda c: c.score, reverse=True)
        selected.append(remaining.pop(0))

        while len(selected) < top_n and remaining:
            best_idx = 0
            best_score = -1.0
            for i, candidate in enumerate(remaining):
                relevance = candidate.score
                # Diversity penalty: penalize overlap with already selected
                max_sim = max(
                    self._content_similarity(candidate.content, s.content)
                    for s in selected
                )
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def _content_similarity(a: str, b: str) -> float:
        """Jaccard similarity on word sets — lightweight proxy."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
