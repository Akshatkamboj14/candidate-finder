import os
import json
import sys
from dotenv import load_dotenv

load_dotenv()

BEDROCK_REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
EMBED_MODEL = os.getenv("BEDROCK_EMBEDDING_MODEL_ID")
COMP_MODEL  = os.getenv("BEDROCK_COMPLETION_MODEL_ID")
DEV_DUMMY = os.getenv("DEV_DUMMY_EMBEDDINGS", "false").lower() in ("1","true","yes")

_bedrock_client = None

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is not None:
        return _bedrock_client
    try:
        import boto3
    except Exception as e:
        raise RuntimeError("boto3 not installed: " + str(e))
    region = BEDROCK_REGION or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("No AWS region configured. Set BEDROCK_REGION / AWS_REGION / AWS_DEFAULT_REGION in env.")
    _bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_client

def _invoke_model_raw(model_id: str, payload: dict):
    """
    Call bedrock invoke_model and return (status_ok:bool, parsed_json_or_text)
    """
    client = get_bedrock_client()
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json", body=bytes(json.dumps(payload), "utf-8"))
        body = resp["body"].read()
        try:
            data = json.loads(body)
        except Exception:
            data = body.decode("utf-8", errors="replace")
        return True, data
    except Exception as e:
        # If boto3 raised, try to extract error response if present
        err_text = str(e)
        return False, err_text

def _try_extract_embedding(data):
    # common shapes
    if isinstance(data, dict):
        if "embedding" in data and isinstance(data["embedding"], list):
            return data["embedding"]
        if "embeddings" in data and isinstance(data["embeddings"], list):
            # possibly list of vectors
            if len(data["embeddings"]) and isinstance(data["embeddings"][0], (list, float, int)):
                return data["embeddings"][0] if isinstance(data["embeddings"][0], list) else data["embeddings"]
        if "results" in data and isinstance(data["results"], list):
            for item in data["results"]:
                if isinstance(item, dict):
                    if "embedding" in item:
                        return item["embedding"]
                    if "embeddings" in item:
                        return item["embeddings"][0] if isinstance(item["embeddings"], list) else item["embeddings"]
        if "output" in data:
            out = data["output"]
            if isinstance(out, list) and len(out) and isinstance(out[0], dict) and "embedding" in out[0]:
                return out[0]["embedding"]
    return None

def get_embedding_for_text(text: str) -> list:
    """
    Try several payload shapes for embeddings. If DEV_DUMMY_EMBEDDINGS=true returns a dummy vector.
    If the model rejects payloads, the last raw response is included in the RuntimeError to help debugging.
    """
    if DEV_DUMMY:
        # cheap dev vector (change dim as you need)
        return [0.0] * 1536

    if not EMBED_MODEL:
        raise RuntimeError("BEDROCK_EMBEDDING_MODEL_ID not set in env. Set it to an embedding model id (e.g. amazon.titan-embed-text-v2:0).")

    candidate_payloads = [
        {"input": text},                        # common for many embedding models
        {"text": text},                         # alternative
        {"prompt": text, "max_tokens_to_sample": 0},  # completion shaped payload (to see model response)
    ]

    last_resp = None
    for payload in candidate_payloads:
        ok, data = _invoke_model_raw(EMBED_MODEL, payload)
        last_resp = data
        emb = None
        if ok:
            emb = _try_extract_embedding(data)
            if emb:
                # normalize
                flat = []
                if isinstance(emb[0], (list,)):
                    emb = emb[0]
                for v in emb:
                    flat.append(float(v))
                return flat
            # no embedding found — continue to try next payload
        else:
            # invocation itself failed; keep the text for error message
            last_resp = data

    # nothing worked — raise with clear diagnostic
    err_msg = (
        "Failed to obtain embeddings from Bedrock embedding model.\n"
        f"ModelId={EMBED_MODEL}\n"
        "Tried payload shapes: 'input', 'text', 'prompt+max_tokens_to_sample'.\n"
        "Last response (or exception text):\n"
        f"{json.dumps(last_resp, indent=2) if isinstance(last_resp, (dict,list)) else str(last_resp)}\n\n"
        "Actionable steps:\n"
        "  * Ensure BEDROCK_EMBEDDING_MODEL_ID is an embedding model (eg. amazon.titan-embed-text-v2:0).\n"
        "  * Inspect the raw response above to learn the required payload shape.\n"
        "  * For fast iteration, set DEV_DUMMY_EMBEDDINGS=true in env to use dummy vectors while you debug.\n"
    )
    raise RuntimeError(err_msg)



