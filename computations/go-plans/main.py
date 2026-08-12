#!/usr/bin/env python3
"""
Go Plans — a comprehensive Go strategy system "better than anyone has ever seen."

Features:
  - Full-rules Go board (9x9, 13x13, 19x19) with ko and superko
  - Monte Carlo Tree Search AI engine (playable opponent)
  - Fuseki/joseki library with named openings
  - Shin Jinseo strategy guide — the world #1's complete playbook
  - Tactical position analysis and territory estimation
  - SGF import/export
  - Beautiful Unicode terminal rendering
  - Interactive play mode

Modes:
  python3 main.py play        — Interactive game (Human vs AI or Human vs Human)
  python3 main.py analyze     — Analyze an SGF file
  python3 main.py fuseki      — Browse opening patterns
  python3 main.py joseki      — Browse corner sequences
  python3 main.py shin        — Shin Jinseo strategy guide
  python3 main.py train       — Engine self-play training
  python3 main.py demo        — Run a demo game
"""

from __future__ import annotations
import sys
import os
import argparse
from typing import Optional, Tuple
import random

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board import Board, Color, Point, new_9x9, new_13x13, new_19x19
from engine import MCTSEngine, create_engine
from fuseki import (
    FUSEKI_DATABASE, JOSEKI_DATABASE,
    match_fuseki, match_joseki, get_fuseki_guide,
    list_all_fuseki, list_all_joseki, analyze_opening,
)
from sgf_parser import parse_sgf, export_sgf, board_to_sgf, sgf_from_moves
from analysis import analyze_position, quick_analysis, detailed_report
from render import (
    render_board, render_compact, render_with_annotations,
    render_game_info, render_influence, render_move_preview,
)
from shin_jinseo import (
    SHIN_OPENINGS, SHIN_TECHNIQUES, PRINCIPLES, FAMOUS_GAMES,
    identify_shin_patterns, evaluate_shin_style,
    shin_recommend_move, shin_style_guide, shin_principles_summary,
)


def parse_point(s: str, board_size: int) -> Optional[Point]:
    """Parse a human coordinate like 'D4', 'Q16', 'pass'."""
    s = s.strip().upper()
    if s in ("PASS", "P", ""):
        return None

    # Parse column letter
    col_char = s[0]
    col = ord(col_char) - ord('A')
    if col >= 8:  # skip I
        col -= 1

    row = int(s[1:]) - 1

    if 0 <= col < board_size and 0 <= row < board_size:
        return Point(board_size - 1 - row, col)
    raise ValueError(f"Invalid coordinate: {s}")


def format_point(point: Optional[Point], board_size: int) -> str:
    """Format a Point to human-readable coordinate."""
    if point is None:
        return "pass"
    col = point.col
    if col >= 8:
        col += 1  # skip I
    col_char = chr(ord('A') + col)
    row = board_size - point.row
    return f"{col_char}{row}"


# ─── Interactive Play ──────────────────────────────────────

