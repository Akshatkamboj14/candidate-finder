# backend/app/utils/skills.py
import re
import json
from collections import Counter

SKILL_PATTERNS = {
    "pytorch": [r"\bimport\s+torch\b", r"\bfrom\s+torch\b", r"\btorch\.", r"\bPyTorch\b", r"\btorchvision\b", r"\bnn\.Module\b", r"\bconv(?:olutional)?\b", r"\bcnn\b"],
    "tensorflow": [r"\btensorflow\b", r"\btf\.keras\b", r"\bkeras\b"],
    "pandas": [r"\bimport\s+pandas\b", r"\bpandas\."],
    "python": [r"\bimport\s+python\b", r"\bdef\s+\w+\b", r"\bprint\(", r"\bclass\s+\w+:", r"\b\.py\b", r"\bflask\b", r"\bdjango\b", r"\b FastAPI\b", r"\b(numpy|scipy|matplotlib)\b"],
    "java": [r"\bimport\s+java\b", r"\bpublic\s+class\b", r"\bstatic\s+void\s+main", r"\b\.jar\b", r"\b\.java\b", r"\bspring\s+boot\b", r"\bhibernate\b"],
    "javascript": [r"\bfunction\s+\w+\(", r"\bconst\s+\w+\s*=\s*", r"\bvar\s+\w+\s*=\s*", r"\b\.js\b", r"\bnode\.js\b", r"\breact\b", r"\bangular\b", r"\bvue\.js\b", r"\bexpress\.js\b", r"\bnext\.js\b"],
    "html": [r"<\s*!DOCTYPE\s+html", r"<\s*html\b", r"<\s*body\b", r"<\s*div\b", r"\b\.html\b"],
    "css": [r"{\s*[\s\w-]+:\s*[\w\d]+;", r"\b\.css\b", r"\bstyle=[\"']", r"\bbootstrap\b", r"\b(tailwind|sass|less)\b"],
    "sql": [r"\bselect\s+\*\s+from\b", r"\binsert\s+into\b", r"\bupdate\s+\w+\s+set\b", r"\bdelete\s+from\b", r"\bjoin\s+\w+\s+on\b"],
    "c_cpp": [r"#include\s+<iostream>", r"\bstd::cout\b", r"\bint\s+main\s*\(", r"\bchar\s+\*?\s*\w+", r"\b\.c(pp)?\b"],
    "csharp": [r"\busing\s+system;", r"\bpublic\s+static\s+void\s+main", r"\b\.cs\b", r"\b.NET\b"],
    "go": [r"\bpackage\s+main\b", r"\bfunc\s+main\b", r"\bimport\s+\"fmt\"\b", r"\b\.go\b"],
    "ruby": [r"\bdef\s+\w+", r"\bclass\s+\w+", r"\bend\b", r"\bruby\s+on\s+rails\b"],
    "php": [r"\b<\?php", r"\bfunction\s+\w+\b", r"\blaravel\b", r"\bwordpress\b"],
    "aws": [r"\baws\b", r"\bamazon\s+web\s+services\b", r"\bS3\b", r"\bLambda\b", r"\bEC2\b", r"\bRDS\b", r"\bIAM\b", r"\bcloudformation\b", r"\b(cloudfront|ecs|eks|fargate)\b"],
    "azure": [r"\bazure\b", r"\bmicrosoft\s+azure\b", r"\bazure\s+functions\b", r"\bazure\s+devops\b", r"\b(azure\s+blobs|azure\s+app\s+service)\b"],
    "gcp": [r"\bgcp\b", r"\bgoogle\s+cloud\b", r"\bgoogle\s+compute\s+engine\b", r"\bcloud\s+storage\b", r"\bcloud\s+run\b", r"\b(gke|bigquery)\b"],
    "docker": [r"\bdocker\b", r"\bDockerfile\b", r"\bdocker\s+compose\b", r"\bdocker\s+image\b"],
    "kubernetes": [r"\bkube(ctl|rnetes)?\b", r"\bdeployment\.yaml\b", r"\bkind\s+cluster\b", r"\b(pod|service|ingress)\b", r"\bhelm\b", r"\bopenshift\b"],
    "ci_cd": [r"\b(ci/cd|continuous\s+integration|continuous\s+delivery|continuous\s+deployment)\b", r"\bjenkins\b", r"\bgithub\s+actions\b", r"\btravis\s+ci\b"],
    "terraform": [r"\bterraform\b", r"\b\.tf\b"],
    "ansible": [r"\bansible\b", r"\bansible\s+playbook\b"],
    "git": [r"\bgit\b", r"\bgit(hub|lab)\b", r"\bbitbucket\b", r"\bcommit\b", r"\bmerge\b", r"\bpull\s+request\b"],
    "mysql": [r"\bmysql\b", r"\b(my|sql)db\b"],
    "postgresql": [r"\bpostgresql\b", r"\b(postgres|psql)\b"],
    "mongodb": [r"\bmongo(db)?\b"],
    "redis": [r"\bredis\b"],
    "data_analysis": [r"\b(data|statistical)\s+analysis\b", r"\bdata\s+(science|analytics)\b", r"\bdata\s+(mining|visualization)\b", r"\bspark\b", r"\b(hadoop|hdfs)\b", r"\br\s+language\b"],
    "nosql": [r"\bnosql\b", r"\bcassandra\b", r"\bcouchdb\b"],
    "scikit_learn": [r"\b(sklearn|scikit-learn)\b"],
    "ml_ai": [r"\bmachine\s+learning\b", r"\bai\b", r"\bartificial\s+intelligence\b", r"\bdeep\s+learning\b", r"\bneural\s+network\b", r"\bnlp\b", r"\bcomputer\s+vision\b", r"\b(reinforcement|supervised|unsupervised)\s+learning\b"],
    "operating_systems": [r"\b(linux|ubuntu|centos|debian)\b", r"\b(windows|mac)\b", r"\b(unix|shell|bash)\b"],
    "networking": [r"\b(tcp/ip|http|dns|rest\s+api)\b", r"\b(network|socket)\s+programming\b", r"\b(firewall|protocol|ip\s+address)\b"],
    "security": [r"\b(cybersecurity|encryption|authentication|ssl)\b", r"\b(vulnerability|penetration\s+testing)\b"],
    "agile_methodologies": [r"\b(agile|scrum|kanban)\b", r"\b(sprint|stand-up)\b"]
}

