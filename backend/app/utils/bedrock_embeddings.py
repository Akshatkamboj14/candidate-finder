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
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                body=json.dumps({"inputText": text})
            )
            
            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding", [])
            
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

            response = self.client.invoke_model(
                modelId=bedrock_config.completion_model_id,
                contentType="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": messages
                })
            )
            
            response_body = json.loads(response["body"].read())
            
            # Extract the response content
            if "content" in response_body:
                for content in response_body["content"]:
                    if content.get("type") == "text":
                        return content.get("text", "")
            
            raise ValueError("No text content in response")
        except Exception as e:
            raise RuntimeError(f"Failed to get completion from Bedrock: {str(e)}")

# Create a singleton instance
embedding_service = EmbeddingService()