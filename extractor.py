import re

try:
    import spacy

    try:
        _NLP = spacy.load("en_core_web_sm")
    except OSError:
        _NLP = None
except ImportError:
    _NLP = None


# Keyword lexicon for preference / intent detection.
PREFERENCE_KEYWORDS = {
    "tourist_places": [
        "tourist", "attractions", "sightseeing", "places", "monuments",
        "temples", "landmarks", "museums", "parks", "famous places",
    ],
    "restaurants": [
        "restaurant", "food", "eat", "dining", "cuisine", "cafe", "street food",
    ],
    "hotels": [
        "hotel", "stay", "accommodation", "lodge", "resort", "homestay",
    ],
    "adventure": [
        "adventure", "trekking", "hiking", "sports", "adrenaline",
    ],
    "shopping": [
        "shopping", "market", "mall", "souvenirs",
    ],
    "nightlife": [
        "nightlife", "pub", "club", "bar",
    ],
}

BUDGET_KEYWORDS = {
    "budget": ["budget", "cheap", "affordable", "low cost", "economical"],
    "luxury": ["luxury", "premium", "5 star", "five star", "high end"],
    "mid-range": ["mid-range", "moderate", "3 star", "four star", "comfortable"],
}

TRIP_INTENT_PATTERNS = [
    r"\bplan\b.*\btrip\b",
    r"\bvisit\b",
    r"\btravel\b",
    r"\bitinerary\b",
    r"\btour\b",
]

DAYS_PATTERN = re.compile(r"(\d+)\s*(?:-|\s)?\s*day", re.IGNORECASE)

# Simple fallback location extraction: "to <Place>", "in <Place>", "for <Place>"
LOCATION_PATTERN = re.compile(
    r"\b(?:to|in|for|near)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)"
)

STOPWORDS_IN_LOCATION = {"Days", "Day", "Famous", "Good", "Budget"}


def detect_intent(text: str) -> str:
    """Very lightweight intent classifier: trip_planning vs unknown."""
    lowered = text.lower()
    for pattern in TRIP_INTENT_PATTERNS:
        if re.search(pattern, lowered):
            return "plan_trip"
    return "unknown"


def extract_destination(text: str) -> str | None:
    """Extract destination using spaCy NER (GPE/LOC) if available, else regex."""
    if _NLP is not None:
        doc = _NLP(text)
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC"):
                return ent.text.strip()

    # Fallback regex
    matches = LOCATION_PATTERN.findall(text)
    for m in matches:
        if m not in STOPWORDS_IN_LOCATION:
            return m.strip()
    return None


def extract_days(text: str) -> int:
    """Extract trip duration in days. Defaults to 3 if not mentioned."""
    match = DAYS_PATTERN.search(text)
    if match:
        return max(1, int(match.group(1)))
    return 3


def extract_preferences(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for category, keywords in PREFERENCE_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(category)
    if not found:
        # Sensible default: most travelers want sights + food
        found = ["tourist_places", "restaurants"]
    return found


def extract_budget(text: str) -> str:
    lowered = text.lower()
    for level, keywords in BUDGET_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return level
    return "mid-range"


def parse_travel_query(text: str) -> dict:
   
    return {
        "intent": detect_intent(text),
        "destination": extract_destination(text),
        "days": extract_days(text),
        "preferences": extract_preferences(text),
        "budget": extract_budget(text),
    }