STOPWORDS = {
    "with","and","experience","knowledge","in","the","a","an","of","for","on","using","skills","skill"
}

def extract_evidence_for_skills_from_text(text: str, skills: list = None, max_per_skill: int = 6):
    """
    Return a dict: { skill: [snippet, ...], ... }
    If skills is None: check all keys in SKILL_PATTERNS.
    Only include skills for which at least one snippet is found.
    """
    if not text:
        return {}
    skills_to_check = skills if skills else list(SKILL_PATTERNS.keys())
    out = {}
    lower_text = text  # keep case-sensitivity in regex via flags
    for skill in skills_to_check:
        patterns = SKILL_PATTERNS.get(skill, [])
        snippets = []
        for pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 80)
                snippet = text[start:end].replace("\n", " ").strip()
                snippets.append(snippet)
                if len(snippets) >= max_per_skill:
                    break
            if len(snippets) >= max_per_skill:
                break
        if snippets:
            # dedupe preserving order
            seen = set(); uniq=[]
            for s in snippets:
                if s not in seen:
                    seen.add(s); uniq.append(s)
                if len(uniq) >= max_per_skill:
                    break
            out[skill] = uniq
    return out

def extract_keywords_from_jd(jd_text: str, top_k: int = 8):
    """
    Lightweight extractor: picks tech-like tokens from JD.
    Returns a list of tokens to use as skill probes.
    """
    if not jd_text:
        return []
    tokens = re.findall(r"[A-Za-z0-9\-\+\.#]+", jd_text)
    tokens = [t for t in tokens if len(t) > 2]
    tech_candidates = [t for t in tokens if re.search(r"[A-Z]|[0-9]|[-\+#\.]", t)]
    if len(tech_candidates) < 3:
        tech_candidates = tokens
    normalized = [t.strip() for t in tech_candidates if t.lower() not in STOPWORDS]
    counts = Counter([t.lower() for t in normalized])
    common = [x for x,_ in counts.most_common(top_k)]
    seen=set(); out=[]
    for t in normalized:
        tl = t.lower()
        if tl in common and tl not in seen:
            seen.add(tl); out.append(t)
    return out[:top_k]

