# Export infrastructure components
from .aws.bedrock_config import bedrock_config
from .aws.bedrock_embeddings import embedding_service, get_embedding_for_text, get_text_completion
from .aws.vectorstore import query_similar, clear_collection, upsert_profile
from .cache.cache import cache

__all__ = [
    'bedrock_config',
    'embedding_service',
    'get_embedding_for_text',
    'get_text_completion',
    'query_similar',
    'clear_collection',
    'upsert_profile',
    'cache'
]