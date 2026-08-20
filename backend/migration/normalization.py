import re

def clean_text(text: str) -> str:
    """Basic text cleaning: strips whitespaces, collapses multi-spaces, removes underscores/hyphens."""
    if not text:
        return ""
    # Replace underscores/hyphens/punctuation with spaces
    cleaned = re.sub(r'[\-_/\\.,;:!@#$%^&*()_+={}\[\]|?<>\"\'`~]', ' ', text)
    # Collapse multi-spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def normalize_case(text: str) -> str:
    """Converts to title case for standard representations."""
    return text.title()

def expand_abbreviations(text: str) -> str:
    """Expand common job role and status abbreviations."""
    cleaned = text.lower()
    # Expand senior/junior
    cleaned = re.sub(r'\bsr\b', 'senior', cleaned)
    cleaned = re.sub(r'\bjr\b', 'junior', cleaned)
    # Expand QA / UI / UX
    cleaned = re.sub(r'\bqa\b', 'quality assurance', cleaned)
    cleaned = re.sub(r'\bui\b', 'user interface', cleaned)
    cleaned = re.sub(r'\bux\b', 'user experience', cleaned)
    return cleaned

def normalize_job_title(title: str) -> str:
    """Normalize job title according to canonical specifications."""
    if not title:
        return ""
    
    cleaned = clean_text(title).lower()
    cleaned = expand_abbreviations(cleaned)
    
    # Handle specific replacements (e.g. backend engineer/programmer/developer)
    cleaned = re.sub(r'\b(back\s*end|back\-end)\b', 'backend', cleaned)
    cleaned = re.sub(r'\b(front\s*end|front\-end)\b', 'frontend', cleaned)
    cleaned = re.sub(r'\b(full\s*stack|full\-stack)\b', 'full stack', cleaned)
    
    # Map synonyms to 'developer'
    cleaned = re.sub(r'\b(engineer|programmer|coder)\b', 'developer', cleaned)
    
    # Standardize 'software engineer (backend)' style brackets
    # If the title matches something like 'software developer backend', convert to 'backend developer'
    if 'backend' in cleaned and 'developer' in cleaned:
        if cleaned.startswith('senior'):
            cleaned = 'senior backend developer'
        elif cleaned.startswith('junior'):
            cleaned = 'junior backend developer'
        else:
            cleaned = 'backend developer'
            
    if 'frontend' in cleaned and 'developer' in cleaned:
        if cleaned.startswith('senior'):
            cleaned = 'senior frontend developer'
        elif cleaned.startswith('junior'):
            cleaned = 'junior frontend developer'
        else:
            cleaned = 'frontend developer'
            
    # Collapse multiple whitespaces and return Title Case
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return normalize_case(cleaned)

def normalize_company_name(name: str) -> str:
    """Normalize company name by stripping legal suffixes and excess spaces."""
    if not name:
        return ""
    
    cleaned = clean_text(name).lower()
    
    # Suffixes pattern
    suffixes = [
        r'\bprivate\s+limited\b', r'\bpvt\s+ltd\b', r'\bpvt\b', r'\bltd\b',
        r'\bincorporated\b', r'\binc\b', r'\bcorporation\b', r'\bcorp\b',
        r'\bllc\b', r'\bllp\b', r'\bcompany\b', r'\bco\b'
    ]
    
    for suffix in suffixes:
        cleaned = re.sub(suffix, '', cleaned)
        
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return normalize_case(cleaned)
