import uuid
from ..utils.embeddings import get_embedding_for_text
from ..utils.vectorstore import query_similar

class JobService:
    def __init__(self):
        self.job_store = {}

    async def create_job(self, jd: str, k: int) -> dict:
        """Create a new job with JD and retrieve top k candidates"""
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
                results = query_similar(jd_vec, k=k)
                print(f"[DEBUG] Query returned {len(results)} results")
            except Exception as e:
                print(f"[ERROR] Vector query failed: {str(e)}")
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
                raise ValueError(f"Failed to query vector store: {str(e)}")
            
            if not results:
                print("[DEBUG] No similar documents found")
                results = []
                
            return {"job_id": job_id, "results": results}
        except Exception as e:
            print(f"[ERROR] Error in JobService.create_job: {str(e)}")
            print(f"[ERROR] Full traceback: {traceback.format_exc()}")
            raise

    def get_job(self, job_id: str) -> dict:
        """Retrieve a job by ID"""
        return self.job_store.get(job_id)