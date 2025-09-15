import uuid
from ..utils.embeddings import get_embedding_for_text
from ..utils.vectorstore import query_similar

class JobService:
    def __init__(self):
        self.job_store = {}

    async def create_job(self, jd: str, k: int) -> dict:
        """Create a new job with JD and retrieve top k semantically matched candidates"""
        import traceback
        try:
            job_id = str(uuid.uuid4())
            self.job_store[job_id] = {"jd": jd, "k": k}
            
            print(f"[DEBUG] Creating job with JD length: {len(jd)}")
            print(f"[DEBUG] JD content: {jd[:200]}...")  # Print first 200 chars
            
            # embed JD and query vector DB
            try:
                jd_vec = get_embedding_for_text(jd)
                print(f"[DEBUG] Embedding vector length: {len(jd_vec) if jd_vec else 'None'}")
            except Exception as e:
                print(f"[ERROR] Embedding creation failed: {str(e)}")
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
                raise ValueError(f"Failed to create embedding: {str(e)}")
                
            if not jd_vec:
                raise ValueError("Empty embedding vector returned")
                
            print("[DEBUG] Got embedding, querying similar documents...")
            
            try:
                # Get initial results from vector search
                candidates = query_similar(jd_vec, k=k)
                print(f"[DEBUG] Query returned {len(candidates)} candidates")
                
                # Calculate semantic similarity scores and confidence
                from numpy import dot
                from numpy.linalg import norm
                
                enhanced_results = []
                for candidate in candidates:
                    # Get candidate embedding
                    candidate_text = candidate.get("document", "")
                    candidate_vec = get_embedding_for_text(candidate_text)
                    
                    # Calculate cosine similarity
                    similarity = dot(jd_vec, candidate_vec)/(norm(jd_vec)*norm(candidate_vec))
                    confidence = "HIGH" if similarity >= 0.45 else ("MEDIUM" if similarity >= 0.35 else "LOW")  # Adjusted thresholds for more reasonable confidence levels
                    
                    # Extract skills from candidate
                    from ..utils.skills import extract_keywords_from_jd, find_evidence_for_skills
                    candidate_skills = extract_keywords_from_jd(candidate_text)
                    skill_evidence = find_evidence_for_skills([candidate], candidate_skills)
                    
                    enhanced_result = {
                        **candidate,
                        "similarity_score": round(similarity * 100, 2),
                        "confidence": confidence,
                        "matched_skills": candidate_skills,
                        "skill_evidence": skill_evidence
                    }
                    enhanced_results.append(enhanced_result)
                
                # Sort by similarity score
                enhanced_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
                
                print(f"[DEBUG] Enhanced {len(enhanced_results)} results with semantic matching")
                return {
                    "job_id": job_id, 
                    "results": enhanced_results,
                    "total_candidates": len(enhanced_results)
                }
                
            except Exception as e:
                print(f"[ERROR] Vector query failed: {str(e)}")
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
                raise ValueError(f"Failed to query vector store: {str(e)}")
            
            if not candidates:
                print("[DEBUG] No similar documents found")
                return {"job_id": job_id, "results": [], "total_candidates": 0}
        except Exception as e:
            print(f"[ERROR] Error in JobService.create_job: {str(e)}")
            print(f"[ERROR] Full traceback: {traceback.format_exc()}")
            raise

    def get_job(self, job_id: str) -> dict:
        """Retrieve a job by ID"""
        return self.job_store.get(job_id)