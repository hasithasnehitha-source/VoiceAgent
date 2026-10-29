import hashlib
import json
import logging
import math
import os
import re
from typing import List, Dict, Any, Optional
from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory
from app.db.models import KnowledgeDocument, DocumentChunk

logger = logging.getLogger("voice_agent.rag")


def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate mathematical cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def generate_fallback_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Generate deterministic semantic-hashed vector embedding for offline/testing mode.
    Maps words and character n-grams to a normalized dimensional hypersphere.
    """
    vector = [0.0] * dim
    clean_words = re.findall(r'\b\w+\b', text.lower())

    for word in clean_words:
        h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        vector[idx] += 1.0

    # L2 Normalization
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude > 0:
        vector = [round(x / magnitude, 6) for x in vector]
    else:
        vector = [0.0] * dim
    return vector


class RAGService:
    """Vector Retrieval-Augmented Generation (RAG) Service for Executive Documents."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.embedding_model = "text-embedding-004"
        self._init_gemini_client()

    def _init_gemini_client(self):
        if self.api_key and self.api_key.strip():
            try:
                self.client = genai.Client(api_key=self.api_key.strip())
                self.is_live = True
                logger.info("RAG Service initialized with live Google text-embedding-004.")
            except Exception as e:
                logger.warning(f"RAG Gemini client init failed: {e}. Using deterministic fallback.")
                self.client = None
                self.is_live = False
        else:
            self.client = None
            self.is_live = False
            logger.info("RAG Service running in local vector mode.")

    async def get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text using Google GenAI or local fallback."""
        if self.is_live and self.client:
            try:
                response = await self.client.aio.models.embed_content(
                    model=self.embedding_model,
                    contents=text
                )
                if response.embedding and response.embedding.values:
                    return list(response.embedding.values)
            except Exception as exc:
                logger.warning(f"Live embedding error: {exc}. Using fallback.")

        return generate_fallback_embedding(text)

    def chunk_text(self, text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
        """Split text into semantically overlapping paragraph chunks."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        # Fallback if text has no double line-breaks
        if not chunks and text.strip():
            words = text.split()
            for i in range(0, len(words), chunk_size - overlap):
                chunk = " ".join(words[i:i + chunk_size])
                chunks.append(chunk)

        return chunks or [text.strip()]

    async def ingest_document(
        self,
        title: str,
        content: str,
        filename: Optional[str] = None,
        category: str = "handbook"
    ) -> Dict[str, Any]:
        """Ingest document, generate vector embeddings, and store in the database."""
        chunks = self.chunk_text(content)
        if not chunks:
            return {"success": False, "error": "No content to ingest."}

        async with async_session_factory() as db:
            doc = KnowledgeDocument(
                title=title.strip(),
                filename=filename.strip() if filename else None,
                category=category.lower(),
                chunk_count=len(chunks)
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)

            for idx, chunk_text in enumerate(chunks):
                vector = await self.get_embedding(chunk_text)
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=chunk_text,
                    embedding_json=json.dumps(vector)
                )
                db.add(chunk_obj)

            await db.commit()
            logger.info(f"Ingested document '{doc.title}' with {len(chunks)} chunks.")

            return {
                "success": True,
                "document": doc.to_dict(),
                "chunks_ingested": len(chunks)
            }

    async def search_semantic(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.15
    ) -> List[Dict[str, Any]]:
        """Perform semantic cosine similarity vector search across knowledge chunks."""
        query_vector = await self.get_embedding(query)

        async with async_session_factory() as db:
            result = await db.execute(select(DocumentChunk, KnowledgeDocument).join(
                KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id
            ))
            rows = result.all()

            if not rows:
                return []

            scored_results = []
            for chunk, doc in rows:
                try:
                    chunk_vector = json.loads(chunk.embedding_json)
                    sim = compute_cosine_similarity(query_vector, chunk_vector)
                    if sim >= min_similarity:
                        scored_results.append({
                            "similarity": round(sim, 4),
                            "content": chunk.content,
                            "document_title": doc.title,
                            "category": doc.category,
                            "chunk_index": chunk.chunk_index
                        })
                except Exception as e:
                    logger.error(f"Error computing similarity for chunk {chunk.id}: {e}")

            scored_results.sort(key=lambda x: x["similarity"], reverse=True)
            return scored_results[:top_k]

    async def list_documents(self) -> List[Dict[str, Any]]:
        """List all ingested knowledge documents."""
        async with async_session_factory() as db:
            result = await db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()))
            docs = result.scalars().all()
            return [d.to_dict() for d in docs]


rag_service = RAGService()


# ---------------------------------------------------------------------------
# Seed Default Executive Handbook for Demo
# ---------------------------------------------------------------------------

DEFAULT_HANDBOOK = """# Executive Corporate Policies & Guidelines

## 1. Executive Travel & Accommodation Policy
All executive travel exceeding 4 hours of flight time is authorized for Business Class booking. Preferred airline partner is Delta Airlines and Singapore Airlines. Hotel accommodation is pre-approved for Marriott and Four Seasons with a standard nightly cap of $650 USD. Expense claims must be submitted within 14 days of travel conclusion.

## 2. Emergency Crisis & Escalation Protocol
In the event of severe cybersecurity incidents, data breaches, or critical infrastructure outages, immediately notify the Incident Response Commander at crisis@acme-corp.com and call the emergency hotline. All public statements and media communications must be vetted exclusively by General Counsel and VP of Communications.

## 3. Remote Work & Core Hours Guideline
Executives and senior management maintain flexible working arrangements. Core collaboration hours are 10:00 AM to 3:00 PM EST. Team sync meetings are strictly capped at 25 minutes to preserve focus time, with Fridays designated as No-Internal-Meetings days.

## 4. Quarterly Board Presentation Format
Board presentations must adhere to the 10-slide standard format: Executive Summary, OKR Scorecard, Financial Metrics (ARR, CAC, LTV), Product Velocity, Risk Assessment, and Strategic Next Steps. All decks must be distributed 72 hours before the scheduled meeting.
"""


async def seed_initial_knowledge_base():
    """Seed initial executive knowledge base if empty."""
    docs = await rag_service.list_documents()
    if not docs:
        logger.info("Seeding default Executive Corporate Policies into RAG vector store...")
        await rag_service.ingest_document(
            title="Executive Corporate Policies & Guidelines",
            content=DEFAULT_HANDBOOK,
            filename="executive_handbook.md",
            category="policy"
        )
