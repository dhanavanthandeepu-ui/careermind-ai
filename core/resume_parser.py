"""
Resume PDF parsing utilities.

Extracts raw text from an uploaded PDF and splits it into the sections
CareerMind currently cares about: Skills, Education, Projects,
Certifications and Experience.

This is a lightweight, heuristic (keyword-based) parser only — no
external AI/NLP service is called. It scans the resume line by line,
recognises common section-heading keywords, and groups the lines that
follow each heading (until the next recognised heading) under that
section. Skill-gap calculation and readiness scoring are NOT part of
this module; they are a later step.

The "skills" section additionally goes through `clean_skills()`, which
normalizes raw extracted text into a clean, deduplicated list suitable
for a future skill-matching engine (bracketed "Category [ Tool ]"
labels, stray punctuation, duplicates, and inconsistent capitalization
are all handled there). Education / Projects / Certifications /
Experience are returned as before — this step does not touch them.
"""

import re
import unicodedata

from pypdf import PdfReader

# Canonical section name -> heading keywords that identify it in a resume.
SECTION_KEYWORDS = {
    "skills": [
        "skills", "technical skills", "core skills", "key skills",
        "skill set", "technologies", "tech stack",
    ],
    "education": [
        "education", "academic background", "academic qualifications",
        "educational qualifications",
    ],
    "projects": [
        "projects", "academic projects", "personal projects",
        "key projects", "project experience",
    ],
    "certifications": [
        "certifications", "certificates", "licenses  certifications",
        "professional certifications",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "internship experience", "internships",
    ],
}

# Flat lookup: heading text -> canonical section key.
_HEADING_TO_SECTION = {}
for _section, _keywords in SECTION_KEYWORDS.items():
    for _kw in _keywords:
        _HEADING_TO_SECTION[_kw] = _section


# Canonical display form for common tech skills, keyed by a lowercased,
# punctuation-stripped version of the skill name. Used only to fix
# capitalization of skills that are ALREADY present in the resume — it
# never adds a skill that wasn't extracted from the text.
CANONICAL_SKILLS = {
    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "docker": "Docker", "kubernetes": "Kubernetes", "terraform": "Terraform",
    "ansible": "Ansible", "jenkins": "Jenkins", "azure devops": "Azure DevOps",
    "aws": "AWS", "azure": "Azure", "gcp": "GCP",
    "python": "Python", "java": "Java", "javascript": "JavaScript",
    "typescript": "TypeScript", "nodejs": "Node.js", "node.js": "Node.js",
    "react": "React", "reactjs": "React", "angular": "Angular", "vue": "Vue.js",
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "cicd": "CI/CD", "ci cd": "CI/CD", "ci/cd": "CI/CD",
    "linux": "Linux", "html": "HTML", "css": "CSS", "rest api": "REST API",
    "restapi": "REST API", "graphql": "GraphQL", "kafka": "Kafka", "redis": "Redis",
    "c++": "C++", "c#": "C#", "golang": "Go", "go": "Go", "ruby": "Ruby",
    "php": "PHP", "django": "Django", "flask": "Flask", "spring": "Spring",
    "spring boot": "Spring Boot", "numpy": "NumPy", "pandas": "Pandas",
    "scikitlearn": "scikit-learn", "scikit-learn": "scikit-learn",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "tableau": "Tableau",
    "power bi": "Power BI", "powerbi": "Power BI", "excel": "Excel",
    "jira": "Jira", "confluence": "Confluence", "agile": "Agile", "scrum": "Scrum",
    "devops": "DevOps", "machine learning": "Machine Learning",
    "deep learning": "Deep Learning", "nlp": "NLP", "api": "API",
}