def cmd_play(args):
    """Interactive Go game."""
    size = args.size or 19
    komi = args.komi or 6.5

    board = Board(size=size, komi=komi)
    engine = None

    if args.ai:
        strength = args.strength or "medium"
        engine = create_engine(size, strength)
        print(f"  AI opponent: {strength} strength ({engine.num_simulations} simulations/move)")

    last_move = None
    print(f"\n  New game: {size}x{size}, Komi: {komi}\n")

    while not board.finished:
        # Show board
        print(render_game_info(board, black_name="You" if not args.ai else "Human",
                               white_name="AI" if args.ai else "Opponent"))
        print(render_board(board, last_move=last_move))

        # Show quick analysis
        if board.move_number > 3:
            report = analyze_position(board)
            print(f"  {report.overall_assessment}")
            if report.key_points:
                kp = report.key_points[:3]
                print(f"  Key: " + " | ".join(f"{k.point.label()}({k.label})" for k in kp))
            print()

        # Check for Shin patterns
        if board.move_number >= 4:
            shin_patterns = identify_shin_patterns(board)
            if shin_patterns:
                best = shin_patterns[0]
                print(f"  🎯 Shin Jinseo pattern: {best['name']} (confidence: {best['confidence']:.0%})")
                print()

        # AI move
        if engine and board.current_player == Color.WHITE:
            print("  AI thinking...")
            point, stats = engine.best_move(board, time_limit=args.time or 5.0)
            board.play(point)
            last_move = point
            print(f"  AI plays: {format_point(point, size)}")
            print(f"  Confidence: {stats['confidence']}% | PV: {' → '.join(stats['pv'][:5])}")
            if stats['alternatives']:
                alt_str = ", ".join(f"{a[0]}({a[1]}%)" for a in stats['alternatives'][:3])
                print(f"  Alternatives: {alt_str}")
            print()
            continue

        # Human move
        try:
            move_str = input(f"  {'●' if board.current_player == Color.BLACK else '○'} Your move: ").strip()

            if move_str.lower() in ("quit", "q", "exit"):
                print("  Game ended.")
                break
            if move_str.lower() in ("undo", "u"):
                if board.undo():
                    if engine:
                        board.undo()  # undo AI move too
                    last_move = board.history[-1][0] if board.history else None
                    print("  Move undone.\n")
                else:
                    print("  No moves to undo.\n")
                continue
            if move_str.lower() in ("hint", "h", "help", "?"):
                _show_hint(board, engine)
                continue
            if move_str.lower() in ("score", "s"):
                black_s, white_s = board.score()
                print(f"  Estimated score — Black: {black_s:.1f}, White: {white_s:.1f}")
                print(f"  Difference: {abs(black_s - white_s):.1f} for {'Black' if black_s > white_s else 'White'}\n")
                continue
            if move_str.lower() in ("analyze", "a"):
                print(detailed_report(board))
                continue
            if move_str.lower() in ("shin",):
                shin_eval = evaluate_shin_style(board)
                print(f"\n  Shin Style Score: {shin_eval['shin_score']:.1f}%")
                print(f"  Assessment: {shin_eval['assessment']}")
                print(f"  Principle breakdown:")
                for k, v in shin_eval['principles'].items():
                    print(f"    {k}: {v:.1f}%")
                rec = shin_recommend_move(board)
                if rec:
                    print(f"\n  Shin would play: {format_point(rec['move'], size)}")
                    print(f"  Reason: {rec['reason']}")
                print()
                continue
            if move_str.lower() in ("sgf",):
                sgf = board_to_sgf(board)
                print(f"\n  SGF:\n{sgf}\n")
                continue

            point = parse_point(move_str, size)
            if not board.play(point):
                print("  ❌ Illegal move!\n")
                continue

            last_move = point
        except (ValueError, IndexError) as e:
            print(f"  ❌ Invalid input: {e}")
            print("  Format: LetterNumber (e.g., D4, Q16) or 'pass'\n")
            continue

        except (EOFError, KeyboardInterrupt):
            print("\n  Game ended.")
            break

    # Game over
    print("\n" + render_board(board, last_move=last_move))
    black_s, white_s = board.score()
    print(f"\n  {'='*40}")
    print(f"  GAME OVER — Black: {black_s:.1f}, White: {white_s:.1f}")
    if black_s > white_s:
        print(f"  ● Black wins by {black_s - white_s:.1f} points!")
    elif white_s > black_s:
        print(f"  ○ White wins by {white_s - black_s:.1f} points!")
    else:
        print("  Draw!")
    print(f"  {'='*40}")

    # Option to save SGF
    try:
        save = input("\n  Save as SGF? [y/N]: ").strip().lower()
        if save == 'y':
            sgf = board_to_sgf(board)
            fname = f"game_{random.randint(1000, 9999)}.sgf"
            with open(fname, 'w') as f:
                f.write(sgf)
            print(f"  Saved to {fname}")
    except (EOFError, KeyboardInterrupt):
        pass


