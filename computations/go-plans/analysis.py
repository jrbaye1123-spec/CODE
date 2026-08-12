"""
Tactical Analysis — position evaluation and strategic insight.

Features:
  - Group life/death assessment
  - Territory estimation
  - Influence map
  - Weak group detection
  - Key point identification
  - Tesuji suggestions
  - Full position report
"""

from __future__ import annotations
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from board import Board, Color, Point
from collections import deque


@dataclass
class TacticalPoint:
    """A point with tactical significance."""
    point: Point
    label: str
    significance: str  # "critical", "big", "urgent", "interesting"
    description: str
    category: str  # "capture", "connection", "extension", "invasion", etc.


@dataclass
class GroupAnalysis:
    """Analysis of a single group."""
    stones: Set[Point]
    color: Color
    liberties: int
    eyes: int
    potential_eyes: int
    status: str  # "alive", "dead", "unsettled", "in_atari"
    territory_controlled: int  # estimated points


@dataclass
class PositionReport:
    """Full tactical analysis of a board position."""
    board: Board
    groups: List[GroupAnalysis]
    territory_map: Dict[Color, int]
    influence_map: List[List[float]]  # +Black, -White
    weak_groups: List[GroupAnalysis]
    strong_groups: List[GroupAnalysis]
    key_points: List[TacticalPoint]
    overall_assessment: str
    urgency_rating: int  # 1-10 how urgent the position is


def analyze_position(board: Board) -> PositionReport:
    """Full tactical analysis of the current position."""
    groups = _analyze_all_groups(board)
    territory = _estimate_territory(board)
    influence = _compute_influence(board)
    weak = [g for g in groups if g.status in ("dead", "unsettled", "in_atari")]
    strong = [g for g in groups if g.status == "alive" and g.eyes >= 2]
    key_points = _find_key_points(board, groups, influence)
    assessment = _assess_position(board, groups, territory)
    urgency = _compute_urgency(board, groups)

    return PositionReport(
        board=board,
        groups=groups,
        territory_map=territory,
        influence_map=influence,
        weak_groups=weak,
        strong_groups=strong,
        key_points=key_points,
        overall_assessment=assessment,
        urgency_rating=urgency,
    )


def _analyze_all_groups(board: Board) -> List[GroupAnalysis]:
    """Analyze every group on the board."""
    groups = []
    for r in range(board.size):
        for c in range(board.size):
            p = Point(r, c)
            if board.at(p) is not None and p in board.groups:
                group = board.groups[p]
                stones = set(group.stones)
                libs = group.num_liberties
                eyes, pot_eyes = _count_eyes(board, group)

                status = "alive"
                if libs == 0:
                    status = "dead"
                elif libs == 1:
                    status = "in_atari"
                elif eyes >= 2:
                    status = "alive"
                elif eyes == 1 and pot_eyes >= 1:
                    status = "unsettled"

                territory_est = len(stones)  # rough

                ga = GroupAnalysis(
                    stones=stones,
                    color=group.color,
                    liberties=libs,
                    eyes=eyes,
                    potential_eyes=pot_eyes,
                    status=status,
                    territory_controlled=territory_est,
                )
                groups.append(ga)

    return groups


def _count_eyes(board: Board, group) -> Tuple[int, int]:
    """
    Count eyes and potential eyes for a group.
    Returns (definite_eyes, potential_eyes).
    """
    stones = set(group.stones)
    color = group.color

    # Find all empty points adjacent to this group
    empty_neighbors: Set[Point] = set()
    for stone in stones:
        for n in board.get_neighbors(stone):
            if board.at(n) is None:
                empty_neighbors.add(n)

    # Partition empty neighbors into connected regions
    eye_regions: List[Set[Point]] = []
    visited: Set[Point] = set()

    for start in empty_neighbors:
        if start in visited:
            continue
        region: Set[Point] = set()
        queue = deque([start])
        bordered_only_by_friend = True

        while queue:
            q = queue.popleft()
            if q in visited:
                continue
            visited.add(q)
            region.add(q)

            for n in board.get_neighbors(q):
                if board.at(n) is None:
                    if n not in visited:
                        queue.append(n)
                elif board.at(n) != color:
                    bordered_only_by_friend = False

        if bordered_only_by_friend and len(region) > 0:
            eye_regions.append(region)

    # Count eyes: definite eyes are single points or larger regions
    definite = sum(1 for r in eye_regions if 1 <= len(r) <= 2)
    potential = len(eye_regions)

    return definite, potential


def _estimate_territory(board: Board) -> Dict[Color, int]:
    """Estimate territory using flood fill."""
    territory = {Color.BLACK: 0, Color.WHITE: 0}
    visited: Set[Point] = set()

    for r in range(board.size):
        for c in range(board.size):
            p = Point(r, c)
            if p in visited or board.at(p) is not None:
                continue

            area, borders = _flood_fill(board, p, visited)
            if len(borders) == 1:
                territory[borders.pop()] += len(area)

    # Add captured stones (Japanese scoring)
    territory[Color.BLACK] += board.captures[Color.BLACK]
    territory[Color.WHITE] += board.captures[Color.WHITE]

    return territory


