"""RAG Pipeline API — document ingestion, embedding, vector search, graph retrieval."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from shared.security.auth import get_current_user
from shared.feature_flags import is_enabled, FeatureFlag

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    if not is_enabled(FeatureFlag.RAG_PIPELINE):
        return {"status": "disabled"}
    return {"status": "active", "documents_indexed": 0, "vector_db": "pgvector"}


@router.get("/graph/status")
async def graph_status(current_user: dict = Depends(get_current_user)):
    if not is_enabled(FeatureFlag.GRAPH_RAG):
        return {"status": "disabled"}
    return {"status": "active", "nodes": 0, "relationships": 0, "graph_db": "neo4j"}