def _show_hint(board: Board, engine: Optional[MCTSEngine]):
    """Show move hint using engine or fuseki matching."""
    print()

    # Shin recommendation
    shin_rec = shin_recommend_move(board)
    if shin_rec:
        print(f"  🎯 Shin Jinseo says: {format_point(shin_rec['move'], board.size)}")
        print(f"     {shin_rec['reason']}")

    # Engine recommendation
    if engine:
        point, stats = engine.best_move(board, time_limit=2.0)
        print(f"  🤖 AI recommends: {format_point(point, board.size)}")
        print(f"     Confidence: {stats['confidence']}%")
        print(f"     PV: {' → '.join(stats['pv'][:5])}")
    else:
        # Fuseki-based hint
        analysis = analyze_opening(board)
        if analysis['identified_fuseki']:
            name, score = analysis['identified_fuseki'][0]
            print(f"  📖 Opening: {name} ({score:.0%} match)")
        if analysis['suggestions']:
            for s in analysis['suggestions']:
                print(f"  💡 {s}")

    print()


# ─── SGF Analysis ──────────────────────────────────────────

def cmd_analyze(args):
    """Analyze an SGF file."""
    if not args.file:
        print("  Usage: python3 main.py analyze <file.sgf>")
        return

    with open(args.file) as f:
        sgf_text = f.read()

    game = parse_sgf(sgf_text)
    board = game.to_board()

    print(f"\n  Analyzing: {args.file}")
    print(f"  {game.black_player} (B) vs {game.white_player} (W)")
    print(f"  Result: {game.result}  |  Komi: {game.komi}")
    print(f"  Moves: {len(game.moves)}")
    print()

    # Show final position
    print(render_board(board))
    print()

    # Detailed analysis
    print(detailed_report(board))

    # Shin Jinseo evaluation
    print("\n  ── SHIN JINSEO ANALYSIS ──")
    shin_eval = evaluate_shin_style(board)
    print(f"  Shin Style Score: {shin_eval['shin_score']:.1f}%")
    print(f"  {shin_eval['assessment']}")

    shin_patterns = identify_shin_patterns(board)
    if shin_patterns:
        print("\n  Detected Shin patterns:")
        for p in shin_patterns:
            print(f"    ◆ {p['name']} ({p['type']}, confidence: {p['confidence']:.0%})")

    print()


# ─── Fuseki / Joseki Browser ───────────────────────────────

def cmd_fuseki(args):
    """Browse opening patterns."""
    if args.name:
        pattern = get_fuseki_guide(args.name)
        if pattern:
            print(f"\n  {pattern.name} ({pattern.name_jp})")
            print(f"  {'='*50}")
            print(f"  Era: {pattern.era}  |  Popularity: {'★' * pattern.popularity}")
            print(f"  Difficulty: {'★' * pattern.difficulty}")
            print(f"  Player: {pattern.player_example}")
            print(f"\n  {pattern.description}")
            print("\n  Key moves:")
            for m in pattern.moves:
                key = "  ⬥" if m.is_key_point else "   "
                print(f"  {key} {m.move.label()} ({m.color}) — {m.description[:80]}...")
                if m.alternatives:
                    for alt_pt, alt_desc in m.alternatives:
                        print(f"       Alt: {alt_pt.label()} — {alt_desc[:60]}...")
            print()
        else:
            print(f"  No fuseki found matching '{args.name}'")
            print("  Available: " + ", ".join(p.name for p in FUSEKI_DATABASE))
    else:
        print("\n  FUSEKI DATABASE\n")
        for fuseki in FUSEKI_DATABASE:
            print(f"  ◆ {fuseki.name} ({fuseki.name_jp})")
            print(f"    Era: {fuseki.era:10s} | Popularity: {'★' * fuseki.popularity} | Difficulty: {'★' * fuseki.difficulty}")
            print(f"    {fuseki.description[:100]}...")
            print()


