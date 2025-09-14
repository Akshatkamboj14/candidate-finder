from typing import List, Optional
from .bedrock_embeddings import embedding_service as bedrock_service

class EmbeddingService:
    def __init__(self):
        self.bedrock_service = bedrock_service

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text"""
        try:
            result = self.bedrock_service.get_embedding_for_text(text)
            print(f"[DEBUG] Successfully got embedding of length: {len(result) if result else 'None'}")
            return result
        except Exception as e:
            print(f"[ERROR] Error in get_embedding: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise

    def get_completion(self, prompt: str, context: Optional[str] = None) -> str:
        """Get completion from the chat model"""
        if context:
            prompt = f"Context: {context}\n\n{prompt}"
        return self.bedrock_service.generate_completion(prompt)

    def create_chain(self, prompt_template: str):
        """Create a chain with the given prompt template"""
        def run_chain(variables):
            filled_prompt = prompt_template.format(**variables)
            return self.get_completion(filled_prompt)
        return run_chain

# Create a singleton instance
embedding_service = EmbeddingService()



def get_embedding_for_text(text: str) -> list:
    """Get embedding for a text using the embedding service"""
    return embedding_service.get_embedding(text)



def get_text_completion(prompt: str, context: Optional[str] = None) -> str:
    """Get text completion using the embedding service"""
    return embedding_service.get_completion(prompt, context)





































































































































































































































