# Common phonetic transliterations of the same tech terms as they can
# appear on resumes written in an Indian regional script. Every entry
# maps a native-script spelling to the SAME canonical English skill
# name above — this never invents a skill, it only recognizes one
# that's already in CANONICAL_SKILLS under a different script.
# Starter set covering 9 widely-used tools/languages per language;
# expand as needed (ideally reviewed by a native speaker before
# relying on it for anything beyond a starting point).
MULTILINGUAL_SKILL_ALIASES = {
    # Docker
    "டாக்கர்": "Docker", "डॉकर": "Docker", "డాకర్": "Docker",
    "ಡಾಕರ್": "Docker", "ഡോക്കർ": "Docker",
    # Kubernetes
    "குபர்நெட்டீஸ்": "Kubernetes", "कुबरनेट्स": "Kubernetes",
    "కుబర్నెటెస్": "Kubernetes", "ಕುಬರ್ನೆಟಿಸ್": "Kubernetes",
    "കുബർനെറ്റിസ്": "Kubernetes",
    # Git
    "கிட்": "Git", "गिट": "Git", "గిట్": "Git", "ಗಿಟ್": "Git", "ഗിറ്റ്": "Git",
    # Python
    "பைதான்": "Python", "पायथन": "Python", "పైథాన్": "Python",
    "ಪೈಥಾನ್": "Python", "പൈത്തൺ": "Python",
    # Java
    "ஜாவா": "Java", "जावा": "Java", "జావా": "Java", "ಜಾವಾ": "Java", "ജാവ": "Java",
    # JavaScript
    "ஜாவாஸ்கிரிப்ட்": "JavaScript", "जावास्क्रिप्ट": "JavaScript",
    "జావాస్క్రిప్ట్": "JavaScript", "ಜಾವಾಸ್ಕ್ರಿಪ್ಟ್": "JavaScript",
    "ജാവാസ്ക്രിപ്റ്റ്": "JavaScript",
    # Linux
    "லினக்ஸ்": "Linux", "लिनक्स": "Linux", "లినక్స్": "Linux",
    "ಲಿನಕ್ಸ್": "Linux", "ലിനക്സ്": "Linux",
    # Jenkins
    "ஜென்கின்ஸ்": "Jenkins", "जेनकिंस": "Jenkins", "జెంకిన్స్": "Jenkins",
    "ಜೆಂಕಿನ್ಸ್": "Jenkins", "ജെങ്കിൻസ്": "Jenkins",
    # Azure
    "அஸூர்": "Azure", "एज़्योर": "Azure", "అజూర్": "Azure",
    "ಅಜೂರ್": "Azure", "അസൂർ": "Azure",
}
CANONICAL_SKILLS.update(MULTILINGUAL_SKILL_ALIASES)

# Characters that should be stripped from the edges of a skill token, or
# removed entirely as noise (brackets/braces/pipes are never meaningful
# inside a skill name).
_NOISE_CHARS = '[]{}|'
_EDGE_STRIP_CHARS = ' \t.,;:*-–—•·()'


def extract_text_from_pdf(file_obj) -> str:
    """Extract raw text from a PDF file-like object using pypdf."""
    reader = PdfReader(file_obj)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def _match_section_heading(line: str):
    """
    Return the canonical section key if `line` looks like a section heading.

    Heading recognition is currently English-only (e.g. "SKILLS",
    "WORK EXPERIENCE"). Resumes with section content in Tamil / Hindi /
    Telugu / Kannada / Malayalam under an English heading are supported
    (that's what CANONICAL_SKILLS' multilingual aliases are for) — a
    resume whose section HEADINGS are themselves in a regional script
    is not yet recognized and is a natural next step.
    """
    cleaned = re.sub(r'[^a-zA-Z& ]', '', line).strip().lower()
    if not cleaned or len(cleaned) > 40:
        return None
    return _HEADING_TO_SECTION.get(cleaned)


