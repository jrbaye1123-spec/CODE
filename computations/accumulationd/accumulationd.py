#!/usr/bin/env python3
"""
accumulationd — a zeroconf daemon for solution manifolds.

Architecture (mirrors avahi-daemon):
  - Listener:  accepts (instance, solution) submissions via UNIX socket
  - Cache:     maintains Fisher metric over accumulated corpus in memory
  - Query API: answers geodesic interpolation queries

Version 0.1.0 — 2-SAT only. Toy scale. No P=NP claims.
"""

import argparse
import json
import os
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ── Protocol constants ──────────────────────────────────────────────
SOCKET_PATH = "/tmp/accumulationd.sock"
HEADER_FMT = "!I"  # 4-byte length prefix
MAX_MSG = 2**20     # 1 MB max message

# ── Data structures ──────────────────────────────────────────────────

@dataclass
class TwoSATInstance:
    """A 2-SAT instance: n variables, list of (literal, literal) clauses.
    Literals: 1..n for positive, -(1..n) for negative."""
    n_vars: int
    clauses: list  # list of (int, int) tuples

    def to_dict(self):
        return {"n_vars": self.n_vars, "clauses": self.clauses}

    @classmethod
    def from_dict(cls, d):
        return cls(n_vars=d["n_vars"], clauses=[tuple(c) for c in d["clauses"]])

    @classmethod
    def random(cls, n_vars, n_clauses, seed=None):
        """Generate a random 2-SAT instance."""
        rng = np.random.RandomState(seed)
        clauses = []
        for _ in range(n_clauses):
            a = rng.randint(1, n_vars + 1) * (1 if rng.rand() > 0.5 else -1)
            b = rng.randint(1, n_vars + 1) * (1 if rng.rand() > 0.5 else -1)
            while b == a or b == -a:  # avoid tautologies and contradictions
                b = rng.randint(1, n_vars + 1) * (1 if rng.rand() > 0.5 else -1)
            clauses.append((a, b))
        return cls(n_vars=n_vars, clauses=clauses)


@dataclass
class CorpusEntry:
    """One accumulated (instance, solution) pair."""
    instance: TwoSATInstance
    solution: list  # list of +/-1 for each variable
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"


@dataclass
class FisherCache:
    """Maintains the Fisher Information Metric over the accumulated corpus.

    For 2-SAT, the "Fisher metric" is simplified: we compute the covariance
    matrix of solution vectors and use its inverse as the metric for geodesic
    interpolation. The Connes distance between two instances is computed from
    their clause-overlap embedding.
    """
    entries: list = field(default_factory=list)
    solution_matrix: np.ndarray = None       # N x n_vars
    covariance: np.ndarray = None             # n_vars x n_vars
    covariance_inv: np.ndarray = None         # for geodesic steps
    alpha: float = None                       # FIM spectral exponent
    _dirty: bool = True

    def add(self, entry: CorpusEntry):
        self.entries.append(entry)
        self._dirty = True

    def _update(self):
        if not self._dirty or len(self.entries) < 2:
            return
        n = len(self.entries)
        d = self.entries[0].instance.n_vars
        self.solution_matrix = np.array([e.solution for e in self.entries])
        self.covariance = (self.solution_matrix.T @ self.solution_matrix) / n
        # Ridge-stabilized inverse
        ridge = 1e-6 * np.eye(d)
        try:
            self.covariance_inv = np.linalg.inv(self.covariance + ridge)
        except np.linalg.LinAlgError:
            self.covariance_inv = np.linalg.pinv(self.covariance + ridge)
        # Compute spectral exponent alpha
        eigs = np.linalg.eigvalsh(self.covariance)
        eigs = np.sort(eigs)[::-1]
        eigs = eigs[eigs > 1e-12]
        if len(eigs) >= 3:
            x = np.log(np.arange(1, len(eigs) + 1))
            y = np.log(np.maximum(eigs, 1e-15))
            # Fit only top 70% of eigenvalues
            n_fit = max(3, int(len(eigs) * 0.7))
            slope, _ = np.polyfit(x[:n_fit], y[:n_fit], 1)
            self.alpha = float(-slope)
        self._dirty = False

    @property
    def size(self):
        return len(self.entries)

    @property
    def is_ready(self):
        return len(self.entries) >= 2