def _flood_fill(board: Board, start: Point, visited: Set[Point]) -> Tuple[Set[Point], Set[Color]]:
    """Flood fill from start, return (area, bordering_colors)."""
    area: Set[Point] = set()
    borders: Set[Color] = set()
    queue = deque([start])

    while queue:
        p = queue.popleft()
        if p in visited:
            continue
        visited.add(p)

        if board.at(p) is None:
            area.add(p)
            for n in board.get_neighbors(p):
                if n not in visited:
                    queue.append(n)
        else:
            borders.add(board.at(p))

    return area, borders


def _compute_influence(board: Board) -> List[List[float]]:
    """
    Compute influence map using a simple distance-based heuristic.
    Positive = Black influence, Negative = White influence.
    """
    size = board.size
    influence = [[0.0] * size for _ in range(size)]

    # Source points (stones)
    for r in range(size):
        for c in range(size):
            stone = board.grid[r][c]
            if stone is None:
                continue

            sign = 1.0 if stone == Color.BLACK else -1.0

            # Radiate influence
            for dr in range(-4, 5):
                for dc in range(-4, 5):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < size and 0 <= nc < size:
                        distance = abs(dr) + abs(dc)
                        if distance <= 4:
                            decay = 1.0 / (1.0 + distance)
                            influence[nr][nc] += sign * decay

    return influence


def _find_key_points(
    board: Board,
    groups: List[GroupAnalysis],
    influence: List[List[float]],
) -> List[TacticalPoint]:
    """Identify tactically significant points on the board."""
    key_points: List[TacticalPoint] = []

    # 1. Capturing points (atari)
    for g in groups:
        if g.status == "in_atari":
            # Find the liberty point
            for stone in g.stones:
                for n in board.get_neighbors(stone):
                    if board.at(n) is None:
                        key_points.append(TacticalPoint(
                            n, "Capture",
                            "critical",
                            f"Captures {g.color}'s group in atari",
                            "capture",
                        ))

    # 2. Saving points (own atari)
    for g in groups:
        if g.status == "in_atari" and g.color == board.current_player:
            for stone in g.stones:
                for n in board.get_neighbors(stone):
                    if board.at(n) is None:
                        key_points.append(TacticalPoint(
                            n, "Save",
                            "urgent",
                            f"Saves own group in atari",
                            "defense",
                        ))

    # 3. Connection points — cutting points between opponent groups
    # Simplified: find empty points adjacent to two opponent groups
    _add_connection_points(board, key_points)

    # 4. Extension points — big moves on the sides
    _add_extension_points(board, key_points)

    # 5. Empty corners
    _add_corner_points(board, key_points)

    # Deduplicate and sort by significance
    seen = set()
    unique = []
    for kp in key_points:
        if kp.point not in seen:
            seen.add(kp.point)
            unique.append(kp)

    priority = {"critical": 0, "urgent": 1, "big": 2, "interesting": 3}
    unique.sort(key=lambda k: priority.get(k.significance, 99))

    return unique[:15]


def _add_connection_points(board: Board, key_points: List[TacticalPoint]) -> None:
    """Find connection/cutting points."""
    for r in range(board.size):
        for c in range(board.size):
            p = Point(r, c)
            if board.at(p) is not None:
                continue

            adj_colors: Set[Color] = set()
            for n in board.get_neighbors(p):
                if board.at(n) is not None:
                    adj_colors.add(board.at(n))

            if len(adj_colors) >= 2:
                key_points.append(TacticalPoint(
                    p, "Cut/Connect",
                    "big",
                    "Connection point between opposing groups — key for shape",
                    "connection",
                ))


def _add_extension_points(board: Board, key_points: List[TacticalPoint]) -> None:
    """Find big extension points on the sides."""
    size = board.size
    # Check third and fourth lines
    for r in [2, 3, size - 3, size - 4]:
        for c in range(size):
            p = Point(r, c)
            if board.at(p) is not None:
                continue
            # Check if there are stones nearby for extension
            has_stone_near = False
            for n in board.get_neighbors(p):
                if board.at(n) is not None:
                    has_stone_near = True
                    break
            if not has_stone_near:
                # Check 2-3 spaces away
                for dr in range(-3, 4):
                    for dc in range(-3, 4):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < size and 0 <= nc < size:
                            if abs(dr) + abs(dc) <= 3 and board.grid[nr][nc] is not None:
                                has_stone_near = True
                                break
            if has_stone_near:
                key_points.append(TacticalPoint(
                    p, "Extension",
                    "big",
                    "Good extension point on the side",
                    "extension",
                ))


