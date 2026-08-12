"""Natural Language → SQL Translator for sovereign 6TB datasets.

Hybrid approach:
- Primary: sentence-transformers embedding matching (if installed)
- Fallback: regex/keyword template extraction (zero dependencies)
- Optional: Ollama LLM for complex unseen queries

Templates are extensible — add your domain's queries in TEMPLATES.
"""

import json
import re
import os
import logging
from typing import Optional

logger = logging.getLogger("nl2sql")

# ── SQL Templates (extensible per domain) ──────────────

TEMPLATES = [
    {
        "intent": "survival_rate",
        "pattern": r"(survival|hr|hazard ratio|os|overall survival).*(EGFR|ALK|KRAS|WT|mutant|wild)",
        "sql": "SELECT treatment, hr, ci_low, ci_high, p_value, survival_months FROM oncology WHERE treatment ILIKE '%{entity}%' ORDER BY survival_months DESC LIMIT 10;",
        "example": "what is the survival rate for EGFR?",
        "domain": "oncology",
    },
    {
        "intent": "toxicity",
        "pattern": r"(toxicity|side effect|ae|adverse event|grade 3|grade 4)",
        "sql": "SELECT ae_name, grade, rate, n FROM safety WHERE ae_name ILIKE '%{entity}%' AND grade >= 3 ORDER BY rate DESC LIMIT 10;",
        "example": "show grade 3 toxicity for EGFR inhibitors",
        "domain": "safety",
    },
    {
        "intent": "cohort_summary",
        "pattern": r"(cohort|population|demographics|age|gender|stage)",
        "sql": "SELECT stage, count(*) as n, avg(age) as mean_age FROM demographics GROUP BY stage;",
        "example": "summarize the patient cohort",
        "domain": "demographics",
    },
    {
        "intent": "causal_query",
        "pattern": r"(what causes|cause of|why does|reason for|what leads to)",
        "sql": "SELECT source_note_id, relation, target_note_id, confidence FROM edges WHERE variant = 'causal' AND source_note_id ILIKE '%{entity}%' LIMIT 20;",
        "example": "what causes demand drop?",
        "domain": "vaultlens",
    },
    {
        "intent": "evidential_query",
        "pattern": r"(evidence|supports|proves|confirms|validates|backs|corroborates)",
        "sql": "SELECT source_note_id, relation, target_note_id, confidence FROM edges WHERE variant = 'evidential' AND target_note_id ILIKE '%{entity}%' LIMIT 20;",
        "example": "what evidence supports rate hikes?",
        "domain": "vaultlens",
    },
    {
        "intent": "general",
        "pattern": r".*",
        "sql": "SELECT * FROM oncology LIMIT 5;",
        "example": "show me some data",
        "domain": "general",
    },
]

# ── Entity extraction ──────────────────────────────────

KNOWN_ENTITIES = [
    "EGFR", "ALK", "KRAS", "WT", "mutant", "wild",
    "NSCLC", "breast", "lung", "colon", "melanoma",
    "inflation", "demand drop", "rate hikes", "recession",
    "monetary policy", "interest rate", "supply shock",
]


def extract_entity(text: str) -> str:
    """Extract a known entity from natural language text."""
    for entity in sorted(KNOWN_ENTITIES, key=len, reverse=True):
        if entity.lower() in text.lower():
            return entity
    # Fallback: first capitalized phrase
    caps = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
    return caps[0] if caps else "EGFR"


# ── Regex/Keyword Translator (zero dependencies) ───────

class RegexTranslator:
    """Template-based SQL translation using regex patterns."""

    def __init__(self, templates: list[dict] = None):
        self.templates = templates or TEMPLATES

    def translate(self, text: str) -> dict:
        """Return best-matching template with filled SQL."""
        text_lower = text.lower()
        best = self.templates[-1]  # Default: 'general'

        for tpl in self.templates:
            if re.search(tpl["pattern"], text_lower, re.IGNORECASE):
                best = tpl
                break

        entity = extract_entity(text)
        sql = best["sql"].format(entity=entity) if "{entity}" in best["sql"] else best["sql"]

        return {
            "intent": best["intent"],
            "sql": sql,
            "entity": entity,
            "method": "regex_template",
            "domain": best.get("domain", "general"),
            "confidence": 0.7,
            "matched_example": best["example"],
        }


# ── ML Translator (sentence-transformers) ──────────────

try:
    from sentence_transformers import SentenceTransformer, util
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class MLTranslator:
    """Embedding-based template matching for higher accuracy."""

    def __init__(self, templates: list[dict] = None, model_name: str = "all-MiniLM-L6-v2"):
        self.templates = templates or TEMPLATES
        self.model = None
        self.embeddings = None
        self.queries = [t["example"] for t in self.templates]

        if ML_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                self.embeddings = self.model.encode(self.queries, convert_to_tensor=True)
                logger.info(f"MLTranslator loaded: {model_name}")
            except Exception as e:
                logger.warning(f"ML model failed: {e}. Using regex fallback.")
                self.model = None
        else:
            logger.info("sentence-transformers not installed. Using regex fallback.")

    def translate(self, text: str) -> dict:
        if not self.model:
            return RegexTranslator(self.templates).translate(text)

        query_emb = self.model.encode(text, convert_to_tensor=True)
        scores = util.cos_sim(query_emb, self.embeddings)[0]
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score < 0.35:
            return RegexTranslator(self.templates).translate(text)

        best = self.templates[best_idx]
        entity = extract_entity(text)
        sql = best["sql"].format(entity=entity) if "{entity}" in best["sql"] else best["sql"]

        return {
            "intent": best["intent"],
            "sql": sql,
            "entity": entity,
            "method": "ml_embedding",
            "domain": best.get("domain", "general"),
            "confidence": round(best_score, 3),
            "matched_example": best["example"],
        }


# ── Master translator ──────────────────────────────────

class MasterTranslator:
    """Main entry point: ML if available, regex fallback always."""

    def __init__(self):
        self.ml = MLTranslator()
        self.regex = RegexTranslator()

    def translate(self, text: str) -> dict:
        result = self.ml.translate(text)
        if result.get("method") == "regex_template":
            result["fallback_reason"] = "ml_unavailable_or_low_confidence"
        return result


# ── Singleton ──────────────────────────────────────────

_translator: Optional[MasterTranslator] = None


def get_translator() -> MasterTranslator:
    global _translator
    if _translator is None:
        _translator = MasterTranslator()
    return _translator


def translate_to_sql(text: str) -> dict:
    """Translate natural language to SQL. Returns dict with sql, intent, method."""
    return get_translator().translate(text)