# ── Solver (2-SAT via implication graph) ─────────────────────────────

def solve_2sat(instance: TwoSATInstance):
    """Solve 2-SAT using SCC on the implication graph. Returns solution or None."""
    n = instance.n_vars
    # Build implication graph: 2n nodes, 0..n-1 for +x, n..2n-1 for -x
    adj = [[] for _ in range(2 * n)]
    adj_rev = [[] for _ in range(2 * n)]

    def var_to_node(lit):
        return (abs(lit) - 1) + (0 if lit > 0 else n)

    def node_to_var(node):
        return (node % n) + 1

    for a, b in instance.clauses:
        # (a ∨ b) ≡ (¬a → b) ∧ (¬b → a)
        na = var_to_node(-a)
        nb_pos = var_to_node(b)
        adj[na].append(nb_pos)
        adj_rev[nb_pos].append(na)

        nb = var_to_node(-b)
        na_pos = var_to_node(a)
        adj[nb].append(na_pos)
        adj_rev[na_pos].append(nb)

    # Kosaraju SCC
    visited = [False] * (2 * n)
    order = []

    def dfs1(u):
        visited[u] = True
        for v in adj[u]:
            if not visited[v]:
                dfs1(v)
        order.append(u)

    for i in range(2 * n):
        if not visited[i]:
            dfs1(i)

    comp = [-1] * (2 * n)
    current = 0

    def dfs2(u):
        comp[u] = current
        for v in adj_rev[u]:
            if comp[v] == -1:
                dfs2(v)

    for u in reversed(order):
        if comp[u] == -1:
            dfs2(u)
            current += 1

    # Check satisfiability
    solution = [0] * n
    for i in range(n):
        if comp[i] == comp[i + n]:
            return None  # UNSAT
        solution[i] = 1 if comp[i] > comp[i + n] else -1

    return solution


# ── Geodesic solver (simplified: nearest-neighbor interpolation) ─────

