"""VaultLens Terminal UI Cockpit: sovereign, local-first command center.

Built with Textual. Provides:
- Truth Index & Debt Load gauges
- Consolidation Queue (swipeable inbox for proposal review)
- Socratic Terminal (interactive disambiguation)
- Watchman cycle trigger

Launch: vaultlens tui
"""

import os
import sys
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, DataTable, Input, RichLog
    from textual.containers import Container, Horizontal, Vertical
    from textual.binding import Binding
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


class EpistemicDashboard(App if HAS_TEXTUAL else object):
    """The sovereign cockpit for VaultLens v1.0."""

    if HAS_TEXTUAL:
        CSS = """
        Screen {
            layout: grid;
            grid-size: 2 2;
            grid-gutter: 1;
        }
        #health_pane {
            column-span: 1;
            row-span: 1;
            border: solid green;
        }
        #queue_pane {
            column-span: 1;
            row-span: 1;
            border: solid blue;
        }
        #socratic_pane {
            column-span: 2;
            row-span: 1;
            border: solid yellow;
        }
        #metrics_bar {
            column-span: 2;
            row-span: 1;
            height: 3;
            border: solid $primary;
        }
        """

        BINDINGS = [
            Binding("a", "approve", "Approve Proposal", show=True),
            Binding("r", "reject", "Reject Proposal", show=True),
            Binding("s", "skip", "Skip / Next", show=True),
            Binding("w", "run_watchman", "Run Watchman", show=True),
            Binding("q", "quit", "Quit", show=True),
        ]

    def __init__(self, vault_db: str = ""):
        if HAS_TEXTUAL:
            super().__init__()
        self.vault_db = vault_db or os.path.expanduser(
            "~/vaultlens/sample_vault/.vaultlens/vaultlens.db"
        )
        self._queue: list[dict] = []
        self._queue_index = 0
        self._metrics = {"truth_index": 1.0, "debt_load": 0, "queue_size": 0}

    if HAS_TEXTUAL:
        def compose(self) -> ComposeResult:
            yield Header()
            yield Container(
                Static("Truth Index: --\nDebt Load: --\nContradictions: --",
                       id="health_pane"),
                Vertical(
                    Static("CONSOLIDATION QUEUE", id="queue_header"),
                    Static("No proposals loaded", id="proposal_view"),
                    id="queue_pane",
                ),
                id="top_row",
            )
            yield Container(
                RichLog(id="socratic_log", highlight=True, markup=True),
                Input(placeholder="Type response or command...", id="socratic_input"),
                id="socratic_pane",
            )
            yield Static("Press [W] Watchman  [A] Approve  [R] Reject  [Q] Quit",
                         id="metrics_bar")
            yield Footer()

        def on_mount(self) -> None:
            self._load_metrics()
            self._load_queue()
            log = self.query_one("#socratic_log", RichLog)
            log.write("[bold green]VaultLens v1.0 — Sovereign Node[/bold green]")
            log.write("Type [bold]'help'[/bold] for commands, or ask a question.")

        def action_approve(self) -> None:
            self._handle_queue_action("approved")

        def action_reject(self) -> None:
            self._handle_queue_action("rejected")

        def action_skip(self) -> None:
            self._queue_index += 1
            self._show_current_proposal()

        def action_run_watchman(self) -> None:
            log = self.query_one("#socratic_log", RichLog)
            log.write("[bold yellow]Running Night Watchman cycle...[/bold yellow]")
            try:
                from vaultlens.agents.watchman import NightWatchman
                watchman = NightWatchman(self.vault_db)
                report = watchman.run_cycle(dry_run=False)
                text = watchman.print_report(report)
                for line in text.split("\n"):
                    log.write(line)
                self._load_metrics()
            except Exception as e:
                log.write(f"[red]Watchman error: {e}[/red]")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            value = event.value.strip()
            log = self.query_one("#socratic_log", RichLog)
            log.write(f"[bold]> {value}[/bold]")

            if value.lower() in ("help", "?"):
                log.write("Commands: help, stats, watchman, ask <query>, clear")
            elif value.lower() == "stats":
                self._show_stats(log)
            elif value.lower() == "watchman":
                self.action_run_watchman()
            elif value.lower() == "clear":
                log.clear()
            elif value.lower().startswith("ask "):
                query = value[4:]
                log.write(f"[dim]Querying: {query}...[/dim]")
                try:
                    import sqlite3
                    from vaultlens.graph_store import GraphStore
                    from vaultlens.retriever import retrieve
                    conn = sqlite3.connect(self.vault_db)
                    graph = GraphStore(conn)
                    result = retrieve(conn, graph, query, max_notes=10)
                    notes = result.get("retrieved_notes", [])
                    log.write(f"[green]Found {len(notes)} notes[/green]")
                    for n in notes[:5]:
                        log.write(f"  - {n.get('title', '?')}")
                    conn.close()
                except Exception as e:
                    log.write(f"[red]Error: {e}[/red]")
            else:
                log.write(f"[dim]Unknown command. Type 'help' for options.[/dim]")

            event.input.clear()

        def _load_metrics(self) -> None:
            try:
                import sqlite3
                conn = sqlite3.connect(self.vault_db)
                total = conn.execute("SELECT COUNT(*) FROM edges WHERE resolved=1").fetchone()[0]
                high = conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE resolved=1 AND confidence>=0.7"
                ).fetchone()[0]
                contra = conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE relation='refutes' AND resolved=1"
                ).fetchone()[0]
                conn.close()

                self._metrics = {
                    "truth_index": high / max(total, 1),
                    "debt_load": 0,
                    "queue_size": len(self._queue),
                }
                pane = self.query_one("#health_pane", Static)
                pane.update(
                    f"Truth Index: {self._metrics['truth_index']:.1%}\n"
                    f"Epistemic Debt: {self._metrics['debt_load']}\n"
                    f"Contradictions: {contra}\n"
                    f"Total Edges: {total}"
                )
            except Exception:
                pass

        def _load_queue(self) -> None:
            # Scan pending proposals
            proposals_dir = os.path.join(
                os.path.dirname(self.vault_db), "..", ".vaultlens", "proposals", "pending"
            )
            if os.path.isdir(proposals_dir):
                import json
                self._queue = []
                for fname in sorted(os.listdir(proposals_dir)):
                    if fname.endswith(".json"):
                        try:
                            with open(os.path.join(proposals_dir, fname)) as f:
                                self._queue.append(json.load(f))
                        except json.JSONDecodeError:
                            pass
            self._queue_index = 0
            self._show_current_proposal()

        def _show_current_proposal(self) -> None:
            view = self.query_one("#proposal_view", Static)
            if self._queue_index < len(self._queue):
                p = self._queue[self._queue_index]
                view.update(
                    f"[{self._queue_index + 1}/{len(self._queue)}] "
                    f"{p.get('source_title', '?')} --{p.get('relation', '?')}--> "
                    f"{p.get('target_title', '?')}\n"
                    f"Variant: {p.get('variant', '?')}  "
                    f"Confidence: {p.get('confidence', 0):.2f}\n"
                    f"Rationale: {p.get('rationale', '?')[:200]}"
                )
            else:
                view.update("Queue empty — no pending proposals.")

        def _handle_queue_action(self, action: str) -> None:
            log = self.query_one("#socratic_log", RichLog)
            if self._queue_index < len(self._queue):
                p = self._queue[self._queue_index]
                log.write(f"[bold]{action.upper()}:[/bold] {p.get('source_title','?')} "
                         f"--{p.get('relation','?')}--> {p.get('target_title','?')}")
                # Remove from queue list
                self._queue.pop(self._queue_index)
            else:
                log.write("[yellow]No proposal to act on.[/yellow]")
            self._show_current_proposal()

        def _show_stats(self, log) -> None:
            try:
                import sqlite3
                conn = sqlite3.connect(self.vault_db)
                notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
                edges = conn.execute("SELECT COUNT(*) FROM edges WHERE resolved=1").fetchone()[0]
                pending = conn.execute(
                    "SELECT COUNT(*) FROM proposals WHERE status='pending'"
                ).fetchone()[0]
                conn.close()
                log.write(f"Notes: {notes}  |  Active Edges: {edges}  |  Pending Proposals: {pending}")
            except Exception:
                log.write("[red]Could not load stats[/red]")


def run_tui(vault_db: str = ""):
    """Launch the VaultLens Terminal UI."""
    if not HAS_TEXTUAL:
        print("Textual not installed. Run: pip install textual")
        print("Falling back to CLI mode.")
        return

    app = EpistemicDashboard(vault_db)
    app.run()
