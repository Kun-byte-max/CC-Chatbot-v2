import re

def normalize_text(text: str) -> str:
    """Helper to lowercase and clean basic punctuation/whitespace/underscores/hyphens."""
    if not text:
        return ""
    text = text.lower().strip()
    # Replace underscores/hyphens/punctuation with space
    text = re.sub(r'[\-_/\\.,;:!@#$%^&*()_+={}\[\]|?<>\"\'`~]', ' ', text)
    # Collapse multiple whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_job_title(title: str) -> str:
    """Normalize job title and convert to standard canonical form if recognized."""
    cleaned = normalize_text(title)
    if not cleaned:
        return ""
    
    # Common abbreviations/canonical mapping examples:
    # e.g., 'backend engineer' -> 'backend developer'
    # 'back-end developer' -> 'backend developer'
    # 'backend programmer' -> 'backend developer'
    cleaned = re.sub(r'\b(back\s*end|back\-end)\b', 'backend', cleaned)
    cleaned = re.sub(r'\b(front\s*end|front\-end)\b', 'frontend', cleaned)
    cleaned = re.sub(r'\b(full\s*stack|full\-stack)\b', 'full stack', cleaned)
    cleaned = re.sub(r'\b(devops|dev\s*ops)\b', 'devops', cleaned)
    cleaned = re.sub(r'\b(ui\s*ux|ui/ux)\b', 'ui ux', cleaned)
    
    cleaned = re.sub(r'\b(engineer|programmer|developer|coder)\b', 'developer', cleaned)
    cleaned = re.sub(r'\b(sr|senior)\b', 'senior', cleaned)
    cleaned = re.sub(r'\b(jr|junior)\b', 'junior', cleaned)
    
    # Re-collapse and trim
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned.title()

def normalize_company_name(company: str) -> str:
    """Normalize company name by removing legal suffixes and abbreviations."""
    cleaned = normalize_text(company)
    if not cleaned:
        return ""
    
    # List of legal suffixes to remove
    suffixes = [
        r'\bpvt\b', r'\bltd\b', r'\bprivate\b', r'\blimited\b', r'\bcorp\b',
        r'\bcorporation\b', r'\binc\b', r'\bincorporated\b', r'\bllp\b',
        r'\bllc\b', r'\bco\b', r'\bcompany\b', r'\bse\b', r'\bsa\b',
        r'\bgmbh\b', r'\bpt\b', r'\bpty\b', r'\bprivate limited\b', r'\bpvt ltd\b'
    ]
    
    for s in suffixes:
        cleaned = re.sub(s, '', cleaned)
        
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned.title()

def normalize_skill(skill: str) -> str:
    """Normalize skill name (standardizes case, spacing, etc.)."""
    cleaned = normalize_text(skill)
    if not cleaned:
        return ""
    
    # Map common aliases/typos to canonical skill names
    mapping = {
        "js": "javascript",
        "py": "python",
        "reactjs": "react",
        "react.js": "react",
        "nodejs": "node.js",
        "node": "node.js",
        "postgres": "postgresql",
        "sql server": "mssql",
        "html5": "html",
        "css3": "css",
        "typescriptjs": "typescript"
    }
    
    words = cleaned.split()
    mapped_words = [mapping.get(w, w) for w in words]
    cleaned = " ".join(mapped_words)
    
    # Specific full match replacements
    if cleaned in mapping:
        cleaned = mapping[cleaned]
        
    return cleaned.title() if len(cleaned) > 3 else cleaned.upper()

def normalize_location(location: str) -> str:
    """Normalize location names."""
    cleaned = normalize_text(location)
    if not cleaned:
        return ""
    
    # Common location standardizations
    mapping = {
        "bengaluru": "bangalore",
        "bombay": "mumbai",
        "new delhi": "delhi",
        "gurugram": "gurgaon",
        "wfh": "work from home",
        "remote": "work from home",
        "calcutta": "kolkata"
    }
    
    if cleaned in mapping:
        cleaned = mapping[cleaned]
        
    return cleaned.title()
