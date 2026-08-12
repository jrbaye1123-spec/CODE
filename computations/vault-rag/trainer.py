"""
Vault RAG Engine — Self-Learning Training Pipeline
====================================================
Converts vault notes into training data and fine-tunes a small model
on the vault's knowledge and writing style.

Two training modes:
  1. Instruction tuning: Convert wiki/ notes into Q&A pairs
  2. Contrastive: Train the retriever to match queries to relevant notes

Continuous learning loop:
  Watch for new notes → Generate training pairs → Fine-tune → Evaluate → Repeat
"""

import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────
VAULT = Path.home() / "Desktop/backup-20260606/vault"
TRAINING_DIR = Path.home() / "gpt2_moe_1m/vault_rag/training_data"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)

# Note types that make good instruction-tuning sources
INSTRUCTION_SOURCES = {
    "wiki/concepts": "concept_explanation",
    "wiki/synthesis": "synthesis_summary",
    "wiki/claims": "claim_verification",
    "wiki/questions": "question_exploration",
    "knowledge": "personal_reference",
    "decisions": "decision_rationale",
}

# Instruction templates
INSTRUCTION_TEMPLATES = [
    "Explain the concept of {title} in detail.",
    "What is {title} and how does it relate to other ideas?",
    "Summarize the key points about {title}.",
    "What are the implications of {title}?",
    "Describe {title} and provide examples.",
    "How does {title} work?",
    "What is the significance of {title}?",
    "Break down {title} for someone unfamiliar with the topic.",
]


