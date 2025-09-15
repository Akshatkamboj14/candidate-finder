import json
from typing import List, Optional
from .bedrock_config import bedrock_config

class EmbeddingService:
    def __init__(self):
        self.client = bedrock_config.get_bedrock_client()
        self.model_id = bedrock_config.embedding_model_id

    def get_embedding_for_text(self, text: str) -> List[float]:
        """Get embedding from AWS Bedrock Titan model"""
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
                
            return [float(x) for x in embedding]
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