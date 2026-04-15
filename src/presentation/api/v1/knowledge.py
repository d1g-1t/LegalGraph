from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from src.application.dto import (
    KnowledgeDocOut,
    KnowledgeStatsOut,
    PaginatedResponse,
    SearchChunkOut,
    SearchRequest,
    SearchResponse,
)
from src.domain.entities import ApiUser, KnowledgeDocument
from src.infrastructure.database.repositories import (
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
)
from src.infrastructure.queue.tasks import ingest_knowledge_document_task
from src.presentation.deps import get_current_user, get_db_session, require_roles

router = APIRouter()

_UPLOAD_DIR = Path("/tmp/legalops_uploads")


@router.post("/ingest", status_code=202, summary="Ingest document into KB")
async def ingest_document(
    file: UploadFile = File(...),
    category: str = Form(""),
    is_global: bool = Form(False),
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER")),
    session=Depends(get_db_session),
) -> dict:
    allowed_ext = {".pdf", ".docx", ".txt", ".md"}
    filename = file.filename or "unnamed"
    ext = Path(filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}. Allowed: {allowed_ext}")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=413, detail="File size exceeds 50MB limit")

    checksum = hashlib.sha256(content).hexdigest()

    type_map = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT", ".md": "TXT"}
    doc_type = type_map.get(ext, "TXT")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _UPLOAD_DIR / f"{uuid4().hex}_{filename}"
    file_path.write_bytes(content)

    doc = KnowledgeDocument(
        document_name=filename,
        document_type=doc_type,
        category=category or None,
        source_path=str(file_path),
        checksum=checksum,
        is_global=is_global,
        legal_entity_id=user.legal_entity_id,
    )

    repo = KnowledgeDocumentRepository(session)
    await repo.create(doc)

    ingest_knowledge_document_task.apply_async(
        args=[str(doc.id), str(file_path)],
        queue="legalops.ingest",
    )

    return {
        "document_id": str(doc.id),
        "document_name": doc.document_name,
        "status": "queued_for_ingestion",
    }


@router.get("/documents", response_model=PaginatedResponse, summary="List KB documents")
async def list_documents(
    user: ApiUser = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session=Depends(get_db_session),
) -> PaginatedResponse:
    repo = KnowledgeDocumentRepository(session)
    docs = await repo.list_documents(limit=limit, offset=offset)
    return PaginatedResponse(
        items=[
            KnowledgeDocOut(
                id=d.id,
                document_name=d.document_name,
                document_type=d.document_type,
                category=d.category,
                is_global=d.is_global,
                total_chunks=d.total_chunks,
                created_at=d.created_at,
            ).model_dump()
            for d in docs
        ],
        total=len(docs),
        limit=limit,
        offset=offset,
    )


@router.delete("/documents/{doc_id}", status_code=204, summary="Delete KB document")
async def delete_document(
    doc_id: UUID,
    user: ApiUser = Depends(require_roles("ADMIN")),
    session=Depends(get_db_session),
) -> None:
    repo = KnowledgeDocumentRepository(session)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunk_repo = KnowledgeChunkRepository(session)
    await chunk_repo.delete_by_document(doc_id)
    await repo.delete(doc_id)


@router.post("/search", response_model=SearchResponse, summary="Semantic search KB")
async def search_knowledge(
    body: SearchRequest,
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> SearchResponse:
    from src.infrastructure.llm import OllamaLLMService
    from src.infrastructure.rag import RAGService

    chunk_repo = KnowledgeChunkRepository(session)
    doc_repo = KnowledgeDocumentRepository(session)
    llm = OllamaLLMService()
    rag = RAGService(doc_repo, chunk_repo, llm)

    results = await rag.search(
        query=body.query,
        legal_entity_id=user.legal_entity_id,
        category=body.category,
        top_k=body.top_k,
    )
    return SearchResponse(
        query=body.query,
        total=len(results),
        chunks=[
            SearchChunkOut(
                chunk_id=r.chunk_id,
                document_name=r.document_name,
                section_header=r.section_header,
                page_number=r.page_number,
                content=r.content,
                score=r.score,
                category=r.category,
            )
            for r in results
        ],
    )


@router.get("/stats", response_model=KnowledgeStatsOut, summary="KB statistics")
async def kb_stats(
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> KnowledgeStatsOut:
    doc_repo = KnowledgeDocumentRepository(session)
    chunk_repo = KnowledgeChunkRepository(session)
    return KnowledgeStatsOut(
        total_documents=await doc_repo.count_total(),
        total_chunks=await chunk_repo.count_total(),
    )