class VaultTrainer:
    """
    Convert vault notes to training data and manage fine-tuning.

    Usage:
        trainer = VaultTrainer()
        pairs = trainer.generate_instruction_pairs(limit=500)
        trainer.export_jsonl(pairs, "instruction_tuning.jsonl")
    """

    def __init__(self):
        self.stats = {"files_processed": 0, "pairs_generated": 0, "skipped": 0}

    # ── Content extraction ───────────────────────────────────────────

    def _extract_body(self, file_path: Path) -> str:
        """Extract body text, stripping YAML frontmatter."""
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            return ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            return parts[2] if len(parts) >= 3 else content
        return content

    def _extract_frontmatter(self, file_path: Path) -> dict:
        """Extract YAML frontmatter."""
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            return {}
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        try:
            import yaml
            fm = yaml.safe_load(parts[1])
            return fm if isinstance(fm, dict) else {}
        except Exception:
            return {}

    def _clean_body(self, body: str) -> str:
        """Clean body text for training: remove wikilinks, normalize whitespace."""
        # Convert [[wikilink|display]] → display, [[wikilink]] → wikilink
        body = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', body)
        body = re.sub(r'\[\[([^\]]+)\]\]', r'\1', body)
        # Normalize whitespace
        body = re.sub(r'\n{3,}', '\n\n', body)
        body = body.strip()
        return body

    # ── Instruction pair generation ──────────────────────────────────

    def generate_instruction_pairs(self, limit: int = 500) -> list[dict]:
        """
        Walk the vault and generate instruction-tuning pairs.

        Each pair: {instruction, response, source_file, category}

        Returns list of training pairs in conversational format.
        """
        pairs = []
        self.stats = {"files_processed": 0, "pairs_generated": 0, "skipped": 0}

        for dir_name, category in INSTRUCTION_SOURCES.items():
            dir_path = VAULT / dir_name
            if not dir_path.exists():
                continue

            for md_file in dir_path.rglob("*.md"):
                if len(pairs) >= limit:
                    break

                self.stats["files_processed"] += 1
                body = self._extract_body(md_file)
                if not body or len(body.split()) < 50:
                    self.stats["skipped"] += 1
                    continue

                fm = self._extract_frontmatter(md_file)
                title = fm.get("title", md_file.stem.replace("-", " ").replace("_", " "))
                clean_body = self._clean_body(body)

                # Generate 1-2 instruction pairs per note
                templates = random.sample(
                    INSTRUCTION_TEMPLATES,
                    min(2, len(INSTRUCTION_TEMPLATES))
                )

                for template in templates:
                    instruction = template.replace("{title}", title)
                    # Truncate response to ~1000 words for training efficiency
                    words = clean_body.split()
                    if len(words) > 1000:
                        response = " ".join(words[:1000]) + "..."
                    else:
                        response = clean_body

                    pairs.append({
                        "instruction": instruction,
                        "response": response,
                        "source_file": str(md_file.relative_to(VAULT)),
                        "category": category,
                    })
                    self.stats["pairs_generated"] += 1

        print(f"[trainer] Generated {len(pairs)} pairs from "
              f"{self.stats['files_processed']} files "
              f"({self.stats['skipped']} skipped — too short)", file=sys.stderr)
        return pairs

    # ── Retrieval training pairs ─────────────────────────────────────

    def generate_retrieval_pairs(self, limit: int = 300) -> list[dict]:
        """
        Generate training pairs for the retriever: (query, relevant_doc, irrelevant_doc).

        Uses note titles as queries and bodies as documents. Also generates
        hard negatives from notes in different categories.
        """
        pairs = []
        all_notes = []

        # Collect all notes with their embeddings potential
        for dir_name in INSTRUCTION_SOURCES:
            dir_path = VAULT / dir_name
            if not dir_path.exists():
                continue
            for md_file in dir_path.rglob("*.md"):
                body = self._extract_body(md_file)
                if not body or len(body.split()) < 50:
                    continue
                fm = self._extract_frontmatter(md_file)
                title = fm.get("title", md_file.stem.replace("-", " ").replace("_", " "))
                clean_body = self._clean_body(body)
                all_notes.append({
                    "path": str(md_file.relative_to(VAULT)),
                    "title": title,
                    "body": clean_body,
                    "category": dir_name,
                })

        if len(all_notes) < 10:
            return []

        # For each note, generate a positive pair (title → body)
        # and a hard negative (title → random other body)
        for note in all_notes[:limit]:
            # Positive: query = title, doc = body
            pos_pair = {
                "query": f"What is {note['title']}?",
                "positive_doc": note["body"][:2000],
                "positive_path": note["path"],
                "type": "positive",
            }
            pairs.append(pos_pair)

            # Hard negative: query = title, doc = body from different category
            neg_candidates = [n for n in all_notes
                             if n["category"] != note["category"]]
            if neg_candidates:
                neg = random.choice(neg_candidates)
                neg_pair = {
                    "query": f"What is {note['title']}?",
                    "positive_doc": note["body"][:2000],
                    "negative_doc": neg["body"][:2000],
                    "negative_path": neg["path"],
                    "type": "hard_negative",
                }
                pairs.append(neg_pair)

        # Shuffle
        random.shuffle(pairs)
        print(f"[trainer] Generated {len(pairs)} retrieval training pairs", file=sys.stderr)
        return pairs

    # ── Export ───────────────────────────────────────────────────────

    def export_jsonl(self, pairs: list[dict], filename: str):
        """Export training pairs as JSONL."""
        output_path = TRAINING_DIR / filename
        with open(output_path, "w") as f:
            for pair in pairs:
                f.write(json.dumps(pair) + "\n")
        print(f"[trainer] Exported {len(pairs)} pairs to {output_path}", file=sys.stderr)

    def export_chat_format(self, pairs: list[dict], filename: str,
                           system_prompt: str = None):
        """
        Export in chat-completion format for fine-tuning APIs.

        Format: {"messages": [{"role": "system", "content": "..."},
                               {"role": "user", "content": "..."},
                               {"role": "assistant", "content": "..."}]}
        """
        if system_prompt is None:
            system_prompt = (
                "You are a knowledgeable assistant with expertise in quantum cosmology, "
                "AI architecture, algorithmic trading, and philosophy. "
                "You have deep knowledge of the user's personal vault and can reference "
                "specific concepts, papers, and frameworks from it. "
                "Answer questions accurately using the vault's knowledge."
            )

        output_path = TRAINING_DIR / filename
        with open(output_path, "w") as f:
            for pair in pairs:
                chat = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": pair["instruction"]},
                        {"role": "assistant", "content": pair["response"]},
                    ]
                }
                f.write(json.dumps(chat) + "\n")
        print(f"[trainer] Exported {len(pairs)} chat-format pairs to {output_path}",
              file=sys.stderr)

    # ── Training statistics ──────────────────────────────────────────

    def vault_stats(self) -> dict:
        """Analyze the vault for training data quality."""
        stats = {
            "total_notes": 0,
            "total_words": 0,
            "by_category": {},
            "avg_words_per_note": 0,
            "notes_over_1000_words": 0,
            "notes_with_frontmatter": 0,
            "notes_with_tags": 0,
        }

        for dir_name in INSTRUCTION_SOURCES:
            dir_path = VAULT / dir_name
            if not dir_path.exists():
                continue
            count = 0
            words = 0
            for md_file in dir_path.rglob("*.md"):
                body = self._extract_body(md_file)
                if not body:
                    continue
                wc = len(body.split())
                count += 1
                words += wc
                if wc > 1000:
                    stats["notes_over_1000_words"] += 1

                fm = self._extract_frontmatter(md_file)
                if fm:
                    stats["notes_with_frontmatter"] += 1
                    if fm.get("tags"):
                        stats["notes_with_tags"] += 1

            stats["by_category"][dir_name] = {"notes": count, "words": words}
            stats["total_notes"] += count
            stats["total_words"] += words

        if stats["total_notes"] > 0:
            stats["avg_words_per_note"] = stats["total_words"] // stats["total_notes"]

        return stats


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    trainer = VaultTrainer()

    # Show vault stats
    print("=" * 60)
    print("VAULT TRAINING DATA ANALYSIS")
    print("=" * 60)
    stats = trainer.vault_stats()
    print(f"  Total notes:      {stats['total_notes']}")
    print(f"  Total words:      {stats['total_words']:,}")
    print(f"  Avg words/note:   {stats['avg_words_per_note']}")
    print(f"  Notes >1000 words: {stats['notes_over_1000_words']}")
    print(f"  With frontmatter: {stats['notes_with_frontmatter']}")
    print(f"  With tags:        {stats['notes_with_tags']}")
    print(f"\n  By category:")
    for cat, s in sorted(stats["by_category"].items()):
        print(f"    {cat:25s} {s['notes']:4d} notes  {s['words']:8,d} words")

    # Generate instruction pairs
    print(f"\n{'=' * 60}")
    print("GENERATING INSTRUCTION PAIRS")
    print(f"{'=' * 60}")
    pairs = trainer.generate_instruction_pairs(limit=500)
    trainer.export_jsonl(pairs, "instruction_tuning.jsonl")
    trainer.export_chat_format(pairs, "chat_tuning.jsonl")

    # Generate retrieval pairs
    print(f"\n{'=' * 60}")
    print("GENERATING RETRIEVAL PAIRS")
    print(f"{'=' * 60}")
    retrieval_pairs = trainer.generate_retrieval_pairs(limit=200)
    trainer.export_jsonl(retrieval_pairs, "retrieval_training.jsonl")
