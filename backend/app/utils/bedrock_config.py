import os
import boto3
from typing import Optional

class BedrockConfig:
    def __init__(self):
        # These should be loaded by main.py before this class is instantiated
        self.region = os.getenv("BEDROCK_REGION")
        if not self.region:
            print("[ERROR] BEDROCK_REGION not found in environment")
            raise ValueError("BEDROCK_REGION environment variable is required")
            
        self.completion_model_id = os.getenv("BEDROCK_COMPLETION_MODEL_ID")
        if not self.completion_model_id:
            print("[ERROR] BEDROCK_COMPLETION_MODEL_ID not found in environment")
            raise ValueError("BEDROCK_COMPLETION_MODEL_ID environment variable is required")
            
        self.embedding_model_id = os.getenv("BEDROCK_EMBEDDING_MODEL_ID")
        if not self.embedding_model_id:
            print("[ERROR] BEDROCK_EMBEDDING_MODEL_ID not found in environment")
            raise ValueError("BEDROCK_EMBEDDING_MODEL_ID environment variable is required")
            
        self._client = None
        
        # Debug logging for environment variables
        print(f"[DEBUG] AWS Configuration:")
        print(f"[DEBUG] Region: {self.region}")
        print(f"[DEBUG] AWS Access Key ID: {'Set' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not Set'}")
        print(f"[DEBUG] AWS Secret Key: {'Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'Not Set'}")
        print(f"[DEBUG] Completion Model: {self.completion_model_id}")
        print(f"[DEBUG] Embedding Model: {self.embedding_model_id}")

    @property
    def client(self):
        if self._client is None:
            try:
                aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
                aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
                
                if not aws_access_key or not aws_secret_key:
                    raise ValueError("AWS credentials not found in environment variables")
                
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
                print("[DEBUG] Successfully created Bedrock client")
            except Exception as e:
                print(f"[ERROR] Failed to create Bedrock client: {str(e)}")
                raise
        return self._client

    def get_bedrock_client(self):
        """Get or create Bedrock client"""
        # Debug print for AWS configuration
        print(f"[DEBUG] Bedrock Client Config:")
        print(f"[DEBUG] Region: {self.region}")
        print(f"[DEBUG] Access Key ID: {'Set' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not Set'}")
        print(f"[DEBUG] Secret Key: {'Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'Not Set'}")
        print(f"[DEBUG] Models:")
        print(f"[DEBUG] - Completion: {self.completion_model_id}")
        print(f"[DEBUG] - Embedding: {self.embedding_model_id}")
        
        # Return the client
        return self.client

# Create a singleton instance
bedrock_config = BedrockConfig()