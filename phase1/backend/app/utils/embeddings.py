import os
import boto3
import base64
import json
from dotenv import load_dotenv

load_dotenv()
BEDROCK_REGION = os.getenv("BEDROCK_REGION")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

# Minimal Bedrock embedding + text completion wrappers.
# NOTE: adapt model_id and payload structure to the Bedrock model you want to use.


_bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def get_embedding_for_text(text: str) -> list:
    """Call Bedrock embedding model and return vector (list of floats).
    This is a placeholder — update according to the model's required payload.
    """
    payload = {"input": text}
    # Example: some Bedrock models accept 'input' and return 'embeddings' in body
    resp = _bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        body=bytes(json.dumps(payload), "utf-8"),
    )
    body = resp["body"].read()
    data = json.loads(body)
    # This assumes the model returns {'embeddings': [float,...]}
    vec = data.get("embeddings")
    return vec


def get_text_completion(prompt: str, max_tokens: int = 256) -> str:
    """_summary_

    Args:
        prompt (str): _description_
        max_tokens (int, optional): _description_. Defaults to 256.

    Returns:
        str: _description_
    """
    payload = {"input": prompt, "max_tokens": max_tokens}
    resp = _bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        body=bytes(json.dumps(payload), "utf-8"),
    )
    body = resp["body"].read()
    data = json.loads(body)
    # Adapt this to your model's text output key, e.g., 'output' or 'results'
    text = data.get("output") or data.get("results") or data.get("generated_text")
    if isinstance(text, list):
        text = "\n".join(text)
    return text