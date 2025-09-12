# backend/app/utils/skills.py
import re
from collections import Counter

STOPWORDS = {
    "with","and","experience","knowledge","in","the","a","an","of","for","on","using","skills","skill"
}

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

def find_evidence_for_skills(docs, skills):
    """
    docs: list of dicts with 'id' and 'document'
    skills: list of skill tokens (strings)
    returns: dict mapping doc id -> list of evidence snippets
    """
    out = {}
    if not skills:
        for d in docs:
            out[d.get("id")] = []
        return out

    for d in docs:
        text = (d.get("document","") or "").lower()
        snippets = []
        for s in skills:
            s_norm = s.lower()
            for m in re.finditer(re.escape(s_norm), text):
                start = max(0, m.start()-80)
                end = min(len(text), m.end()+80)
                snippet = text[start:end].replace("\n"," ")
                snippets.append(snippet.strip())
        seen = set(); uniq=[]
        for sn in snippets:
            if sn not in seen:
                seen.add(sn); uniq.append(sn)
            if len(uniq) >= 6:
                break
        out[d.get("id")] = uniq
    return out
