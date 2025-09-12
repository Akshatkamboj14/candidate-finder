# backend/app/utils/github_connector_async.py
import os, time, requests, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from .embeddings import get_embedding_for_text
from .vectorstore import upsert_profile
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
GITHUB_API_BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

def _req(url: str, params: dict = None, raw=False, timeout=15):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 403:
                # rate limited, back off a bit
                retry = r.headers.get("Retry-After")
                wait = int(retry) if (retry and retry.isdigit()) else (attempt+1)*2
                time.sleep(wait)
                continue
            if r.status_code in (404, 422):
                return None
            time.sleep(0.5 + attempt)
        except Exception:
            time.sleep(0.5 + attempt)
    return None

def search_users(query: str, page: int = 1, per_page: int = 30):
    url = f"{GITHUB_API_BASE}/search/users"
    return _req(url, params={"q": query, "per_page": per_page, "page": page})

def get_user(username: str):
    return _req(f"{GITHUB_API_BASE}/users/{username}")

def list_repos(username: str, per_page: int = 5):
    return _req(f"{GITHUB_API_BASE}/users/{username}/repos", params={"per_page": per_page, "sort":"updated"})

def get_readme_raw(owner: str, repo: str):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    headers = HEADERS.copy(); headers["Accept"]="application/vnd.github.v3.raw"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None

def normalize_user_to_profile(user_obj: dict, top_repos: List[dict], readmes: Dict[str,str]) -> str:
    parts = []
    name = user_obj.get("name") or user_obj.get("login")
    bio = user_obj.get("bio") or ""
    parts.append(f"Name: {name}")
    if bio:
        parts.append(f"Bio: {bio}")
    parts.append(f"ProfileURL: {user_obj.get('html_url')}")
    parts.append("Top Repositories:")
    for r in top_repos:
        parts.append(f"- {r.get('name')} (stars:{r.get('stargazers_count')}, lang:{r.get('language')})")
        rd = readmes.get(r.get("name"))
        if rd:
            parts.append("README excerpt:\\n" + "\\n".join(rd.splitlines()[:15]))
    return "\\n\\n".join(parts)

def fetch_and_index_github_users_concurrent(query: str, max_users: int = 50, per_user_repos: int = 3, concurrency: int = 8):
    summary = []
    # search pages until we have enough users
    users = []
    page = 1
    per_page = 30
    while len(users) < max_users:
        resp = search_users(query, page=page, per_page=per_page)
        if not resp:
            break
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        users.extend([it.get("login") for it in items])
        page += 1

    users = users[:max_users]

    # thread pool to fetch user details + repos + readmes concurrently
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        future_to_username = {}
        for username in users:
            future = ex.submit(_fetch_user_bundle, username, per_user_repos)
            future_to_username[future] = username

        for fut in as_completed(future_to_username):
            username = future_to_username[fut]
            try:
                user_obj, top_repos, readmes, reason = fut.result()
                if not user_obj:
                    summary.append({"username": username, "indexed": False, "reason": reason or "user_fetch_failed"})
                    continue

                profile_text = normalize_user_to_profile(user_obj, top_repos or [], readmes or {})

                # get embedding (this is blocking; you could batch these if you prefer)
                try:
                    vec = get_embedding_for_text(profile_text)
                except Exception as e:
                    summary.append({"username": username, "indexed": False, "reason": f"embedding_err:{e}"})
                    continue

                profile_id = f"github:{username}"
                try:
                    upsert_profile(profile_id, profile_text, vec, metadata={"source":"github","username":username,"profile_url":user_obj.get("html_url")})
                    summary.append({"username": username, "id": profile_id, "indexed": True})
                except Exception as e:
                    summary.append({"username": username, "indexed": False, "reason": f"upsert_err:{e}"})
            except Exception as exc:
                summary.append({"username": username, "indexed": False, "reason": f"internal_exc:{exc}"})
    return summary

def _fetch_user_bundle(username: str, per_user_repos: int = 3):
    try:
        uresp = get_user(username)
        if not uresp:
            return None, None, None, "user_not_found"
        user_obj = uresp.json()
        repos_resp = list_repos(username, per_page=per_user_repos)
        top_repos = repos_resp.json() if repos_resp is not None else []
        readmes = {}
        for r in top_repos:
            owner = r.get("owner",{}).get("login") or username
            repo = r.get("name")
            try:
                rd = get_readme_raw(owner, repo)
                if rd:
                    readmes[repo] = rd
            except Exception:
                pass
        return user_obj, top_repos, readmes, None
    except Exception as e:
        return None, None, None, str(e)