def _tokenize_skill_line(line: str):
    """
    Break one raw "skills" line into candidate skill tokens.

    Handles two common resume formats:
      - "Category [ Tool ]" / "Category (Tool)" — only the bracketed
        tool name is kept; the category label is a descriptive prefix,
        not a skill itself, so it's discarded.
      - "Python, Django, React" — a plain delimiter-separated list.

    A line may contain several bracket groups (e.g. "Cloud [AWS, GCP]"),
    each of which is tokenized in turn. Works the same way regardless of
    script (Latin, Tamil, Devanagari, Telugu, Kannada, Malayalam).
    """
    bracket_groups = re.findall(r'[\[({]\s*([^\[\]{}()]+?)\s*[\])}]', line)

    if bracket_groups:
        raw_tokens = []
        for group in bracket_groups:
            raw_tokens.extend(re.split(r'[,;•·]', group))
        return raw_tokens

    # No brackets: split on common list delimiters. Deliberately NOT
    # splitting on '/' or '.' so compound tokens like "CI/CD" and
    # "Node.js" survive intact.
    return re.split(r'[,;•·]', line)


def _clean_skill_token(token: str):
    """Strip noise characters and edge punctuation from a single skill token."""
    token = token.translate(str.maketrans('', '', _NOISE_CHARS))
    token = re.sub(r'\s+', ' ', token).strip(_EDGE_STRIP_CHARS).strip()
    return token


def _lookup_key(token: str) -> str:
    """
    Build the dictionary-lookup key for a skill token.

    Keeps letters, combining marks, and digits from ANY script — this
    matters for Tamil/Devanagari/Telugu/Kannada/Malayalam, whose vowel
    signs and virama are separate combining characters (Unicode category
    "Mn"/"Mc") that a plain `\\w` regex does NOT match and would
    otherwise silently strip, corrupting the word. `+`, `#`, `.` and
    space are kept too, since they're meaningful inside skill names
    like "C++", "C#", "Node.js", "CI/CD".
    """
    token = unicodedata.normalize('NFC', token)
    allowed_extra = set('+#. ')
    kept = [
        ch for ch in token
        if ch in allowed_extra or unicodedata.category(ch)[0] in ('L', 'M', 'N')
    ]
    return ''.join(kept).lower()


def _normalize_capitalization(token: str) -> str:
    """
    Fix capitalization consistently without inventing or altering meaning.

    - If the token matches a known skill — including a recognized
      Tamil/Hindi/Telugu/Kannada/Malayalam spelling of it — use that
      skill's canonical English display form (e.g. "டாக்கர்" -> "Docker").
    - If it's short and already all-uppercase, assume it's an acronym
      (e.g. "SQL", "AWS") and leave it as-is.
    - If it already has internal mixed case (e.g. "PyTorch", "JavaScript"),
      trust the resume's own casing and leave it as-is.
    - Non-Latin scripts (Tamil, Devanagari, Telugu, Kannada, Malayalam,
      etc.) have no case to fix, so an unrecognized native-script token
      is returned unchanged rather than mangled by title-casing.
    - Otherwise (plain lowercase Latin text), apply title case.
    """
    lookup_key = _lookup_key(token)
    if lookup_key in CANONICAL_SKILLS:
        return CANONICAL_SKILLS[lookup_key]

    if token.isupper() and len(token) <= 6:
        return token

    if not token.islower() and not token.isupper():
        return token

    return token.title()


def clean_skills(raw_lines):
    """
    Turn raw "skills" section lines into a clean, deduplicated list of
    skill names, ready for a future skill-matching engine.

    Every skill returned was actually present in the resume text — this
    only cleans formatting, it never invents skills.
    """
    cleaned = []
    seen = set()

    for line in raw_lines:
        for raw_token in _tokenize_skill_line(line):
            token = _clean_skill_token(raw_token)
            if not token:
                continue

            token = _normalize_capitalization(token)
            dedupe_key = token.lower()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            cleaned.append(token)

    return cleaned


def parse_resume_sections(text: str) -> dict:
    """
    Split resume text into skills / education / projects / certifications /
    experience buckets using section-heading detection.

    "skills" is returned as a clean, deduplicated list (see
    `clean_skills`). The other four sections are returned as the raw,
    non-empty lines found under their heading, unchanged from before.
    """
    sections = {key: [] for key in SECTION_KEYWORDS}
    current_section = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _match_section_heading(line)
        if heading:
            current_section = heading
            continue

        if current_section:
            sections[current_section].append(line)

    sections["skills"] = clean_skills(sections["skills"])

    return sections