def find_evidence_for_skills(docs, skills, max_per_doc_skill=6):
    """
    Enhanced evidence retriever for RAG.

    Priority:
      1) If the document metadata contains a 'skills_evidence' dict, prefer snippets from there.
         The dict is expected as { skill_name: [snippet, ...], ... } (skill names may be any case).
      2) Otherwise, fall back to scanning the document text for the skill tokens (existing logic).

    Args:
      docs: list of dicts, each with at least 'id' and 'document', optionally 'metadata' (dict).
      skills: list of skill tokens (strings) extracted from JD.
      max_per_doc_skill: maximum snippets to return per skill per doc.

    Returns:
      dict mapping doc_id -> list of evidence snippet strings (deduped, limited).
    """
    out = {}
    if not docs:
        return {}

    # normalize requested skills to lowercase for matching
    skill_norms = [s.lower() for s in (skills or [])]

    # If no skills requested, return empty lists for each doc (consistent with prior behavior)
    if not skill_norms:
        for d in docs:
            out[d.get("id")] = []
        return out

    for d in docs:
        doc_id = d.get("id")
        meta = (d.get("metadata") or {}) if isinstance(d.get("metadata"), dict) else {}
        doc_text = (d.get("document", "") or "")
        snippets_for_doc = []

        # 1) Prefer metadata evidence if available
        skills_evidence = {}

        # metadata may carry JSON string or dict; try both safely
        if "skills_evidence_json" in meta and meta["skills_evidence_json"]:
            try:
                skills_evidence = json.loads(meta["skills_evidence_json"])
            except Exception:
                # best-effort: ignore parse errors and continue
                skills_evidence = {}
        elif "skills_evidence" in meta and isinstance(meta["skills_evidence"], dict):
            skills_evidence = meta["skills_evidence"]

        if isinstance(skills_evidence, dict) and skills_evidence:
            for sk in skill_norms:
                for meta_skill_key, snippets in skills_evidence.items():
                    if meta_skill_key and meta_skill_key.lower() == sk:
                        if isinstance(snippets, (list, tuple)):
                            for s in snippets[:max_per_doc_skill]:
                                if s and s not in snippets_for_doc:
                                    snippets_for_doc.append(s)
                        break
            if snippets_for_doc:
                out[doc_id] = snippets_for_doc[: max_per_doc_skill * len(skill_norms)]
                continue

        # 2) Fallback: scan document text for the skill tokens (original behavior)
        found_snippets = []
        for s in skill_norms:
            for m in re.finditer(re.escape(s), doc_text):
                start = max(0, m.start() - 80)
                end = min(len(doc_text), m.end() + 80)
                snippet = (d.get("document","") or "")[start:end].replace("\n", " ")
                if snippet not in found_snippets:
                    found_snippets.append(snippet)
                if len(found_snippets) >= max_per_doc_skill:
                    break
            if len(found_snippets) >= max_per_doc_skill:
                break

        # dedupe preserving order (should already be unique)
        seen = set(); uniq = []
        for sn in found_snippets:
            if sn not in seen:
                seen.add(sn); uniq.append(sn)
            if len(uniq) >= max_per_doc_skill:
                break

        out[doc_id] = uniq

    return out
