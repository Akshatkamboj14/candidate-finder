from typing import Optional, List, Dict, Any
from ..utils.embeddings import get_embedding_for_text, get_text_completion
from ..utils.skills import extract_keywords_from_jd, find_evidence_for_skills
from ..utils.vectorstore import query_similar
from .job_service import JobService

class RAGService:
    def __init__(self):
        self.job_service = JobService()

    async def process_rag_query(self, job_id: Optional[str], query: str, jd: Optional[str]) -> dict:
        """Process a RAG query with either job_id or direct JD with semantic matching"""
        # Determine JD to use
        jd_text = self._get_jd_text(job_id, jd)
        if not jd_text:
            return {"error": "must provide either job_id or jd"}

        # Get semantically similar candidates with scores
        docs = self._get_relevant_docs(jd_text)
        evidence_map = self._process_skills_and_evidence(jd_text, docs)
        
        # Generate detailed analysis using context
        answer = self._generate_answer(docs, evidence_map, jd_text, query)
        
        # Prepare candidate rankings with semantic scores
        ranked_candidates = [{
            "id": d.get("id"),
            "similarity_score": d.get("similarity_score", 0),
            "confidence": d.get("confidence", "LOW"),
            "skills": list(self._extract_candidate_skills(d)),
            "evidence": evidence_map.get(d.get("id"), [])
        } for d in docs]
        
        return {
            "answer": answer,
            "candidates": ranked_candidates,
            "total_candidates": len(ranked_candidates)
        }

    def _get_jd_text(self, job_id: Optional[str], jd: Optional[str]) -> Optional[str]:
        """Get JD text from either job_id or direct JD"""
        if job_id:
            job = self.job_service.get_job(job_id)
            if job:
                return job["jd"]
        return jd

    def _get_relevant_docs(self, jd_text: str, k: int = 6) -> List[Dict[str, Any]]:
        """Get relevant documents for the JD using semantic search"""
        # Get JD embedding
        jd_vec = get_embedding_for_text(jd_text)
        
        # Get similar candidates with scores
        candidates = query_similar(jd_vec, k=k)
        
        # Enhance each candidate with semantic similarity score
        for candidate in candidates:
            # Get candidate text embedding
            candidate_text = candidate.get("document", "")
            candidate_vec = get_embedding_for_text(candidate_text)
            
            # Calculate cosine similarity score
            similarity_score = self._calculate_similarity(jd_vec, candidate_vec)
            candidate["similarity_score"] = round(similarity_score * 100, 2)  # Convert to percentage
            
            # Add confidence level based on similarity score
            candidate["confidence"] = self._get_confidence_level(similarity_score)
            
        # Sort by similarity score
        candidates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        return candidates

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

    def _extract_candidate_skills(self, doc: Dict[str, Any]) -> set:
        """Extract unique skills from a candidate document"""
        skills = set()
        # Extract from metadata if available
        if "metadata" in doc and doc["metadata"]:
            if "skills_list" in doc["metadata"]:
                try:
                    skills.update(doc["metadata"]["skills_list"])
                except:
                    pass
            if "skills_list_json" in doc["metadata"]:
                try:
                    if isinstance(doc["metadata"]["skills_list_json"], str):
                        import json
                        skills.update(json.loads(doc["metadata"]["skills_list_json"]))
                    else:
                        skills.update(doc["metadata"]["skills_list_json"])
                except:
                    pass
        
        # Extract from document text using skill patterns
        from ..utils.skills import SKILL_PATTERNS
        import re
        doc_text = doc.get("document", "").lower()
        for skill, patterns in SKILL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, doc_text, re.IGNORECASE):
                    skills.add(skill)
                    break
        
        return skills

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

    def _calculate_similarity(self, vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        # Convert to numpy arrays if they aren't already
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2)

    def _get_confidence_level(self, similarity_score: float) -> str:
        """Determine confidence level based on similarity score"""
        if similarity_score >= 0.85:
            return "HIGH"
        elif similarity_score >= 0.70:
            return "MEDIUM"
        else:
            return "LOW"

    def _build_prompt(self, context: str, jd_text: str, query: str) -> str:
        """Build prompt for LLM completion"""
        return f"""
SYSTEM: You are an expert recruiter assistant that evaluates candidates based on job descriptions. Use ONLY the CONTEXT below — do NOT make assumptions.
INSTRUCTIONS:
1) Analyze each candidate's fit for the job description:
   - List key matching skills and experiences
   - Note any missing required skills
   - Highlight relevant projects or accomplishments
2) Include similarity scores and confidence levels in your analysis
3) Rank candidates by their overall fit for the role
4) At the end, provide:
   - Top 3 best matching candidates with reasons
   - Any red flags or concerns
   - Suggested next steps for each promising candidate

CONTEXT:
{context}

JOB DESCRIPTION:
{jd_text}

QUERY:
{query}

Provide your analysis now.
"""