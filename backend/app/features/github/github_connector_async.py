import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
import json
import requests
from ...infrastructure.aws.bedrock_embeddings import get_embedding_for_text
from ...features.skills.skills import extract_evidence_for_skills_from_text
from ...infrastructure.aws.vectorstore import upsert_profile


class GitHubConnectorAsync:
    GITHUB_API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", None)
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"


    def _req(self, url: str, params: dict = None, raw=False, timeout=15):
        for attempt in range(3):
            try:
                r = requests.get(url, headers=self.headers, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r
                if r.status_code == 403:
                    # rate limited, back off a bit
                    retry = r.headers.get("Retry-After")
                    wait = int(retry) if (retry and retry.isdigit()) else (attempt + 1) * 2
                    time.sleep(wait)
                    continue
                if r.status_code in (404, 422):
                    return None
                time.sleep(0.5 + attempt)
            except Exception:
                time.sleep(0.5 + attempt)
        return None

    def search_users(self, query: str, page: int = 1, per_page: int = 30):
        url = f"{self.GITHUB_API_BASE}/search/users"
        return self._req(url, params={"q": query, "per_page": per_page, "page": page})

    def get_user(self, username: str):
        return self._req(f"{self.GITHUB_API_BASE}/users/{username}")

    def list_repos(self, username: str, per_page: int = 5):
        return self._req(
            f"{self.GITHUB_API_BASE}/users/{username}/repos",
            params={"per_page": per_page, "sort": "updated"},
        )

    def get_readme_raw(self, owner: str, repo: str):
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.raw"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.text
        except Exception:
            return None
        return None


    def normalize_user_to_profile(
        self, user_obj: dict, top_repos: List[dict], readmes: Dict[str, str]
    ) -> str:
        """
        Build a unified profile_text string from user metadata, repo READMEs and repo metadata.
        Enriches the profile with evidence snippets extracted from bio + READMEs.
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
            readme = readmes.get(r.get("name"))
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

        evidence = extract_evidence_for_skills_from_text(full_text)
        if evidence:
            parts.append("Detected skill evidence (snippets):")
            for skill, snippets in evidence.items():
                for snippet in snippets:
                    # keep snippets short
                    parts.append(f"- {skill}: {snippet[:400]}")

        # small summary footer
        parts.append("EndProfile")
        doc = "\n\n".join(parts)
        return doc


    def _fetch_user_bundle(self, username: str, per_user_repos: int = 3) -> Tuple[dict, list, dict, str]:
        try:
            uresp = self.get_user(username)
            if not uresp:
                return None, None, None, "user_not_found"
            user_obj = uresp.json()
            repos_resp = self.list_repos(username, per_page=per_user_repos)
            top_repos = repos_resp.json() if repos_resp is not None else []
            readmes = {}
            for r in top_repos:
                owner = r.get("owner", {}).get("login") or username
                repo = r.get("name")
                try:
                    rd = self.get_readme_raw(owner, repo)
                    if rd:
                        readmes[repo] = rd
                except Exception:
                    pass
            return user_obj, top_repos, readmes, None
        except Exception as e:
            return None, None, None, str(e)

    def fetch_and_index_github_users_concurrent(
        self, query: str, max_users: int = 50, per_user_repos: int = 3, concurrency: int = 8
    ) -> List[Dict]:
        """
        Search GitHub users by `query` and index them into Chroma.
        Returns a list of dicts with {username, id, indexed, reason}
        """
        summary = []
        users_indexed = 0
        # search pages until we have enough users
        users = []
        page = 1
        per_page = 30
        while len(users) < max_users:
            resp = self.search_users(query, page=page, per_page=per_page)
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
                future = ex.submit(self._fetch_user_bundle, username, per_user_repos)
                future_to_username[future] = username

            for fut in as_completed(future_to_username):
                username = future_to_username[fut]
                try:
                    user_obj, top_repos, readmes, reason = fut.result()
                    if not user_obj:
                        summary.append(
                            {
                                "username": username,
                                "indexed": False,
                                "reason": reason or "user_fetch_failed",
                            }
                        )
                        continue

                    profile_text = self.normalize_user_to_profile(
                        user_obj, top_repos or [], readmes or {}
                    )

                    # get embedding (this is blocking; you could batch these if you prefer)
                    try:
                        vec = get_embedding_for_text(profile_text)
                    except Exception as e:
                        summary.append(
                            {
                                "username": username,
                                "indexed": False,
                                "reason": f"embedding_err:{e}",
                            }
                        )
                        continue

                    profile_id = f"github:{username}"
                    try:
                        # Helper function to sanitize metadata values
                        def sanitize_value(value):
                            if value is None:
                                return ""
                            if isinstance(value, (str, int, float, bool)):
                                return value
                            return str(value)

                        meta = {
                            "source": "github",
                            "username": username,
                            "name": sanitize_value(user_obj.get("name")),
                            "bio": sanitize_value(user_obj.get("bio")),
                            "location": sanitize_value(user_obj.get("location")),
                            "email": sanitize_value(user_obj.get("email")),
                            "company": sanitize_value(user_obj.get("company")),
                            "blog": sanitize_value(user_obj.get("blog")),
                            "twitter_username": sanitize_value(user_obj.get("twitter_username")),
                            "public_repos": sanitize_value(user_obj.get("public_repos", 0)),
                            "public_gists": sanitize_value(user_obj.get("public_gists", 0)),
                            "followers": sanitize_value(user_obj.get("followers", 0)),
                            "following": sanitize_value(user_obj.get("following", 0)),
                            "created_at": sanitize_value(user_obj.get("created_at")),
                            "updated_at": sanitize_value(user_obj.get("updated_at")),
                            "profile_url": sanitize_value(user_obj.get("html_url")),
                            
                            # Add repository URLs as a JSON string
                            "repository_urls": json.dumps([
                                repo.get("html_url", "") for repo in (top_repos or [])
                                if repo.get("html_url")
                            ]),
                            
                            # Add repository details as a JSON string
                            "top_repositories": json.dumps([
                                {
                                    "name": sanitize_value(repo.get("name")),
                                    "description": sanitize_value(repo.get("description")),
                                    "language": sanitize_value(repo.get("language")),
                                    "stars": sanitize_value(repo.get("stargazers_count", 0)),
                                    "forks": sanitize_value(repo.get("forks_count", 0)),
                                    "url": sanitize_value(repo.get("html_url"))
                                }
                                for repo in (top_repos or [])
                            ])
                        }

                        # Extract evidence using the structured extractor
                        evidence_map = {}
                        try:
                            evidence_map = extract_evidence_for_skills_from_text(profile_text)
                        except Exception:
                            evidence_map = {}

                        # Normalize metadata: encode nested structures as JSON strings to be safe for Chroma
                        if evidence_map:
                            try:
                                meta["skills_evidence_json"] = json.dumps(evidence_map, ensure_ascii=False)
                            except Exception:
                                meta["skills_evidence_json"] = str(evidence_map)
                            # also store a simple skills list for quick filtering (as JSON string)
                            try:
                                skills_list = list(evidence_map.keys())
                                meta["skills_list"] = json.dumps([s.lower() for s in skills_list], ensure_ascii=False)
                            except Exception:
                                meta["skills_list"] = json.dumps(list(evidence_map.keys()))

                        # final upsert
                        upsert_profile(profile_id, profile_text, vec, metadata=meta)
                        summary.append({"username": username, "id": profile_id, "indexed": True})
                        users_indexed += 1
                    except Exception as e:
                        summary.append({"username": username, "indexed": False, "reason": f"upsert_err:{e}"})
                except Exception as exc:
                    summary.append({"username": username, "indexed": False, "reason": f"internal_exc:{exc}"})
        return summary
