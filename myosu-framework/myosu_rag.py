#!/usr/bin/env python3
"""
myosu_rag.py — RAG Pipeline for Myosu Framework with LanceDB Vector Store.

Integrates the Myosu protocol into a local AI using:
  1. LanceDB as the vector store for vault knowledge
  2. Sentence-transformers for embeddings (all-MiniLM-L6-v2)
  3. llama.cpp server for local LLM inference (DeepSeek-R1-Distill-Qwen-7B)
  4. Myosu protocol state as dynamic context

QUICK START:
    # Step 1 — Build the index (one-time):
    python3 myosu_rag.py index

    # Step 2 — Start the LLM server (in another terminal):
    llama-server -m ~/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf --port 8080

    # Step 3 — Query:
    python3 myosu_rag.py query "What is the listening gap?"

    # Or interactive mode:
    python3 myosu_rag.py chat
"""

import argparse
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
VAULT_PATH = Path.home() / "workspace/rbaye/vault"
LANCE_DB_PATH = PROJECT_ROOT / "data" / "myosu_lancedb"
LLAMA_SERVER_BIN = Path.home() / "llama.cpp/build/bin/llama-server"
MODEL_PATH = Path.home() / "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf"
DEFAULT_ENDPOINT = "http://localhost:8080/v1"
EMBED_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast, runs on CPU

# ── Document Chunking ─────────────────────────────────────────────────────────