def geodesic_query(cache: FisherCache, instance: TwoSATInstance, max_steps=100):
    """Find a solution by interpolating from the nearest corpus entry.

    Strategy: find the nearest corpus entry, then use the 2-SAT implication
    graph to propagate forced assignments. Only flip variables when implication
    propagation gets stuck.
    """
    cache._update()
    if not cache.is_ready:
        return None, {"error": "cache too small", "corpus_size": cache.size}

    n = instance.n_vars

    # Build implication graph for quick propagation
    adj = [[] for _ in range(2 * n)]

    def _var_to_node(lit):
        return (abs(lit) - 1) + (0 if lit > 0 else n)

    for a, b in instance.clauses:
        adj[_var_to_node(-a)].append(_var_to_node(b))
        adj[_var_to_node(-b)].append(_var_to_node(a))

    # Compute clause overlap embedding for the query instance
    query_vec = np.zeros(n)
    for a, b in instance.clauses:
        query_vec[abs(a) - 1] += 1
        query_vec[abs(b) - 1] += 1

    # Find nearest corpus entry
    best_dist = float("inf")
    best_solution = None
    best_idx = -1

    for i, entry in enumerate(cache.entries):
        if entry.instance.n_vars != n:
            continue
        corpus_vec = np.zeros(n)
        for a, b in entry.instance.clauses:
            corpus_vec[abs(a) - 1] += 1
            corpus_vec[abs(b) - 1] += 1
        qn = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        cn = corpus_vec / (np.linalg.norm(corpus_vec) + 1e-10)
        dist = 2 * np.sqrt(1 - abs(np.dot(qn, cn)))
        if dist < best_dist:
            best_dist = dist
            best_solution = list(entry.solution)
            best_idx = i

    if best_solution is None:
        return None, {"error": "no compatible corpus entry"}

    # Propagate forced assignments from the instance
    candidate = list(best_solution)
    assigned = [False] * n

    def _node_val(node):
        var = node % n
        return candidate[var] if node < n else -candidate[var]

    def propagate():
        """Propagate: if a clause (¬a → b) has ¬a true but b unassigned, force b true."""
        changed = True
        while changed:
            changed = False
            for a, b in instance.clauses:
                va = candidate[abs(a) - 1] if a > 0 else -candidate[abs(a) - 1]
                vb = candidate[abs(b) - 1] if b > 0 else -candidate[abs(b) - 1]
                # clause a ∨ b: if a is false, b must be true
                if va < 0 and vb >= 0:
                    pass  # b already true or unassigned, need to check implication
                if va <= 0 and vb <= 0 and va < 0:
                    # a is false, force b true
                    target_var = abs(b) - 1
                    target_val = 1 if b > 0 else -1
                    if candidate[target_var] != target_val:
                        candidate[target_var] = target_val
                        changed = True
                if vb < 0 and va <= 0:
                    target_var = abs(a) - 1
                    target_val = 1 if a > 0 else -1
                    if candidate[target_var] != target_val:
                        candidate[target_var] = target_val
                        changed = True

    for step in range(max_steps):
        propagate()

        # Check all clauses
        violated = []
        for a, b in instance.clauses:
            va = candidate[abs(a) - 1] if a > 0 else -candidate[abs(a) - 1]
            vb = candidate[abs(b) - 1] if b > 0 else -candidate[abs(b) - 1]
            if va < 0 and vb < 0:
                violated.append((a, b))

        if not violated:
            return candidate, {
                "method": "geodesic_interpolation",
                "nearest_idx": best_idx,
                "connes_distance": float(best_dist),
                "adaptation_steps": step,
                "corpus_size": cache.size,
                "alpha": cache.alpha,
            }

        # Flip the variable in the first violated clause that appears least
        a, b = violated[0]
        va_count = sum(1 for c in instance.clauses
                       if abs(c[0]) == abs(a) or abs(c[1]) == abs(a))
        vb_count = sum(1 for c in instance.clauses
                       if abs(c[0]) == abs(b) or abs(c[1]) == abs(b))
        flip_var = abs(a) if va_count <= vb_count else abs(b)
        candidate[flip_var - 1] *= -1

    return None, {
        "error": "max adaptation steps exceeded",
        "steps": max_steps,
        "corpus_size": cache.size,
        "alpha": cache.alpha,
    }


# ── Server ────────────────────────────────────────────────────────────