def cmd_joseki(args):
    """Browse joseki sequences."""
    print("\n  JOSEKI DATABASE\n")
    for j in JOSEKI_DATABASE:
        status = "✓ AI-approved" if j.ai_approved else "⚠ Traditional"
        print(f"  ◆ {j.name} [{j.category}] — {status}")
        print(f"    {j.description[:100]}...")
        print(f"    Variations: {len(j.sequences)}")
        for i, seq in enumerate(j.sequences):
            moves_str = " → ".join(f"{pt.label()}({color})" for pt, color, _ in seq)
            print(f"      Var {i+1}: {moves_str}")
        print()


# ─── Shin Jinseo Guide ─────────────────────────────────────

def cmd_shin(args):
    """Display the Shin Jinseo strategy guide."""
    if args.summary:
        print(shin_principles_summary())
    elif args.principle:
        pname = args.principle.upper()
        for p in PRINCIPLES:
            if pname in p.principle.name:
                print(f"\n  {p.principle.name}")
                print(f"  {'='*50}")
                print(f"  {p.summary}")
                print(f"\n  {p.explanation}")
                print(f"\n  📋 Example: {p.example_game}")
                print()
                return
        print(f"  Principle '{args.principle}' not found.")
        print(f"  Available: " + ", ".join(p.principle.name for p in PRINCIPLES))
    elif args.opening:
        oname = args.opening.lower()
        for o in SHIN_OPENINGS:
            if oname in o.name.lower():
                print(f"\n  {o.name}")
                print(f"  {'='*50}")
                print(f"  Win rate: {o.win_rate*100:.0f}%  |  Frequency: {o.frequency*100:.0f}%")
                print(f"\n  {o.description}")
                print(f"\n  Innovation: {o.key_innovation}")
                print(f"\n  Moves:")
                for pt, color, ann in o.moves:
                    print(f"    {format_point(pt, 19)} ({color}) — {ann[:80]}...")
                if o.counters:
                    print(f"\n  Counters: " + " | ".join(o.counters))
                print()
                return
        print(f"  Opening '{args.opening}' not found.")
        print(f"  Available: " + ", ".join(o.name for o in SHIN_OPENINGS))
    elif args.technique:
        tname = args.technique.lower()
        for t in SHIN_TECHNIQUES:
            if tname in t.name.lower():
                print(f"\n  {t.name} [{t.category}]")
                print(f"  {'='*50}")
                print(f"  Difficulty: {'★' * t.difficulty}")
                print(f"\n  {t.description}")
                print(f"\n  Setup: {t.setup}")
                print(f"\n  Sequence:")
                for pt, color, ann in t.sequence:
                    print(f"    {format_point(pt, 19)} ({color}) — {ann[:80]}...")
                print(f"\n  AI Evaluation: {t.ai_evaluation}")
                print(f"\n  📋 {t.game_reference}")
                print()
                return
        print(f"  Technique '{args.technique}' not found.")
        print(f"  Available: " + ", ".join(t.name for t in SHIN_TECHNIQUES))
    elif args.games:
        print("\n  SHIN JINSEO — FAMOUS GAMES\n")
        for g in FAMOUS_GAMES:
            print(f"  ◆ vs {g.opponent}")
            print(f"    {g.event} — {g.date}")
            print(f"    Result: {g.result}")
            print(f"    {g.significance[:120]}...")
            print(f"    Key moves: {', '.join(f'#{n} {format_point(pt, 19)}' for n, pt, _ in g.key_moves[:3])}")
            print()
    else:
        print()
        print(shin_style_guide())


# ─── Demo ──────────────────────────────────────────────────

