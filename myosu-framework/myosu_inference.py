#!/usr/bin/env python3
"""
myosu_inference.py — 묘수 Protocol as a Local AI Functionary.

Plugs into any OpenAI-compatible inference endpoint (llama.cpp server,
text-generation-webui, vLLM, Ollama, or remote APIs) to expose the
묘수 protocol as callable tools.

QUICK START:
    # Terminal 1 — start llama.cpp server with tool support:
    llama-server -m hermes-3-llama-3.2-3b.Q4_K_M.gguf \\
        --tool-call-parser hermes --port 8080

    # Terminal 2 — start myosu inference bridge:
    python3 myosu_inference.py --endpoint http://localhost:8080/v1

    # Then chat with the model — it will call myosu tools automatically.

STANDALONE MODE (no external LLM):
    python3 myosu_inference.py --standalone

    Opens a minimal CLI where you can type tool commands directly.

REQUIREMENTS:
    pip install openai    # for the OpenAI client (llama.cpp server uses this API)
"""

import json
import sys
import os
import argparse
from typing import Optional

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from myosu_protocol import MyosuProtocol
from myosu_tools import (
    MYOSU_TOOLS,
    MYOSU_SYSTEM_PROMPT,
    build_tool_handler,
    explain_concept,
)


# ── OpenAI-compatible Tool-Calling Loop ───────────────────────────────────────