class AccumulationDaemon:
    """The daemon: listener thread + cache + query handler."""

    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path
        self.cache = FisherCache()
        self.running = False
        self.stats = {
            "submissions": 0,
            "queries": 0,
            "successful_queries": 0,
            "start_time": time.time(),
        }

    # ── Message protocol ──────────────────────────────────────────

    def _recv_msg(self, conn):
        """Receive a length-prefixed JSON message."""
        header = conn.recv(4)
        if len(header) < 4:
            return None
        length = struct.unpack(HEADER_FMT, header)[0]
        if length > MAX_MSG:
            return None
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return json.loads(data.decode("utf-8"))

    def _send_msg(self, conn, msg):
        """Send a length-prefixed JSON response."""
        data = json.dumps(msg).encode("utf-8")
        conn.sendall(struct.pack(HEADER_FMT, len(data)) + data)

    # ── Handlers ──────────────────────────────────────────────────

    def handle_submit(self, msg):
        """Handle a SUBMIT request: add (instance, solution) to cache."""
        try:
            inst = TwoSATInstance.from_dict(msg["instance"])
            solution = msg["solution"]
            source = msg.get("source", "unknown")
            entry = CorpusEntry(instance=inst, solution=solution, source=source)
            self.cache.add(entry)
            self.stats["submissions"] += 1
            return {
                "status": "ok",
                "corpus_size": self.cache.size,
                "alpha": self.cache.alpha,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def handle_solve(self, msg):
        """Handle a SOLVE request: solve a 2-SAT instance directly."""
        try:
            inst = TwoSATInstance.from_dict(msg["instance"])
            solution = solve_2sat(inst)
            if solution is not None:
                # Auto-submit to cache
                entry = CorpusEntry(instance=inst, solution=solution,
                                    source="accumulationd-solver")
                self.cache.add(entry)
                self.stats["submissions"] += 1
                self.stats["successful_queries"] += 1
            self.stats["queries"] += 1
            return {
                "status": "ok",
                "solution": solution,
                "satisfiable": solution is not None,
                "corpus_size": self.cache.size,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def handle_query(self, msg):
        """Handle a QUERY request: geodesic interpolation from corpus."""
        self.stats["queries"] += 1
        try:
            inst = TwoSATInstance.from_dict(msg["instance"])
            max_steps = msg.get("max_steps", 100)
            solution, meta = geodesic_query(self.cache, inst, max_steps)
            if solution is not None:
                self.stats["successful_queries"] += 1
            return {
                "status": "ok",
                "solution": solution,
                "satisfiable": solution is not None,
                "meta": meta,
                "corpus_size": self.cache.size,
                "alpha": self.cache.alpha,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def handle_status(self, msg):
        """Handle a STATUS request: daemon statistics."""
        uptime = time.time() - self.stats["start_time"]
        cache_hit_rate = (
            self.stats["successful_queries"] / max(self.stats["queries"], 1)
        )
        return {
            "status": "ok",
            "uptime_seconds": uptime,
            "corpus_size": self.cache.size,
            "alpha": self.cache.alpha,
            "submissions": self.stats["submissions"],
            "queries": self.stats["queries"],
            "successful_queries": self.stats["successful_queries"],
            "cache_hit_rate": cache_hit_rate,
            "version": "0.1.0",
        }

    # ── Main loop ─────────────────────────────────────────────────

    def handle_connection(self, conn):
        """Handle one client connection."""
        try:
            msg = self._recv_msg(conn)
            if msg is None:
                return

            cmd = msg.get("command", "status")
            handlers = {
                "submit": self.handle_submit,
                "solve": self.handle_solve,
                "query": self.handle_query,
                "status": self.handle_status,
            }
            handler = handlers.get(cmd, self.handle_status)
            response = handler(msg)
            self._send_msg(conn, response)
        except Exception as e:
            try:
                self._send_msg(conn, {"status": "error", "error": str(e)})
            except Exception:
                pass
        finally:
            conn.close()

    def run(self):
        """Start the daemon. Blocks until SIGTERM/SIGINT."""
        # Clean up stale socket
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(5)
        os.chmod(self.socket_path, 0o666)
        self.running = True

        print(f"accumulationd v0.1.0 running on {self.socket_path}")
        print(f"  corpus: {self.cache.size} entries")
        print(f"  ready for SUBMIT / SOLVE / QUERY / STATUS")

        try:
            while self.running:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_connection,
                                 args=(conn,), daemon=True).start()
        except KeyboardInterrupt:
            print("\nshutting down...")
        finally:
            server.close()
            os.unlink(self.socket_path)
            print("accumulationd stopped")


# ── CLI client ───────────────────────────────────────────────────────

def send_command(cmd_dict, socket_path=SOCKET_PATH):
    """Send a command to the daemon and return the response."""
    data = json.dumps(cmd_dict).encode("utf-8")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(socket_path)
        sock.sendall(struct.pack(HEADER_FMT, len(data)) + data)
        # Receive response
        header = sock.recv(4)
        if len(header) < 4:
            return {"status": "error", "error": "no response"}
        length = struct.unpack(HEADER_FMT, header)[0]
        resp = b""
        while len(resp) < length:
            chunk = sock.recv(length - len(resp))
            if not chunk:
                break
            resp += chunk
        return json.loads(resp.decode("utf-8"))
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="accumulationd — solution manifold daemon")
    sub = parser.add_subparsers(dest="mode")

    # Server mode
    sub.add_parser("serve", help="start the daemon")

    # Status
    sub.add_parser("status", help="query daemon status")

    # Submit: submit a solved instance
    submit_p = sub.add_parser("submit", help="submit a solved instance")
    submit_p.add_argument("--n-vars", type=int, default=5)
    submit_p.add_argument("--n-clauses", type=int, default=10)
    submit_p.add_argument("--seed", type=int)

    # Solve: direct 2-SAT solve
    solve_p = sub.add_parser("solve", help="solve a 2-SAT instance")
    solve_p.add_argument("--n-vars", type=int, default=5)
    solve_p.add_argument("--n-clauses", type=int, default=10)
    solve_p.add_argument("--seed", type=int)
    solve_p.add_argument("--max-steps", type=int, default=100)

    # Query: geodesic interpolation
    query_p = sub.add_parser("query", help="geodesic interpolation query")
    query_p.add_argument("--n-vars", type=int, default=5)
    query_p.add_argument("--n-clauses", type=int, default=10)
    query_p.add_argument("--seed", type=int)
    query_p.add_argument("--max-steps", type=int, default=100)

    # Populate: seed the cache with random solved instances
    populate_p = sub.add_parser("populate", help="populate cache with random instances")
    populate_p.add_argument("--n-vars", type=int, default=5)
    populate_p.add_argument("--n-clauses", type=int, default=10)
    populate_p.add_argument("--count", type=int, default=50)
    populate_p.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    if args.mode == "serve":
        daemon = AccumulationDaemon()
        daemon.run()

    elif args.mode == "status":
        resp = send_command({"command": "status"})
        print(json.dumps(resp, indent=2))

    elif args.mode == "submit":
        inst = TwoSATInstance.random(args.n_vars, args.n_clauses, args.seed)
        sol = solve_2sat(inst)
        if sol is None:
            print("UNSAT — cannot submit unsatisfiable instance")
            return
        resp = send_command({
            "command": "submit",
            "instance": inst.to_dict(),
            "solution": sol,
            "source": "cli",
        })
        print(json.dumps(resp, indent=2))

    elif args.mode == "solve":
        inst = TwoSATInstance.random(args.n_vars, args.n_clauses, args.seed)
        resp = send_command({
            "command": "query" if False else "solve",
            "instance": inst.to_dict(),
            "max_steps": args.max_steps,
        })
        print(json.dumps(resp, indent=2))

    elif args.mode == "query":
        inst = TwoSATInstance.random(args.n_vars, args.n_clauses, args.seed)
        resp = send_command({
            "command": "query",
            "instance": inst.to_dict(),
            "max_steps": args.max_steps,
        })
        print(json.dumps(resp, indent=2))

    elif args.mode == "populate":
        rng = np.random.RandomState(args.seed)
        for i in range(args.count):
            seed = rng.randint(0, 2**31)
            inst = TwoSATInstance.random(args.n_vars, args.n_clauses, seed)
            sol = solve_2sat(inst)
            if sol is None:
                continue
            resp = send_command({
                "command": "submit",
                "instance": inst.to_dict(),
                "solution": sol,
                "source": "populate",
            })
            if i % 10 == 0:
                print(f"  submitted {i+1}/{args.count} (corpus: {resp.get('corpus_size', '?')})")
        print(f"populated: {args.count} instances submitted")
        # Show final status
        status = send_command({"command": "status"})
        print(json.dumps(status, indent=2))
        print(f"cache hit rate: {status.get('cache_hit_rate', 0):.2%}")
        print(f"alpha: {status.get('alpha', 'N/A')}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