def cmd_demo(args):
    """Run a quick demo game."""
    board = new_19x19()
    engine = create_engine(19, "fast")

    # Play a Shin Double 3-3 opening
    print("\n  🎯 DEMO: Shin Jinseo Double 3-3 Opening")
    print("  Black: AI (Shin-style)  vs  White: AI\n")

    # Play opening moves to demonstrate Shin style
    demo_moves = [
        Point(16, 3),   # B: 3-3 bottom right
        Point(2, 15),   # W: 3-3 top left
        Point(16, 15),  # B: 3-3 top right
        Point(2, 3),    # W: 3-3 bottom left
        Point(15, 10),  # B: Micro Chinese extension
        Point(3, 10),   # W: Side extension
    ]

    for i, move in enumerate(demo_moves):
        if board.finished:
            break
        color = Color.BLACK if i % 2 == 0 else Color.WHITE
        board.play(move)
        print(f"  Move {i+1}: {color} plays {format_point(move, 19)}")
        print(render_compact(board, last_move=move))
        print()

    # Let engines continue
    print("  Continuing with AI play...")
    for i in range(15):
        if board.finished:
            break
        color = board.current_player
        point, stats = engine.best_move(board, time_limit=0.5)
        if point and point.row >= 0:
            board.play(point)
            print(f"  Move {board.move_number}: {color} plays {format_point(point, 19)} "
                  f"({stats['confidence']:.0f}%)")

    print()
    print(render_board(board))

    # Analysis
    shin_eval = evaluate_shin_style(board)
    print(f"\n  Shin Style Score: {shin_eval['shin_score']:.1f}%")
    print(f"  {shin_eval['assessment']}")

    black_s, white_s = board.score()
    print(f"  Score: Black {black_s:.1f} — White {white_s:.1f}")
    print()


# ─── Training ──────────────────────────────────────────────

def cmd_train(args):
    """Self-play training for the engine."""
    print("  Self-play training mode not yet implemented.")
    print("  The engine already uses MCTS with heuristic playouts.")
    print("  For neural network training, integrate with KataGo or Leela Zero.")


# ─── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Go Plans — comprehensive Go strategy system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # Play
    p_play = sub.add_parser("play", help="Interactive Go game")
    p_play.add_argument("--size", type=int, choices=[9, 13, 19], help="Board size")
    p_play.add_argument("--komi", type=float, help="Komi (default: 6.5)")
    p_play.add_argument("--ai", action="store_true", help="Play against AI")
    p_play.add_argument("--strength", choices=["fast", "medium", "strong", "max"],
                        default="medium", help="AI strength")
    p_play.add_argument("--time", type=float, default=5.0, help="AI think time (seconds)")

    # Analyze
    p_analyze = sub.add_parser("analyze", help="Analyze an SGF file")
    p_analyze.add_argument("file", help="SGF file to analyze")

    # Fuseki
    p_fuseki = sub.add_parser("fuseki", help="Browse fuseki patterns")
    p_fuseki.add_argument("name", nargs="?", help="Specific fuseki name")

    # Joseki
    p_joseki = sub.add_parser("joseki", help="Browse joseki sequences")

    # Shin
    p_shin = sub.add_parser("shin", help="Shin Jinseo strategy guide")
    p_shin.add_argument("--summary", action="store_true", help="Quick reference card")
    p_shin.add_argument("--principle", help="Explain a specific principle")
    p_shin.add_argument("--opening", help="Show a specific Shin opening")
    p_shin.add_argument("--technique", help="Show a specific Shin technique")
    p_shin.add_argument("--games", action="store_true", help="List famous games")

    # Demo
    p_demo = sub.add_parser("demo", help="Run a demo game")

    # Train
    p_train = sub.add_parser("train", help="Self-play training")

    args = parser.parse_args()

    if args.command == "play":
        cmd_play(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "fuseki":
        cmd_fuseki(args)
    elif args.command == "joseki":
        cmd_joseki(args)
    elif args.command == "shin":
        cmd_shin(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "train":
        cmd_train(args)
    else:
        parser.print_help()
        print(f"\n  Quick start:")
        print(f"    python3 main.py shin          — Shin Jinseo strategy guide")
        print(f"    python3 main.py play --ai     — Play against AI")
        print(f"    python3 main.py demo          — Watch a demo game")
        print(f"    python3 main.py fuseki        — Browse opening theory")


if __name__ == "__main__":
    main()
