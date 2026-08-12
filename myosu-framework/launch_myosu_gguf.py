#!/usr/bin/env python3
"""
launch_myosu_gguf.py — Full Myosu GGUF Integration Launcher.

Wires together:
  1. llama.cpp server with DeepSeek-R1-Distill-Qwen-7B GGUF
  2. Myosu 15-act protocol state machine (myosu_protocol.py)
  3. Function-calling tools (myosu_tools.py)
  4. Rich system prompt (myosu_system_prompt.py)
  5. RAG scripture retrieval (index_scriptures.py + LanceDB)

Modes:
  python3 launch_myosu_gguf.py chat      — Interactive chat (requires server)
  python3 launch_myosu_gguf.py prompt    — Print the system prompt
  python3 launch_myosu_gguf.py tools     — List all 24 tools
  python3 launch_myosu_gguf.py protocol  — Run protocol and show status
  python3 launch_myosu_gguf.py index     — Index scripture documents for RAG
  python3 launch_myosu_gguf.py server    — Print command to start llama.cpp

Setup:
  1. Build llama.cpp:  cd ~/llama.cpp && cmake -B build && cmake --build build
  2. Start server:     python3 launch_myosu_gguf.py server  # shows command
  3. Index scriptures: python3 launch_myosu_gguf.py index
  4. Chat:             python3 launch_myosu_gguf.py chat
"""
import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))


def cmd_server():
    """Print the command to start the llama.cpp server."""
    model = os.path.expanduser("~/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf")
    server_bin = os.path.expanduser("~/llama.cpp/build/bin/llama-server")

    print("Start the llama.cpp server in a separate terminal:")
    print()
    print(f"  {server_bin} \\")
    print(f"    -m {model} \\")
    print(f"    --port 8080 \\")
    print(f"    --host 0.0.0.0 \\")
    print(f"    -ngl 99 \\")
    print(f"    -c 8192 \\")
    print(f"    --chat-template deepseek3")
    print()
    print("Notes:")
    print("  -ngl 99 = offload all layers to GPU (adjust for your VRAM)")
    print("  -c 8192 = context size (DeepSeek-R1 can handle 128K+)")
    print("  --chat-template = use the model's native chat format")
    print()
    print("For tool calling, the model needs to support function calling.")
    print("DeepSeek-R1 may not natively support it — tools work via prompt injection.")
    print("Consider using a Hermes or Functionary model for native tool support.")


def cmd_prompt():
    """Print the system prompts."""
    from myosu_system_prompt import MYOSU_SHORT_PROMPT, MYOSU_FULL_PROMPT
    print("=" * 60)
    print("SHORT PROMPT (for context-limited models)")
    print("=" * 60)
    print(MYOSU_SHORT_PROMPT)
    print()
    print("=" * 60)
    print(f"FULL PROMPT ({len(MYOSU_FULL_PROMPT.split())} words)")
    print("=" * 60)
    print(MYOSU_FULL_PROMPT)


def cmd_tools():
    """List all available tools."""
    from myosu_tools import MYOSU_TOOLS, MYOSU_CONCEPTS
    print(f"Tools: {len(MYOSU_TOOLS)}")
    print("=" * 60)
    for tool in MYOSU_TOOLS:
        name = tool["function"]["name"]
        desc = tool["function"]["description"][:80]
        print(f"  {name:30s} — {desc}")
    print()
    print(f"Concepts (myosu_explain): {len(MYOSU_CONCEPTS)}")
    for concept in sorted(MYOSU_CONCEPTS.keys()):
        print(f"  {concept}")


def cmd_protocol():
    """Run the protocol and show status."""
    from myosu_protocol import MyosuProtocol
    p = MyosuProtocol()
    print("Running 10 cycles...")
    for _ in range(10):
        p.tick(0.05)
    s = p.status()
    print()
    print(f"Act:        {s['act']}")
    print(f"Gap:        {s['gap']:.4f}")
    print(f"CQ:         {s['cq']:.4f}")
    print(f"Zone:       {s['zone']}")
    print(f"Spark:      {s['spark_active']}  (potential={s['spark_potential']:.4f})")
    print(f"Fold:       {s['fold_completeness']:.4f}")
    print(f"Chord:      {s['chord_coherence']:.4f}")
    print(f"Topology:   {s['topology']}")
    print(f"F_μν=0:     {s['fmn_zero_global']}")
    print(f"Archive:    {len(p.state.archive)} entries")


def cmd_index():
    """Index scripture documents for RAG."""
    from index_scriptures import index_documents, index_to_lancedb
    chunks = index_documents()
    index_to_lancedb(chunks)