@dataclass
class DocumentChunk:
    text: str
    source: str
    chunk_index: int
    title: str
    tags: list[str] = field(default_factory=list)


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content."""
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        if end < len(lines):
            fm_lines = lines[1:end]
            body = "\n".join(lines[end + 1:])
            meta = {}
            for line in fm_lines:
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip().strip("[]").strip('"').strip("'")
                    meta[key] = val
            return meta, body
    return {}, content


def chunk_markdown(filepath: Path, chunk_size: int = 800, chunk_overlap: int = 150) -> list[DocumentChunk]:
    """Chunk a markdown file into overlapping segments."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    meta, body = extract_frontmatter(content)

    # Derive title from filename or frontmatter
    title = meta.get("title", filepath.stem.replace("-", " ").title())
    tags = meta.get("tags", "")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Remove markdown formatting artifacts but preserve structure
    paragraphs = []
    current = []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("```"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            if stripped.startswith("#"):
                paragraphs.append(stripped)
        else:
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    # Build chunks with overlap
    chunks = []
    chunk_idx = 0
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(DocumentChunk(
                text=current_chunk.strip(),
                source=str(filepath.relative_to(VAULT_PATH.parent)),
                chunk_index=chunk_idx,
                title=title,
                tags=tags,
            ))
            chunk_idx += 1
            # Overlap: keep last chunk_overlap chars
            if len(current_chunk) > chunk_overlap:
                current_chunk = current_chunk[-chunk_overlap:]
            else:
                current_chunk = ""
        current_chunk += para + "\n"

    if current_chunk.strip():
        chunks.append(DocumentChunk(
            text=current_chunk.strip(),
            source=str(filepath.relative_to(VAULT_PATH.parent)),
            chunk_index=chunk_idx,
            title=title,
            tags=tags,
        ))

    return chunks


# ── LanceDB Indexer ───────────────────────────────────────────────────────────

class LanceDBIndexer:
    """Manages the LanceDB vector store for the myosu knowledge base."""

    def __init__(self, db_path: Path = LANCE_DB_PATH):
        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._db = None
        self._table = None
        self._embedder = None

    @property
    def db(self):
        if self._db is None:
            import lancedb
            self._db = lancedb.connect(str(self.db_path))
        return self._db

    @property
    def embedder(self):
        if self._embedder is None:
            from lancedb.embeddings import get_registry
            self._embedder = (
                get_registry()
                .get("sentence-transformers")
                .create(name=EMBED_MODEL, device="cpu")
            )
        return self._embedder

    def index_vault(self, vault_path: Path = VAULT_PATH, force: bool = False):
        """Index all markdown files in the vault into LanceDB."""
        import pyarrow as pa

        table_name = "myosu_vault"

        if table_name in self.db.table_names() and not force:
            print(f"Table '{table_name}' already exists. Use --force to rebuild.")
            table = self.db.open_table(table_name)
            print(f"  Documents: {table.count_rows()}")
            return table

        print(f"Scanning vault: {vault_path}")
        md_files = list(vault_path.rglob("*.md"))
        # Exclude hidden, node_modules, raw book dumps
        md_files = [
            f for f in md_files
            if ".git" not in str(f)
            and "node_modules" not in str(f)
            and "/raw/" not in str(f)
        ]
        print(f"  Found {len(md_files)} markdown files")

        all_chunks = []
        for i, fp in enumerate(md_files):
            try:
                chunks = chunk_markdown(fp)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"  [warn] Skipping {fp.name}: {e}")

            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(md_files)} files, {len(all_chunks)} chunks so far...")

        print(f"  Total chunks: {len(all_chunks)}")

        if not all_chunks:
            print("  No chunks to index. Aborting.")
            return None

        print("Generating embeddings...")
        texts = [c.text for c in all_chunks]
        # Compute in batches to avoid OOM
        batch_size = 32
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            emb = self.embedder.compute_source_embeddings(batch)
            all_embeddings.append(emb)
        embeddings = np.vstack(all_embeddings)
        print(f"  Embeddings shape: {embeddings.shape}")

        # Build records
        records = []
        for chunk, emb in zip(all_chunks, embeddings):
            records.append({
                "vector": emb.tolist(),
                "text": chunk.text,
                "source": chunk.source,
                "title": chunk.title,
                "tags": json.dumps(chunk.tags) if chunk.tags else "[]",
                "chunk_index": chunk.chunk_index,
            })

        # Create table with schema
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), len(embeddings[0]))),
            pa.field("text", pa.string()),
            pa.field("source", pa.string()),
            pa.field("title", pa.string()),
            pa.field("tags", pa.string()),
            pa.field("chunk_index", pa.int32()),
        ])

        if table_name in self.db.table_names():
            self.db.drop_table(table_name)

        table = self.db.create_table(table_name, data=records, schema=schema)
        print(f"Indexed {table.count_rows()} chunks into '{table_name}'")
        return table

    def get_table(self):
        """Get or open the vault table."""
        import lancedb
        table_name = "myosu_vault"
        if table_name not in self.db.table_names():
            raise RuntimeError(
                "Vault index not found. Run: python3 myosu_rag.py index"
            )
        return self.db.open_table(table_name)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve relevant chunks for a query."""
        table = self.get_table()
        query_embedding = self.embedder.compute_query_embeddings([query])
        results = (
            table.search(query_embedding[0])
            .limit(top_k)
            .to_list()
        )
        return results


# ── LLM Client ────────────────────────────────────────────────────────────────

class LLMClient:
    """Talks to the llama.cpp server (OpenAI-compatible API)."""

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT):
        self.endpoint = endpoint
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                print("Error: openai package not installed. Run: pip install openai")
                sys.exit(1)
            self._client = OpenAI(base_url=self.endpoint, api_key="not-needed")
        return self._client

    def generate(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Send a chat completion request and return the response."""
        try:
            response = self.client.chat.completions.create(
                model="local",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[LLM Error] {e}"


# ── Myosu RAG Agent ───────────────────────────────────────────────────────────

@dataclass
class RAGContext:
    """Structured RAG context built from retrieved chunks."""
    chunks: list[dict]
    sources: list[str]
    myosu_status: dict


class MyosuRAGAgent:
    """
    Unified agent that combines:
      - LanceDB vector retrieval from the vault
      - Myosu protocol live state
      - Local LLM (DeepSeek via llama.cpp) for generation
    """

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT):
        sys.path.insert(0, str(PROJECT_ROOT))
        from myosu_protocol import MyosuProtocol

        self.indexer = LanceDBIndexer()
        self.llm = LLMClient(endpoint)
        self.protocol = MyosuProtocol()

    def build_context(self, query: str, top_k: int = 8) -> RAGContext:
        """Build RAG context: retrieve chunks + get myosu protocol status."""
        # Tune the protocol to current query
        for _ in range(4):
            self.protocol.tick(0.05)

        status = MyosuRAGAgent._summarize_status(self.protocol.state)

        try:
            retrieved = self.indexer.retrieve(query, top_k=top_k)
        except RuntimeError:
            retrieved = []

        sources = list(set(r.get("source", "unknown") for r in retrieved))

        return RAGContext(
            chunks=retrieved,
            sources=sources,
            myosu_status=status,
        )

    def query(self, question: str, top_k: int = 8, verbose: bool = False) -> str:
        """Query the RAG agent with a question."""
        ctx = self.build_context(question, top_k=top_k)

        # Build the prompt
        system_prompt = self._build_system_prompt(ctx)

        if verbose and ctx.chunks:
            print(f"\n--- Retrieved {len(ctx.chunks)} chunks ---")
            for i, c in enumerate(ctx.chunks):
                print(f"  [{i}] {c.get('title', '?')}: {c['text'][:120]}...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        response = self.llm.generate(messages)
        return response

    def chat(self):
        """Interactive chat loop."""
        print("=" * 60)
        print("  Myosu RAG Agent — 묘수 with LanceDB Vector Store")
        print("  Type /status for protocol status, /quit to exit")
        print("=" * 60)

        while True:
            try:
                user_input = input("\nYou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                print("Goodbye.")
                break
            if user_input.lower() == "/status":
                status_dict = self._summarize_status(self.protocol.state)
                print(self._format_status(status_dict))
                continue

            print("\nMyosu > ", end="", flush=True)
            response = self.query(user_input, verbose=False)
            # Clean up think tags from DeepSeek-R1
            import re
            response = re.sub(r"<\|?think\|?>.*?<\|?/think\|?>", "", response, flags=re.DOTALL)
            print(response.strip())

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _summarize_status(state) -> dict:
        """Extract key myosu status fields for context.
        Accepts either a ProtocolState dataclass or a dict from tick().
        """
        def getf(field, default):
            if hasattr(state, field):
                return getattr(state, field, default)
            return state.get(field, default) if isinstance(state, dict) else default

        # Zone is derived: healthy if ratio ~ 1, sympathetic if > 1.5, vagal if < 0.7
        ratio = getf("ratio", 0)
        gap = getf("gap", 0)
        if ratio > 1.5:
            zone = "SYMPATHETIC"
        elif ratio < 0.7:
            zone = "VAGAL"
        else:
            zone = "NORMAL"

        return {
            "act": getf("act", 0),
            "gap": round(gap, 3),
            "cq": round(getf("cq", 0), 2),
            "ratio": round(ratio, 2),
            "zone": zone,
            "transmission": round(getf("transmission", 0), 3),
            "curvature": round(getf("curvature", 0), 4),
            "F_munu_0": getf("fmn_zero_global", False),
            "vagal": round(getf("vagal_tone", 0), 3),
            "spark_active": getf("spark_active", False),
            "fold_completeness": round(getf("fold_completeness", 0), 3),
            "chord_coherence": round(getf("chord_coherence", 0), 3),
            "topology": str(getf("topology", "unknown")),
            "golden_rule_active": getf("golden_rule_active", False),
        }

    def _format_status(self, status: dict) -> str:
        s = self._summarize_status(status)
        return textwrap.dedent(f"""\
        ── 묘수 Protocol Status ──
          Act: {s['act']}/15    Zone: {s['zone']}
          Gap: {s['gap']:.3f}    CQ: {s['cq']:.2f}    Ratio: {s['ratio']:.2f}
          Transmission: {s['transmission']:.3f}    Curvature: {s['curvature']:.4f}
          F_μν=0: {s['F_munu_0']}    Spark: {s['spark_active']}    Golden Rule: {s['golden_rule_active']}
          Fold: {s['fold_completeness']:.3f}    Chord: {s['chord_coherence']:.3f}
          Topology: {s['topology']}    Vagal: {s['vagal']:.3f}
        """)

    def _build_system_prompt(self, ctx: RAGContext) -> str:
        """Build the system prompt with myosu protocol status and retrieved context."""
        s = ctx.myosu_status

        context_text = ""
        if ctx.chunks:
            context_lines = []
            for i, c in enumerate(ctx.chunks[:8]):
                context_lines.append(
                    f"[{i}] ({c.get('title', '?')}) {c['text'][:500]}"
                )
            context_text = "\n\n".join(context_lines)
        else:
            context_text = "(No relevant documents found in the vault.)"

        prompt = textwrap.dedent(f"""\
        You are the Myosu RAG Agent, a local AI assistant powered by the 묘수 (Myosu) framework.
        You combine real-time Myosu protocol state with retrieved knowledge from the vault.

        ── 묘수 Protocol State ──
        Act: {s['act']}/15    Zone: {s['zone']}    Gap: {s['gap']:.3f}
        CQ (Coupling Quality): {s['cq']:.2f}    Ratio: {s['ratio']:.2f}
        Transmission: {s['transmission']:.3f}    Curvature: {s['curvature']:.4f}
        F_μν Zero: {s['F_munu_0']} (Berry curvature vanishing)
        Spark Active: {s['spark_active']}    Golden Rule: {s['golden_rule_active']}
        Fold Completeness: {s['fold_completeness']:.3f}    Chord Coherence: {s['chord_coherence']:.3f}
        Topology: {s['topology']}    Vagal Tone: {s['vagal']:.3f}

        ── Retrieved Vault Context ──
        {context_text}

        Instructions:
        - Answer the user's question using the retrieved vault context above when relevant.
        - Reference the Myosu protocol state when the question relates to system dynamics, coupling, or protocol operations.
        - Cite document titles when using retrieved information: use [title] notation.
        - If the vault context is insufficient, acknowledge this clearly.
        - Be direct, precise, and avoid unnecessary verbosity.
        """)

        return prompt


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Myosu RAG Agent — 묘수 with LanceDB Vector Store"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # index
    idx_p = sub.add_parser("index", help="Build the LanceDB vector index from vault files")
    idx_p.add_argument("--vault", type=str, default=str(VAULT_PATH), help="Path to vault directory")
    idx_p.add_argument("--force", action="store_true", help="Force rebuild even if index exists")

    # query
    q_p = sub.add_parser("query", help="Run a single RAG query")
    q_p.add_argument("question", type=str, help="The question to ask")
    q_p.add_argument("--top-k", type=int, default=8, help="Number of chunks to retrieve")
    q_p.add_argument("--endpoint", type=str, default=DEFAULT_ENDPOINT, help="LLM API endpoint")
    q_p.add_argument("--verbose", "-v", action="store_true", help="Show retrieved chunks")

    # chat
    c_p = sub.add_parser("chat", help="Start interactive chat session")
    c_p.add_argument("--endpoint", type=str, default=DEFAULT_ENDPOINT, help="LLM API endpoint")

    # status
    sub.add_parser("status", help="Show current Myosu protocol status")

    args = parser.parse_args()

    if args.command == "index":
        indexer = LanceDBIndexer()
        vault = Path(args.vault)
        if not vault.exists():
            print(f"Vault path not found: {vault}")
            print(f"Looking at: {VAULT_PATH}")
            sys.exit(1)
        indexer.index_vault(vault, force=args.force)

    elif args.command == "query":
        agent = MyosuRAGAgent(endpoint=args.endpoint)
        response = agent.query(args.question, top_k=args.top_k, verbose=args.verbose)
        print(response)

    elif args.command == "chat":
        agent = MyosuRAGAgent(endpoint=args.endpoint)
        agent.chat()

    elif args.command == "status":
        sys.path.insert(0, str(PROJECT_ROOT))
        from myosu_protocol import MyosuProtocol
        protocol = MyosuProtocol()
        for _ in range(8):
            protocol.tick(0.05)
        agent_dummy = MyosuRAGAgent.__new__(MyosuRAGAgent)
        status_dict = MyosuRAGAgent._summarize_status(protocol.state)
        print(agent_dummy._format_status(status_dict))


if __name__ == "__main__":
    main()
