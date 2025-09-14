from typing import Optional, List, Dict, Any
from ..utils.embeddings import get_embedding_for_text, get_text_completion
from ..utils.skills import extract_keywords_from_jd, find_evidence_for_skills
from ..utils.vectorstore import query_similar
from .job_service import JobService

class RAGService:
    def __init__(self):
        self.job_service = JobService()

    async def process_rag_query(self, job_id: Optional[str], query: str, jd: Optional[str]) -> dict:
        """Process a RAG query with either job_id or direct JD"""
        # Determine JD to use
        jd_text = self._get_jd_text(job_id, jd)
        if not jd_text:
            return {"error": "must provide either job_id or jd"}

        # Retrieve and process documents
        docs = self._get_relevant_docs(jd_text)
        evidence_map = self._process_skills_and_evidence(jd_text, docs)
        
        # Generate answer using context
        answer = self._generate_answer(docs, evidence_map, jd_text, query)
        
        return {
            "answer": answer,
            "sources": [d.get("id") for d in docs],
            "evidence": evidence_map
        }

    def _get_jd_text(self, job_id: Optional[str], jd: Optional[str]) -> Optional[str]:
        """Get JD text from either job_id or direct JD"""
        if job_id:
            job = self.job_service.get_job(job_id)
            if job:
                return job["jd"]
        return jd

    def _get_relevant_docs(self, jd_text: str, k: int = 6) -> List[Dict[str, Any]]:
        """Get relevant documents for the JD"""
        jd_vec = get_embedding_for_text(jd_text)
        return query_similar(jd_vec, k=k)

    def _process_skills_and_evidence(self, jd_text: str, docs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Extract skills and find evidence in documents"""
        skill_tokens = extract_keywords_from_jd(jd_text, top_k=8)
        return find_evidence_for_skills(docs, skill_tokens)

    def _generate_answer(self, docs: List[Dict[str, Any]], evidence_map: Dict[str, List[str]], 
                        jd_text: str, query: str) -> str:
        """Generate answer using context and query"""
        context = self._build_context(docs, evidence_map)
        prompt = self._build_prompt(context, jd_text, query)
        return get_text_completion(prompt)

    def _build_context(self, docs: List[Dict[str, Any]], evidence_map: Dict[str, List[str]]) -> str:
        """Build context string from documents and evidence"""
        context_parts = []
        for d in docs:
            cid = d.get("id")
            doc_text = d.get("document", "")
            evid = evidence_map.get(cid, [])
            ev_text = ""
            if evid:
                ev_text = "\nEvidence snippets:\n" + "\n".join([f"- {e}" for e in evid])
            context_parts.append(f"Candidate: {cid}\n{doc_text}\n{ev_text}")
        return "\n\n---\n\n".join(context_parts)

    def _build_prompt(self, context: str, jd_text: str, query: str) -> str:
        """Build prompt for LLM completion"""
        return f"""
SYSTEM: You are an assistant that answers recruiter questions about candidates. Use ONLY the CONTEXT below — do NOT hallucinate.
INSTRUCTIONS:
1) For each candidate, say whether they match the query and list the exact evidence snippets you used (quotations).
2) Provide a confidence label for each candidate: HIGH / MEDIUM / LOW.
3) At the end, give a short conclusions list of candidate ids that match.

CONTEXT:
{context}

JD:
{jd_text}

QUERY:
{query}

Answer now.
"""