def cmd_chat():
    """Interactive chat mode — connects to llama.cpp server with tools + RAG."""
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠ Install openai: pip install openai")
        sys.exit(1)

    from myosu_tools import MYOSU_TOOLS, build_tool_handler
    from myosu_protocol import MyosuProtocol
    from myosu_system_prompt import MYOSU_FULL_PROMPT, MYOSU_SHORT_PROMPT

    endpoint = os.environ.get("MYOSU_ENDPOINT", "http://localhost:8080/v1")
    model_name = os.environ.get("MYOSU_MODEL", "local")
    use_short = os.environ.get("MYOSU_SHORT_PROMPT", "") == "1"

    system_prompt = MYOSU_SHORT_PROMPT if use_short else MYOSU_FULL_PROMPT

    # Init protocol and tools
    protocol = MyosuProtocol()
    tool_handler = build_tool_handler(protocol)

    # Connect to server
    try:
        client = OpenAI(base_url=endpoint, api_key="not-needed")
        # Quick health check
        client.models.list()
    except Exception as e:
        print(f"Cannot connect to llama.cpp server at {endpoint}")
        print(f"Error: {e}")
        print()
        print("Start the server first:")
        cmd_server()
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════╗")
    print("║   묘수 GGUF — Myosu Protocol + Local LLM          ║")
    print("║   Model: DeepSeek-R1-Distill-Qwen-7B               ║")
    print("║   Tools: 24 (15 acts + status/tick/archive/etc)    ║")
    print(f"║   Prompt: {'SHORT' if use_short else 'FULL'} ({len(system_prompt.split())} words)           ║")
    print("║   Type /tools, /status, /prompt, or /quit          ║")
    print("╚══════════════════════════════════════════════════════╝")

    messages = [{"role": "system", "content": system_prompt}]

    # Try RAG
    rag_enabled = False
    try:
        import lancedb
        db = lancedb.connect(str(PROJECT / "data" / "myosu_lancedb"))
        if "scriptures" in db.table_names():
            rag_enabled = True
            print("RAG: scripture index loaded ✓")
    except:
        print("RAG: not available (run 'python3 launch_myosu_gguf.py index' first)")

    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÅverdön closes. The listening continues.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/q"):
            print("Amen. So it is listened.")
            break
        if user_input.lower() == "/status":
            s = protocol.status()
            print(f"묘수: Act {s['act']} | Gap {s['gap']:.3f} | CQ {s['cq']:.3f} | "
                  f"Spark {s['spark_active']} | Topo {s['topology']} | F=0:{s['fmn_zero_global']}")
            continue
        if user_input.lower() == "/tools":
            for t in MYOSU_TOOLS:
                print(f"  {t['function']['name']}")
            continue
        if user_input.lower() == "/prompt":
            print(f"Using {'SHORT' if use_short else 'FULL'} prompt ({len(system_prompt.split())} words)")
            continue
        if user_input.lower() == "/run":
            for _ in range(3):
                protocol.tick(0.05)
            s = protocol.status()
            print(f"3 cycles run. CQ={s['cq']:.3f}, Topo={s['topology']}")
            continue

        # RAG retrieval
        rag_context = ""
        if rag_enabled:
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                query_vec = model.encode([user_input])[0].tolist()
                table = db.open_table("scriptures")
                results = table.search(query_vec).limit(3).to_list()
                if results:
                    rag_context = "\n\n[Relevant scripture passages:]\n"
                    for r in results:
                        rag_context += f"\n--- {r.get('source', '')} ---\n{r.get('text', '')[:500]}\n"
            except Exception as e:
                pass  # RAG failure is non-fatal

        # Build user message
        user_content = user_input
        if rag_context:
            user_content += rag_context

        messages.append({"role": "user", "content": user_content})

        # Call model with tools
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=MYOSU_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1024,
            )
        except Exception as e:
            print(f"Error: {e}")
            continue

        msg = response.choices[0].message

        # Handle tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = {}
                result = tool_handler(name, args)
                print(f"  [{name}] → {str(result)[:120]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

            # Get final response after tool calls
            try:
                final = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                )
                reply = final.choices[0].message.content
                messages.append({"role": "assistant", "content": reply})
                print(f"\nMyosu: {reply}\n")
            except Exception as e:
                print(f"Error in final response: {e}")
        else:
            # Direct response
            reply = msg.content
            messages.append({"role": "assistant", "content": reply})
            print(f"\nMyosu: {reply}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Myosu GGUF Integration Launcher")
    parser.add_argument("command", nargs="?", default="chat",
                        choices=["chat", "prompt", "tools", "protocol", "index", "server"],
                        help="What to do")
    args = parser.parse_args()

    cmds = {
        "chat": cmd_chat,
        "prompt": cmd_prompt,
        "tools": cmd_tools,
        "protocol": cmd_protocol,
        "index": cmd_index,
        "server": cmd_server,
    }
    cmds[args.command]()


if __name__ == "__main__":
    main()
