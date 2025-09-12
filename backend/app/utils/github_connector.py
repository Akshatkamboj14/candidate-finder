# backend/app/utils/github_connector.py
import os
import time
import requests
from typing import List, Dict, Optional
from .embeddings import get_embedding_for_text
from .vectorstore import upsert_profile
from dotenv import load_dotenv
from urllib.parse import quote_plus


# ---------- PyTorch / CNN evidence extractor (paste after imports) ----------
import re
from typing import List

_PYTORCH_PATTERNS = [
    r"\bimport\s+torch\b",
    r"\bfrom\s+torch\b",
    r"\btorch\.",
    r"\bPyTorch\b",
    r"\bConv2d\b",
    r"\bConv3d\b",
    r"\bconvolutional\b",
    r"\bcnn\b",
    r"\bnn\.Module\b",
    r"\btorchvision\b",
    r"\bkeras\b",
    r"\btensorflow\b",
]

def extract_evidence_from_text(text: str) -> List[str]:
    """Return list of matching evidence snippets found in text (deduped)."""
    if not text:
        return []
    evidence = []
    for pattern in _PYTORCH_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            snippet = text[start:end].replace("\n", " ")
            evidence.append(snippet.strip())
    # dedupe while preserving order
    seen = set()
    out = []
    for e in evidence:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out
# ---------------------------------------------------------------------------

















load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)


GITHUB_API_BASE = "https://api.github.com"

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# small helper: safely request and handle rate limit headers
def _req(path: str, params: dict = None, raw: bool = False) -> Optional[requests.Response]:
    url = path if path.startswith("http") else f"{GITHUB_API_BASE}{path}"
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            return resp if raw is False else resp
        if resp.status_code == 403:
            # rate-limited often; respect Retry-After or back off
            retry = resp.headers.get("Retry-After")
            wait = int(retry) if retry and retry.isdigit() else (attempt + 1) * 5
            time.sleep(wait)
            continue
        if resp.status_code in (404, 422):
            return None
        # Try short backoff for other 5xx/4xx transient errors
        time.sleep(1 + attempt)
    return None

def _get_user_search(query: str, per_page: int = 30, page: int = 1):
    # uses GitHub Search Users API: /search/users?q={query}
    q = quote_plus(query)
    path = f"/search/users"
    params = {"q": query, "per_page": per_page, "page": page}
    return _req(path, params=params)

def _get_user(username: str):
    return _req(f"/users/{username}")

def _get_user_repos(username: str, per_page: int = 5):
    # list user repos (sorted by updated)
    params = {"per_page": per_page, "sort": "updated", "direction": "desc"}
    return _req(f"/users/{username}/repos", params=params)

def _get_repo_readme(owner: str, repo: str):
    # Request raw README content
    headers = HEADERS.copy()
    headers["Accept"] = "application/vnd.github.v3.raw"
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
        return resp.text
    return None

def normalize_user_to_profile(user_obj: dict, top_repos: List[dict], readmes: Dict[str, str]) -> str:
    """
    Build a unified profile_text string from user metadata, repo READMEs and repo metadata.
    Enriches the profile with evidence snippets (PyTorch/CNN) extracted from bio + READMEs.
    """
    parts = []
    name = user_obj.get("name") or user_obj.get("login")
    bio = user_obj.get("bio") or ""
    location = user_obj.get("location") or ""
    blog = user_obj.get("blog") or ""
    html_url = user_obj.get("html_url") or ""
    parts.append(f"Name: {name}")
    if bio:
        parts.append(f"Bio: {bio}")
    if location:
        parts.append(f"Location: {location}")
    if blog:
        parts.append(f"Website: {blog}")
    parts.append(f"ProfileURL: {html_url}")

    parts.append("Top Repositories:")
    # include repo metadata and a longer README excerpt (more context helps evidence extraction)
    for r in top_repos:
        repo_line = f"- {r.get('name')} (stars: {r.get('stargazers_count')}, lang: {r.get('language')})\n  Description: {r.get('description') or ''}"
        parts.append(repo_line)
        readme = readmes.get(r.get('name'))
        if readme:
            # include a longer excerpt of the README (up to ~2000 chars)
            excerpt = (readme[:2000] + "...") if len(readme) > 2000 else readme
            parts.append(f"  README excerpt:\n{excerpt}")

    # Build full_text for evidence extraction (bio + all readmes)
    full_text = "\n\n".join(parts)
    # append full readmes to search body (not only excerpts)
    for rd in readmes.values():
        if rd:
            full_text += "\n\n" + rd

    evidence = extract_evidence_from_text(full_text)
    if evidence:
        parts.append("Detected evidence for PyTorch/CNN (snippets):")
        for e in evidence:
            # keep snippets short
            parts.append(f"- {e[:400]}")

    # small summary footer
    parts.append("EndProfile")
    doc = "\n\n".join(parts)
    return doc













































































def fetch_and_index_github_users(query: str, max_users: int = 50, per_user_repos: int = 3) -> List[Dict]:
    """
    Search GitHub users by `query` and index them into Chroma.
    Returns a list of dicts with {username, id, indexed, reason}
    """
    results_summary = []
    users_indexed = 0
    page = 1
    per_page = 30  # search results per page
    while users_indexed < max_users:
        resp = _get_user_search(query, per_page=per_page, page=page)
        if resp is None:
            break
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        for u in items:
            if users_indexed >= max_users:
                break
            username = u.get("login")
            # fetch user details
            user_resp = _get_user(username)
            if not user_resp:
                results_summary.append({"username": username, "indexed": False, "reason": "user_not_found"})
                continue
            user_obj = user_resp.json()
            # fetch top repos
            repos_resp = _get_user_repos(username, per_page=per_user_repos)
            top_repos = repos_resp.json() if repos_resp is not None else []
            # fetch READMEs for each repo (best effort)
            readmes = {}
            for r in top_repos:
                owner = r.get("owner", {}).get("login") or username
                repo_name = r.get("name")
                try:
                    rd = _get_repo_readme(owner, repo_name)
                    if rd:
                        readmes[repo_name] = rd
                except Exception:
                    pass
            # normalize to profile document
            profile_text = normalize_user_to_profile(user_obj, top_repos, readmes)
            # embedding
            try:
                vec = get_embedding_for_text(profile_text)
            except Exception as e:
                results_summary.append({"username": username, "indexed": False, "reason": f"embedding_error:{e}"})
                continue
            # upsert to vectorstore
            profile_id = f"github:{username}"
            try:
               has_evidence = bool(extract_evidence_from_text(profile_text))

		upsert_profile(
                     profile_id,
                   profile_text,
                            vec,
                      metadata={
                            "source": "github",
                            "username": username,
                            "profile_url": user_obj.get("html_url"),
                            "pyTorchEvidence": has_evidence,
                              },
                    )

                results_summary.append({"username": username, "id": profile_id, "indexed": True})
                users_indexed += 1
            except Exception as e:
                results_summary.append({"username": username, "indexed": False, "reason": f"upsert_error:{e}"})
        # next page
        page += 1
        # small sleep to be gentle
        time.sleep(1)
    return results_summary
