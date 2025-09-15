import json
from typing import List, Dict, Any
from ...infrastructure.aws.bedrock_embeddings import embedding_service

class SkillExtractionService:
    def __init__(self):
        self.embedding_service = embedding_service

    def extract_skills(self, text: str) -> List[str]:
        """Extract technical skills from the given text."""
        prompt = """Extract the key technical skills from the following text. Return them as a comma-separated list.
        
        Example output: Python, JavaScript, React, Docker
        
        Text: {text}
        
        Skills:"""
        
        prompt = prompt.replace("{text}", text)
        
        response = self.embedding_service.get_text_completion(prompt)
        if not response:
            return []
        skills = [s.strip() for s in response.split(",") if s.strip()]
        return list(set(skills))

    def find_evidence(self, text: str, skills: List[str]) -> Dict[str, List[str]]:
        """Find evidence snippets for each skill in the text"""
        prompt = """Find evidence snippets that demonstrate these technical skills in the given text.
        Return ONLY a valid JSON object where keys are skills and values are arrays of relevant text snippets.
        Only include skills that have clear evidence in the text.
        The response must start with { and end with } and contain no other text.
        
        Skills: {skills}
        
        Text: {text}
        
        Evidence:"""
        
        prompt = prompt.replace("{skills}", ", ".join(skills))
        prompt = prompt.replace("{text}", text)
        
        response = self.embedding_service.get_text_completion(prompt)
        if not response:
            return {}
            
        # Clean up response to extract just the JSON object
        response = response.strip()
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            print("[WARNING] No JSON object found in response")
            return {}
            
        json_str = response[start_idx:end_idx + 1]
        
        try:
            evidence_map = json.loads(json_str)
            return {k: v for k, v in evidence_map.items() if v} # Remove empty lists
        except json.JSONDecodeError:
            print(f"[WARNING] Failed to parse evidence response as JSON: {json_str[:200]}...")
            return {}
        except Exception as e:
            print(f"[ERROR] Error processing evidence response: {str(e)}")
            return {}

# Create a singleton instance
skill_service = SkillExtractionService()

# For backward compatibility, keep some of the old patterns
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
    import re
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

def extract_keywords_from_jd(text: str, top_k: int = 8) -> List[str]:
    """Extract keywords from job description"""
    return skill_service.extract_skills(text)[:top_k] if top_k else skill_service.extract_skills(text)

def find_evidence_for_skills(docs: List[Dict[str, Any]], skills: List[str]) -> Dict[str, List[str]]:
    """Find evidence for skills in documents"""
    evidence_map = {}
    
    for doc in docs:
        doc_text = doc.get('document', '')
        doc_id = doc.get('id', '')
        
        if doc_text and doc_id:
            doc_evidence = skill_service.find_evidence(doc_text, skills)
            for skill, snippets in doc_evidence.items():
                if skill not in evidence_map:
                    evidence_map[skill] = []
                evidence_map[skill].extend(snippets)
    
    return evidence_map