def get_text_completion(prompt: str, max_tokens: int = 256) -> str:
    """
    Call Bedrock text model for generation.

    Uses the Messages API shape for Anthropic/Claude models on Bedrock:
      {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": <int>,
        "system": "<system instruction>",        # optional top-level system entry
        "messages": [
          {"role":"user","content":[{"type":"text","text":"..."}]},
          {"role":"assistant","content":[{"type":"text","text":""}]}
        ]
      }

    Falls back to a simple prompt payload for other models.
    """
    if not COMP_MODEL:
        raise RuntimeError("BEDROCK_COMPLETION_MODEL_ID not set in env.")
    client = get_bedrock_client()
    model_lower = COMP_MODEL.lower() if COMP_MODEL else ""
    is_anthropic = ("claude" in model_lower) or ("anthropic" in model_lower)

    if is_anthropic:
        # required by Bedrock for Anthropic Claude
        anthropic_version = "bedrock-2023-05-31"
        system_instruction = (
            "You are an assistant that answers questions about candidate profiles. "
            "Be concise and list candidate ids you reference."
        )
        # Build messages: top-level 'system' is allowed by Bedrock examples (and avoids using role 'system' inside messages)
        payload = {
            "anthropic_version": anthropic_version,
            "max_tokens": max_tokens,
            "system": system_instruction,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
        }

        ok, data = None, None
        try:
            ok, data = _invoke_model_raw(COMP_MODEL, payload)
        except Exception as e:
            raise RuntimeError(f"Text completion call failed (invoke error): {e}")

        if not ok:
            raise RuntimeError(f"Text completion call failed: {data}")

        # Parse typical Bedrock messages response:
        # data may look like: {"id": "...", "outputs":[{"content":[{"type":"output_text","text":"..."}]}], ...}
        if isinstance(data, dict) and "outputs" in data:
            try:
                outputs = data.get("outputs", [])
                if outputs and isinstance(outputs, list):
                    first_out = outputs[0]
                    content_list = first_out.get("content", []) if isinstance(first_out, dict) else []
                    # find first text in content_list
                    for c in content_list:
                        # content items vary: use keys 'text' or 'output_text'
                        text = c.get("text") or c.get("output_text") or c.get("content")
                        if text:
                            return text if isinstance(text, str) else str(text)
                    # fallback: join any textual elements
                    texts = []
                    for c in content_list:
                        for k in ("text", "output_text", "content"):
                            if k in c:
                                texts.append(str(c[k]))
                    if texts:
                        return "\n".join(texts)
            except Exception:
                pass

        # If we couldn't parse a usable answer, raise with diagnostic
        raise RuntimeError(f"Text completion returned unexpected format. Raw response: {data}")

    else:
        # Non-Anthropic fallback: simple prompt-style payload (may work for other models)
        payload = {"prompt": prompt, "max_tokens_to_sample": max_tokens}
        ok, data = None, None
        try:
            ok, data = _invoke_model_raw(COMP_MODEL, payload)
        except Exception as e:
            raise RuntimeError(f"Text completion call failed (invoke error): {e}")
        if not ok:
            raise RuntimeError(f"Text completion call failed: {data}")
        if isinstance(data, dict):
            for key in ("completion", "output", "results", "generated_text", "output_text", "text"):
                if key in data:
                    v = data[key]
                    if isinstance(v, list):
                        return "\n".join([str(x) for x in v])
                    return str(v)
        return str(data)




































































































































































































































































