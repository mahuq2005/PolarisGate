import os, re, json, httpx, logging
import pypdf
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction

logger = logging.getLogger(__name__)

class SentenceTransformerEmbedding(EmbeddingFunction):
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.model.encode(input).tolist()

class AegisRAG:
    def __init__(self, persist_directory: str = "./aegis_db"):
        self.embedding_fn = SentenceTransformerEmbedding()
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="aida_compliance",
            embedding_function=self.embedding_fn
        )
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")

    def _extract_section(self, text: str) -> str:
        match = re.search(r'Section (\d+)', text)
        return f"Section {match.group(1)}" if match else None

    def ingest_pdf(self, pdf_path: str, doc_type: str = "regulation", original_filename: str = None) -> int:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        reader = pypdf.PdfReader(pdf_path)
        chunks, metadatas = [], []
        source_name = original_filename or os.path.basename(pdf_path)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            sentences = text.replace('. ', '.\n').split('\n')
            current_chunk = ""
            for sent in sentences:
                if len(current_chunk) + len(sent) < 1000:
                    current_chunk += sent + " "
                else:
                    if len(current_chunk.strip()) > 100:
                        section = self._extract_section(current_chunk)
                        chunks.append(current_chunk.strip())
                        metadatas.append({
                            "source": source_name, "type": doc_type,
                            "page": page_num + 1, "section": section,
                            "chunk_index": len(chunks)
                        })
                    current_chunk = sent + " "
            if len(current_chunk.strip()) > 100:
                section = self._extract_section(current_chunk)
                chunks.append(current_chunk.strip())
                metadatas.append({
                    "source": source_name, "type": doc_type,
                    "page": page_num + 1, "section": section,
                    "chunk_index": len(chunks)
                })
        if not chunks:
            raise ValueError("No text chunks extracted")
        ids = [f"{source_name}_{i}" for i in range(len(chunks))]
        self.collection.add(ids=ids, documents=chunks, metadatas=metadatas)
        logger.info(f"Ingested {len(chunks)} chunks from {source_name}")
        return len(chunks)

    async def query(self, model_name: str, industry: str = "finance", risk_level: str = "medium") -> Dict[str, Any]:
        query_text = f"AIDA compliance requirements for {model_name} in {industry} with risk level {risk_level}"
        results = self.collection.query(
            query_texts=[query_text],
            n_results=5,
            include=["documents", "metadatas", "distances"]
        )
        if not results['documents'][0]:
            return {"error": "No relevant documents found.", "report": "", "sources": []}

        context_chunks = results['documents'][0]
        context = "\n\n---\n\n".join(context_chunks)

        # NEW PROMPT – avoids refusal
        prompt = f"""Using the following AIDA compliance documents, write a 4‑section compliance summary for an AI model.

Model: {model_name}
Industry: {industry}
Risk Level: {risk_level}

Documents:
{context}

Sections to include:
1. Data Provenance Requirements
2. Bias Assessment Criteria
3. Human Oversight Obligations
4. Ongoing Monitoring Requirements

For each section, summarize what the documents say. If the documents don't mention a requirement, write "Not specified in documents."
Keep the tone professional and factual. End with a "Customer Input Required" section listing any gaps."""

        # Async call to Ollama with timeout
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.2:1b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 1500}
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                report_text = data.get("response", "")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"error": f"LLM generation failed: {e}", "report": "", "sources": []}

        sources = []
        for i, meta in enumerate(results['metadatas'][0]):
            label = f"{meta['source']} (page {meta['page']})"
            if meta.get('section'):
                label += f", {meta['section']}"
            sources.append({
                "label": label,
                "full_text": context_chunks[i],
                "text_preview": context_chunks[i][:300] + "...",
                "source_file": meta['source'],
                "page": meta['page'],
                "section": meta.get('section', '')
            })

        return {
            "report": report_text,
            "sources": sources,
            "model_name": model_name,
            "industry": industry,
            "risk_level": risk_level
        }
