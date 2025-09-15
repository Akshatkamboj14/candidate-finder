import json
from typing import List, Optional
from .bedrock_config import bedrock_config
from .cache import cache

class EmbeddingService:
    def __init__(self):
        self.client = bedrock_config.get_bedrock_client()
        self.model_id = bedrock_config.embedding_model_id
        self.cache = cache

    def get_embedding_for_text(self, text: str) -> List[float]:
        """Get embedding from AWS Bedrock Titan model with caching"""
        # Check cache first
        cache_key = f"embedding_{self.model_id}_{text}"
        cached_embedding = self.cache.get(cache_key)
        if cached_embedding is not None:
            print("[DEBUG] Using cached embedding")
            return cached_embedding

        try:
            # Format request based on model type
            if "titan-embed" in self.model_id.lower():
                request_body = {
                    "inputText": text
                }
            else:
                # Default format for other embedding models
                request_body = {
                    "texts": [text]
                }
                
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response["body"].read())
            
            # Handle response based on model type
            if "titan-embed" in self.model_id:
                embedding = response_body.get("embedding", [])
            else:
                # For other models that return embeddings array
                embeddings = response_body.get("embeddings", [[]])
                embedding = embeddings[0] if embeddings else []
            
            if not embedding:
                raise ValueError("No embedding returned from model")
                
            embedding_floats = [float(x) for x in embedding]
            # Cache the result
            self.cache.set(cache_key, embedding_floats)
            return embedding_floats
        except Exception as e:
            raise RuntimeError(f"Failed to get embedding from Bedrock: {str(e)}")

    def get_text_completion(self, prompt: str, context: Optional[str] = None) -> str:
        """Get text completion from AWS Bedrock Claude model"""
        try:
            # Build messages array
            messages = []
            if context:
                messages.append({
                    "role": "system",
                    "content": context
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })

            # Format request based on model type
            if "claude-3" in bedrock_config.completion_model_id.lower():
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            else:
                # Default format for other completion models
                request_body = {
                    "prompt": messages[-1]["content"],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }

            response = self.client.invoke_model(
                modelId=bedrock_config.completion_model_id,
                contentType="application/json",
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response["body"].read())
            
            # Handle response based on model type
            if "claude-3" in bedrock_config.completion_model_id.lower():
                if "content" in response_body:
                    for content in response_body["content"]:
                        if content.get("type") == "text":
                            return content.get("text", "").strip()
                return ""
            else:
                # For other models that return text directly
                return response_body.get("text", response_body.get("completion", ""))
            
            raise ValueError("No text content in response")
        except Exception as e:
            raise RuntimeError(f"Failed to get completion from Bedrock: {str(e)}")

# Create a singleton instance
embedding_service = EmbeddingService()