def _add_corner_points(board: Board, key_points: List[TacticalPoint]) -> None:
    """Find empty corner points that need attention."""
    corners = [(0, 0), (0, board.size - 1),
               (board.size - 1, 0), (board.size - 1, board.size - 1)]

    for r, c in corners:
        # Check 3x3 corner area
        has_stone = False
        for dr in range(3):
            for dc in range(3):
                nr, nc = r + dr * (1 if r == 0 else -1), c + dc * (1 if c == 0 else -1)
                if 0 <= nr < board.size and 0 <= nc < board.size:
                    if board.grid[nr][nc] is not None:
                        has_stone = True

        if has_stone:
            # The 3-3 point
            tr = r + 2 * (1 if r == 0 else -1)
            tc = c + 2 * (1 if c == 0 else -1)
            if 0 <= tr < board.size and 0 <= tc < board.size:
                p = Point(tr, tc)
                if board.at(p) is None:
                    key_points.append(TacticalPoint(
                        p, "3-3 Invasion",
                        "big",
                        "Classic 3-3 invasion point — takes corner territory",
                        "invasion",
                    ))


def _assess_position(
    board: Board,
    groups: List[GroupAnalysis],
    territory: Dict[Color, int],
) -> str:
    """Generate an overall position assessment."""
    black_territory = territory.get(Color.BLACK, 0) + board.komi
    white_territory = territory.get(Color.WHITE, 0)

    diff = black_territory - white_territory

    black_groups = [g for g in groups if g.color == Color.BLACK]
    white_groups = [g for g in groups if g.color == Color.WHITE]
    black_weak = sum(1 for g in black_groups if g.status != "alive")
    white_weak = sum(1 for g in white_groups if g.status != "alive")

    parts = []

    if abs(diff) > 15:
        leader = "Black" if diff > 0 else "White"
        parts.append(f"{leader} leads by ~{abs(diff):.0f} points")
    elif abs(diff) > 5:
        leader = "Black" if diff > 0 else "White"
        parts.append(f"{leader} ahead slightly (~{abs(diff):.0f} pts)")
    else:
        parts.append("Position is balanced")

    if black_weak > 0:
        parts.append(f"Black has {black_weak} weak group(s)")
    if white_weak > 0:
        parts.append(f"White has {white_weak} weak group(s)")

    if board.move_number < 15:
        parts.append("Still in opening phase")
    elif board.move_number > 100:
        parts.append("Late game / endgame")

    return ". ".join(parts) + "."


def _compute_urgency(board: Board, groups: List[GroupAnalysis]) -> int:
    """
    Compute urgency rating 1-10.
    High urgency: groups in atari, unsettled groups, close score.
    """
    urgency = 1

    atari_groups = [g for g in groups if g.status == "in_atari"]
    unsettled = [g for g in groups if g.status == "unsettled"]

    urgency += len(atari_groups) * 3
    urgency += len(unsettled) * 2

    # Clamp to 1-10
    return max(1, min(10, urgency))


def quick_analysis(board: Board) -> str:
    """Quick one-line analysis for display."""
    report = analyze_position(board)
    lines = [f"Move {board.move_number}: {report.overall_assessment}"]

    if report.weak_groups:
        lines.append(f"  ⚠ Weak groups: {len(report.weak_groups)}")

    if report.key_points:
        top3 = report.key_points[:3]
        kp_str = ", ".join(f"{kp.point.label()}({kp.label})" for kp in top3)
        lines.append(f"  Key points: {kp_str}")

    return "\n".join(lines)


def detailed_report(board: Board) -> str:
    """Generate a detailed position report."""
    report = analyze_position(board)
    lines = [
        "=" * 60,
        "  POSITION ANALYSIS",
        "=" * 60,
        f"  Move: {board.move_number}  |  Komi: {board.komi}",
        f"  Next: {board.current_player}",
        "",
        f"  Assessment: {report.overall_assessment}",
        f"  Urgency: {'█' * report.urgency_rating}{'░' * (10 - report.urgency_rating)} {report.urgency_rating}/10",
        "",
        f"  Groups: {len(report.groups)} total",
        f"    Alive: {len([g for g in report.groups if g.status == 'alive'])}",
        f"    Weak:  {len(report.weak_groups)}",
        "",
    ]

    if report.weak_groups:
        lines.append("  WEAK GROUPS:")
        for g in report.weak_groups:
            stones = sorted(g.stones)[:5]
            labels = [s.label() for s in stones]
            lines.append(f"    {g.color} — {g.status} ({g.liberties} liberties, {g.eyes} eyes) at {', '.join(labels)}")

    if report.key_points:
        lines.append("")
        lines.append("  KEY POINTS:")
        for kp in report.key_points[:10]:
            sig_marker = {"critical": "⚡", "urgent": "⚠", "big": "●", "interesting": "○"}
            marker = sig_marker.get(kp.significance, "·")
            lines.append(f"    {marker} {kp.point.label():5s} [{kp.label:12s}] {kp.description}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