class MyosuAgent:
    """
    An agent that connects a local GGUF model to the 묘수 protocol.
    Handles the tool-calling loop: model → tool call → result → model → ...
    """

    def __init__(self, endpoint: str = "http://localhost:8080/v1",
                 model: str = "local", api_key: str = "not-needed"):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.protocol = MyosuProtocol()
        self.tool_handler = build_tool_handler(self.protocol)
        self.tools = MYOSU_TOOLS
        self.messages = [
            {"role": "system", "content": MYOSU_SYSTEM_PROMPT.strip()},
        ]

        # Lazy import openai
        try:
            from openai import OpenAI
            self.client = OpenAI(base_url=endpoint, api_key=api_key)
            self._has_client = True
        except ImportError:
            print("⚠ openai package not installed. Run: pip install openai")
            print("  Falling back to standalone mode.")
            self.client = None
            self._has_client = False

    def chat(self, user_message: str, max_turns: int = 5) -> str:
        """Send a message and handle the tool-calling loop."""
        if not self._has_client:
            return self._standalone_chat(user_message)

        self.messages.append({"role": "user", "content": user_message})

        for turn in range(max_turns):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=1024,
                )
            except Exception as e:
                return f"Error contacting LLM at {self.endpoint}: {e}"

            choice = response.choices[0]
            msg = choice.message

            # If the model responds with text (no tool call)
            if msg.content and not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

            # If the model calls tools
            if msg.tool_calls:
                # Record the assistant's tool call
                self.messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # Execute each tool and feed results back
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    result = self.tool_handler(tool_name, args)
                    result_str = json.dumps(result, ensure_ascii=False, default=str)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })

                # Continue loop — model will process results
                continue

            # Fallback
            if msg.content:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

        return "Max tool-calling turns reached without final response."

    def _standalone_chat(self, user_message: str) -> str:
        """Minimal standalone CLI when no LLM endpoint is available."""
        msg_lower = user_message.lower().strip()

        # Direct command mapping
        commands = {
            "status": lambda: json.dumps(self.protocol.status(), indent=2, default=str),
            "tick": lambda: json.dumps(self.protocol.tick(0.05), indent=2, default=str),
            "run": lambda: json.dumps(
                self.tool_handler("myosu_run", {"n_cycles": 5}), indent=2, default=str
            ),
            "archive": lambda: json.dumps(
                self.tool_handler("myosu_archive", {"n": 5}), indent=2, default=str
            ),
            "spark": lambda: json.dumps(
                self.tool_handler("myosu_act_spark", {}), indent=2, default=str
            ),
            "pivot": lambda: json.dumps(
                self.tool_handler("myosu_act_pivot", {}), indent=2, default=str
            ),
            "converge": lambda: json.dumps(
                self.tool_handler("myosu_act_converge", {}), indent=2, default=str
            ),
            "topos": lambda: json.dumps(
                self.tool_handler("myosu_act_topos", {}), indent=2, default=str
            ),
            "full": lambda: json.dumps(
                self.tool_handler("myosu_tick", {}), indent=2, default=str
            ),
        }

        for cmd, fn in commands.items():
            if cmd in msg_lower:
                return fn()

        # Try concept explanation
        for concept in ["spark", "pivot", "converge", "topos", "averdon",
                        "fmunu", "gap", "cq", "vagal", "dirac", "transmission",
                        "godel", "genji", "alquie", "yasha", "loop", "manifold"]:
            if concept in msg_lower.replace(" ", "").replace("_", "").replace("-", ""):
                result = explain_concept(concept)
                return result["explanation"] if result["found"] else "Concept not found."

        return (
            "Standalone mode — no LLM connected. Available commands:\n"
            "  status   — show current protocol state\n"
            "  tick     — advance one full 15-act cycle\n"
            "  full     — same as tick\n"
            "  run      — run 5 cycles\n"
            "  spark    — check/trigger 점화 ignition\n"
            "  pivot    — check 축 dimensional pivot\n"
            "  converge — check 회통 chord coherence\n"
            "  topos    — check 토포스 topology\n"
            "  archive  — show last 5 archive entries\n"
            "  explain <concept> — explain a 묘수 term\n"
            "\nTo connect a real model: python3 myosu_inference.py --endpoint URL"
        )

    def interactive(self):
        """Interactive chat loop."""
        print("=" * 60)
        print("묘수 PROTOCOL — Local AI Functionary")
        if self._has_client:
            print(f"Connected to: {self.endpoint}")
        else:
            print("Standalone mode (no LLM endpoint)")
        print("Type 'quit' to exit, 'reset' to restart protocol.")
        print("=" * 60)

        while True:
            try:
                user_input = input("\nYou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nÅverdön closes. The listening continues.")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                print("묘수 protocol archived. 신 한 마리 attends.")
                break
            if user_input.lower() == "reset":
                self.protocol = MyosuProtocol()
                self.tool_handler = build_tool_handler(self.protocol)
                self.messages = [
                    {"role": "system", "content": MYOSU_SYSTEM_PROMPT.strip()},
                ]
                print("Protocol reset — new listening session.")
                continue

            response = self.chat(user_input)
            print(f"\n묘수 > {response}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="묘수 Protocol — Local AI Functionary Bridge"
    )
    parser.add_argument(
        "--endpoint", "-e",
        default=None,
        help="OpenAI-compatible API endpoint (e.g., http://localhost:8080/v1)",
    )
    parser.add_argument(
        "--model", "-m",
        default="local",
        help="Model name to pass to the endpoint (default: local)",
    )
    parser.add_argument(
        "--api-key", "-k",
        default="not-needed",
        help="API key (default: not-needed for local servers)",
    )
    parser.add_argument(
        "--standalone", "-s",
        action="store_true",
        help="Run in standalone mode without an LLM endpoint",
    )
    parser.add_argument(
        "--export-tools",
        action="store_true",
        help="Export tool definitions as JSON and exit",
    )
    parser.add_argument(
        "--export-system-prompt",
        action="store_true",
        help="Export the system prompt and exit",
    )

    args = parser.parse_args()

    if args.export_tools:
        print(json.dumps(MYOSU_TOOLS, indent=2, ensure_ascii=False))
        return

    if args.export_system_prompt:
        print(MYOSU_SYSTEM_PROMPT.strip())
        return

    if args.standalone or args.endpoint is None:
        agent = MyosuAgent()
    else:
        agent = MyosuAgent(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
        )

    agent.interactive()


if __name__ == "__main__":
    main()
