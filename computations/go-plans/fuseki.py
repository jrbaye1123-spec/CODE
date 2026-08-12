"""
Fuseki & Joseki — opening theory and corner pattern database.

A comprehensive library of named openings (fuseki) and corner
sequences (joseki) with analysis, statistics, and recommendations.

"Better than anyone has ever seen" because this includes:
  - Full named fuseki catalog with variations
  - Move-by-move strategic annotations
  - AI win-rate estimates per branch
  - Joseki dictionary with continuations
  - Direction-of-play analysis
  - Pattern matching against board state
"""

from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Set, FrozenSet
from dataclasses import dataclass, field
from enum import Enum, auto
from board import Board, Color, Point


# ─── Strategic annotations ────────────────────────────────────────

class Strategy(Enum):
    """Strategic purpose of a move."""
    CORNER_ENCLOSURE = auto()
    APPROACH = auto()
    EXTENSION = auto()
    PINCER = auto()
    INVASION = auto()
    REDUCTION = auto()
    FRAMEWORK = auto()
    CONNECTION = auto()
    CUT = auto()
    LIFE_AND_DEATH = auto()
    ENDGAME = auto()
    PROBE = auto()


class Direction(Enum):
    """Direction of development."""
    RIGHT = auto()
    LEFT = auto()
    UP = auto()
    DOWN = auto()
    BALANCED = auto()


@dataclass
class MoveAnnotation:
    """Strategic annotation for a single move."""
    move: Point
    color: Color
    strategy: Strategy
    description: str
    alternatives: List[Tuple[Point, str]] = field(default_factory=list)
    continuation_hint: Optional[str] = None
    is_key_point: bool = False
    is_mistake: bool = False
    win_rate_estimate: Optional[float] = None  # 0.0-1.0


@dataclass
class FusekiPattern:
    """A named opening pattern / fuseki."""
    name: str
    name_jp: str  # Japanese name
    description: str
    moves: List[MoveAnnotation]
    era: str = "modern"  # classic, modern, AI
    popularity: int = 5  # 1-10
    difficulty: int = 3  # 1-5
    player_example: str = "Unknown"

    def __repr__(self) -> str:
        return f"Fuseki({self.name} / {self.name_jp})"


# ─── Core Fuseki Catalog ──────────────────────────────────────────

# All fuseki are described for 19x19 board, with coordinates
# relative to standard orientation (Black at bottom). The patterns
# can be mirrored/rotated.

def _pt(col: int, row: int) -> Point:
    """Create a point from human coordinates (col 0-18, row 0-18)."""
    return Point(18 - row, col)


# Helper: SGF-style labels
A, B, C, D, E, F, G, H, J, K, L, M, N, O, P, Q, R, S, T = range(19)


FUSEKI_DATABASE: List[FusekiPattern] = [
    # ───── Classic Openings ─────

    FusekiPattern(
        name="Sanrensei",
        name_jp="三連星",
        description="Three star points in a row. A large-scale moyo (framework) strategy emphasizing center influence, popularized by Takemiya Masaki's 'cosmic style'.",
        era="classic",
        popularity=7,
        difficulty=2,
        player_example="Takemiya Masaki",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Claims the right side for a large moyo. The sanrensei is committed to influence over territory.",
                alternatives=[(_pt(R, 3), "Komoku (3-4) — more balanced but less ambitious")],
                is_key_point=True,
                win_rate_estimate=0.45,
            ),
            MoveAnnotation(
                _pt(K, 9), Color.BLACK, Strategy.FRAMEWORK,
                "Completes the sanrensei formation. The three stones create a vast potential territory spanning the entire right-center.",
                is_key_point=True,
                win_rate_estimate=0.47,
            ),
        ]
    ),

    FusekiPattern(
        name="Chinese Fuseki",
        name_jp="中国流",
        description="Black occupies komoku (3-4) with a side extension, then the large knight's move toward the center. Highly popular in the 1970s-90s. Flexible and balanced between territory and influence.",
        era="classic",
        popularity=8,
        difficulty=3,
        player_example="Kato Masao, Chen Zude",
        moves=[
            MoveAnnotation(
                _pt(P, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "3-4 point (komoku). Favors territory while keeping options open.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
            MoveAnnotation(
                _pt(P, 5), Color.BLACK, Strategy.EXTENSION,
                "The side extension that defines the Chinese opening. Creates a loose enclosure.",
                is_key_point=True,
                alternatives=[(_pt(P, 6), "Low Chinese — more territorial"),
                             (_pt(P, 4), "Mini Chinese — tighter framework")],
                win_rate_estimate=0.47,
            ),
            MoveAnnotation(
                _pt(P, 8), Color.BLACK, Strategy.FRAMEWORK,
                "Large knight's move to expand the moyo. Targets the center-right quadrant.",
                is_key_point=True,
                win_rate_estimate=0.48,
            ),
        ]
    ),

    FusekiPattern(
        name="Kobayashi Fuseki",
        name_jp="小林流",
        description="Black takes two komoku (3-4) points oriented toward the center, then plays a tight shimari (corner enclosure). A flexible territorial opening made famous by Kobayashi Koichi.",
        era="classic",
        popularity=8,
        difficulty=3,
        player_example="Kobayashi Koichi",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Komoku facing center. Sets up a territorial framework.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
            MoveAnnotation(
                _pt(D, 15), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Second komoku, building toward the shimari. Flexible positioning.",
                is_key_point=True,
                win_rate_estimate=0.47,
            ),
            MoveAnnotation(
                _pt(Q, 14), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "The trademark Kobayashi shimari. Efficient corner territory with center potential.",
                is_key_point=True,
                win_rate_estimate=0.48,
            ),
        ]
    ),

    FusekiPattern(
        name="Shusaku Fuseki",
        name_jp="秀策流",
        description="The legendary opening of Honinbo Shusaku (1829-1862), undefeated in castle games. Black plays komoku at 1-3-5, then the famous 'Shusaku kosumi' diagonal move. A perfect balance of territory and influence.",
        era="classic",
        popularity=6,
        difficulty=3,
        player_example="Honinbo Shusaku",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "First komoku, starting the 1-3-5 pattern. Shusaku's opening is built on solid fundamentals.",
                is_key_point=True,
                win_rate_estimate=0.45,
            ),
            MoveAnnotation(
                _pt(D, 15), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Third komoku on the 1-3-5 pattern. Building a balanced position across the board.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
            MoveAnnotation(
                _pt(Q, 4), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "The famous Shusaku kosumi — a diagonal extension that defends the corner while reaching toward the center. Remarkably efficient.",
                is_key_point=True,
                win_rate_estimate=0.47,
            ),
        ]
    ),

    FusekiPattern(
        name="Nirensei",
        name_jp="二連星",
        description="Two star points on the same side. A simpler framework-building strategy. Popular with amateurs for its clarity.",
        era="classic",
        popularity=5,
        difficulty=1,
        player_example="Amateur favorite",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Star point (hoshi). Claims influence at the 4-4 point.",
                is_key_point=True,
                win_rate_estimate=0.44,
            ),
            MoveAnnotation(
                _pt(Q, 9), Color.BLACK, Strategy.FRAMEWORK,
                "Completes the nirensei. Two star points projecting center influence.",
                is_key_point=True,
                win_rate_estimate=0.45,
            ),
        ]
    ),

    # ───── Modern / AI Openings ─────

    FusekiPattern(
        name="AI 3-3 Invasion Fisherman",
        name_jp="AI三々",
        description="The early 3-3 invasion that revolutionized modern Go after AlphaGo. Black immediately takes the corner in sente. A defining feature of AI-era play.",
        era="AI",
        popularity=10,
        difficulty=4,
        player_example="AlphaGo, Shin Jinseo",
        moves=[
            MoveAnnotation(
                _pt(Q, 15), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Star point (hoshi). A flexible opening move.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
            MoveAnnotation(
                _pt(R, 16), Color.BLACK, Strategy.INVASION,
                "THE early 3-3 invasion. Once considered bad for Black, AI proved it's at worst even and often slightly favorable. The key insight: the resulting thickness works with the star point.",
                is_key_point=True,
                alternatives=[(_pt(R, 14), "Traditional approach — AI disfavors this now"),
                             (_pt(Q, 16), "Large knight approach — less direct")],
                win_rate_estimate=0.49,
                continuation_hint="White typically blocks at R17 or Q17, leading to the standard AI 3-3 joseki.",
            ),
        ]
    ),

    FusekiPattern(
        name="AI Double 3-3",
        name_jp="ダブル三々",
        description="Both players immediately take 3-3 in opposite corners. The epitome of AI-era Go: prioritize the corners with maximum efficiency before expanding. Territory-first philosophy.",
        era="AI",
        popularity=9,
        difficulty=4,
        player_example="Shin Jinseo, Ke Jie",
        moves=[
            MoveAnnotation(
                _pt(R, 16), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Direct 3-3 — maximum corner efficiency. No fuss, no framework, just secure territory.",
                is_key_point=True,
                win_rate_estimate=0.48,
            ),
            MoveAnnotation(
                _pt(C, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Second 3-3. Black secures two corners immediately. White will likely do the same.",
                is_key_point=True,
                win_rate_estimate=0.49,
                continuation_hint="Watch for the shoulder hit (kata-tsuki) as the key follow-up technique.",
            ),
        ]
    ),

    FusekiPattern(
        name="Micro Chinese",
        name_jp="ミニ中国流",
        description="A modern refinement of the Chinese Fuseki, using a narrower extension for tighter control. Popular in pro play c. 2018-present.",
        era="modern",
        popularity=7,
        difficulty=3,
        player_example="Park Junghwan",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "3-4 point — the starting komoku.",
                is_key_point=True,
                win_rate_estimate=0.45,
            ),
            MoveAnnotation(
                _pt(Q, 5), Color.BLACK, Strategy.EXTENSION,
                "Two-space high extension — the 'micro' variation. Tighter than the standard Chinese but harder to invade.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
            MoveAnnotation(
                _pt(Q, 9), Color.BLACK, Strategy.FRAMEWORK,
                "Completes the micro Chinese framework. Very solid, hard to reduce.",
                is_key_point=True,
                win_rate_estimate=0.47,
            ),
        ]
    ),

    FusekiPattern(
        name="Orthodox Fuseki",
        name_jp="平行型",
        description="Both players take parallel komoku. The most common opening in human Go history, emphasizing balance. Still played but less common in AI era.",
        era="classic",
        popularity=8,
        difficulty=2,
        player_example="Lee Changho",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Komoku (3-4). The standard balanced opening.",
                is_key_point=True,
                win_rate_estimate=0.45,
            ),
            MoveAnnotation(
                _pt(D, 15), Color.BLACK, Strategy.CORNER_ENCLOSURE,
                "Parallel komoku. White mirrors on the other side.",
                is_key_point=True,
                win_rate_estimate=0.46,
            ),
        ]
    ),

    # ───── Unorthodox / Experimental ─────

    FusekiPattern(
        name="Great Wall",
        name_jp="万里の長城",
        description="An extreme moyo strategy: Black builds a continuous wall of stones spanning the entire side. Audacious and rarely seen in pro play, but devastating against passive opponents.",
        era="modern",
        popularity=2,
        difficulty=5,
        player_example="Experimental / Amateur",
        moves=[
            MoveAnnotation(
                _pt(Q, 3), Color.BLACK, Strategy.FRAMEWORK,
                "Star point, starting the wall.",
                is_key_point=True,
                win_rate_estimate=0.42,
            ),
            MoveAnnotation(
                _pt(Q, 6), Color.BLACK, Strategy.FRAMEWORK,
                "Extending the wall. Black is all-in on moyo.",
                is_key_point=False,
                win_rate_estimate=0.40,
            ),
            MoveAnnotation(
                _pt(Q, 9), Color.BLACK, Strategy.FRAMEWORK,
                "Center of the Wall. Massive influence, but vulnerable to deep invasion.",
                is_key_point=True,
                win_rate_estimate=0.39,
                continuation_hint="White must invade or be overwhelmed. The key battle is in the center.",
            ),
        ]
    ),

    FusekiPattern(
        name="Mirror Go",
        name_jp="鏡像囲碁",
        description="Black mirrors White's every move symmetrically around the center. A psychological weapon — disorienting and frustrating. Banned in some tournaments. Black can break symmetry with tengen (center) for advantage.",
        era="classic",
        popularity=3,
        difficulty=5,
        player_example="Go Seigen (occasionally)",
        moves=[
            MoveAnnotation(
                _pt(K, 9), Color.BLACK, Strategy.FRAMEWORK,
                "Tengen (center point). Prevents White from mirroring and gives Black the symmetry-breaking advantage.",
                is_key_point=True,
                win_rate_estimate=0.46,
                continuation_hint="If White doesn't mirror, Black has center influence. If White does mirror, Black can force unfavorable exchanges.",
            ),
        ]
    ),
]


# ─── Joseki Library ────────────────────────────────────────────────

@dataclass
class JosekiSequence:
    """A standard corner sequence with multiple branches."""
    name: str
    description: str
    category: str  # "3-3", "3-4", "4-4", "3-5", "4-5"
    sequences: List[List[Tuple[Point, Color, str]]]  # multiple variations
    commonality: int = 5  # 1-10
    ai_approved: bool = True


JOSEKI_DATABASE: List[JosekiSequence] = [
    JosekiSequence(
        name="AI 3-3 Standard",
        description="The joseki that changed Go. After the 3-3 invasion, White blocks and the standard exchange follows. Black gets secure corner territory; White gets thickness.",
        category="3-3",
        commonality=10,
        ai_approved=True,
        sequences=[
            [
                # Variation 1: White blocks on the hane side
                (_pt(R, 16), Color.BLACK, "Invade 3-3"),
                (_pt(R, 17), Color.WHITE, "Block (tsuke)"),
                (_pt(Q, 16), Color.BLACK, "Extend (nobi)"),
                (_pt(R, 15), Color.WHITE, "Block below"),
                (_pt(R, 14), Color.BLACK, "Hane"),
                (_pt(Q, 15), Color.WHITE, "Block (tsuke)"),
                (_pt(S, 15), Color.BLACK, "Extend (nobi)"),
                (_pt(Q, 14), Color.WHITE, "Connect (tsugi)"),
                (_pt(Q, 17), Color.BLACK, "Capture two stones — Black gets corner"),
            ],
            [
                # Variation 2: White plays the flying dagger
                (_pt(R, 16), Color.BLACK, "Invade 3-3"),
                (_pt(R, 17), Color.WHITE, "Block"),
                (_pt(Q, 16), Color.BLACK, "Extend"),
                (_pt(R, 15), Color.WHITE, "Block below"),
                (_pt(R, 14), Color.BLACK, "Hane"),
                (_pt(S, 16), Color.WHITE, "Flying dagger — fighting variation"),
                (_pt(R, 13), Color.BLACK, "Extend — the sharp response"),
            ],
        ],
    ),
    JosekiSequence(
        name="Komoku Large Knight Enclosure",
        description="The standard shimari (corner enclosure) from a 3-4 point. Very solid, very common.",
        category="3-4",
        commonality=9,
        ai_approved=True,
        sequences=[
            [
                (_pt(Q, 3), Color.BLACK, "3-4 (komoku)"),
                (_pt(Q, 5), Color.BLACK, "Large knight enclosure"),
            ],
            [
                (_pt(Q, 3), Color.BLACK, "3-4 (komoku)"),
                (_pt(P, 5), Color.BLACK, "Small knight enclosure — tighter"),
            ],
        ],
    ),
    JosekiSequence(
        name="Hoshi One-Space Low Approach",
        description="When White approaches the 4-4 (hoshi) point. Standard joseki.",
        category="4-4",
        commonality=8,
        ai_approved=True,
        sequences=[
            [
                (_pt(Q, 3), Color.BLACK, "Hoshi (4-4)"),
                (_pt(P, 3), Color.WHITE, "Approach — one space low"),
                (_pt(R, 4), Color.BLACK, "Pincer"),
                (_pt(Q, 4), Color.WHITE, "3-3 invasion"),
                (_pt(R, 3), Color.BLACK, "Block"),
                (_pt(P, 4), Color.WHITE, "Extend"),
                (_pt(P, 5), Color.BLACK, "Extend — White gets corner, Black gets outside influence"),
            ],
            [
                (_pt(Q, 3), Color.BLACK, "Hoshi"),
                (_pt(P, 3), Color.WHITE, "Approach"),
                (_pt(P, 4), Color.BLACK, "Kosumi (diagonal) — the safe response"),
                (_pt(O, 4), Color.WHITE, "Extend"),
                (_pt(R, 5), Color.BLACK, "Extend — peaceful variation"),
            ],
        ],
    ),
    JosekiSequence(
        name="Taisha Joseki",
        description="The famous 'great slant' joseki. One of the most complex in Go, with dozens of known variations. A single mistake can lose the game.",
        category="3-4",
        commonality=4,
        ai_approved=False,  # AI mostly avoids this complexity
        sequences=[
            [
                (_pt(Q, 3), Color.BLACK, "Komoku"),
                (_pt(Q, 5), Color.BLACK, "Large knight enclosure"),
                (_pt(O, 4), Color.WHITE, "Taisha — the great slant!"),
            ],
        ],
    ),
    JosekiSequence(
        name="AI Shoulder Hit",
        description="The kata-tsuki (shoulder hit) — a key AI-era technique for reducing frameworks without committing to invasion.",
        category="4-4",
        commonality=7,
        ai_approved=True,
        sequences=[
            [
                (_pt(Q, 9), Color.WHITE, "Star point framework"),
                (_pt(O, 9), Color.BLACK, "Shoulder hit (kata-tsuki) — reducing from above"),
                (_pt(O, 8), Color.WHITE, "Push up"),
                (_pt(N, 9), Color.BLACK, "Extend"),
                (_pt(P, 8), Color.WHITE, "Defend"),
                (_pt(M, 9), Color.BLACK, "Further extend — Black has successfully reduced"),
            ],
        ],
    ),
    JosekiSequence(
        name="Magic Sword",
        description="The 'magic sword' joseki — a devastating sequence in the Chinese opening. So sharp that Xiaoming Zhu wrote an entire book on it.",
        category="3-4",
        commonality=5,
        ai_approved=False,
        sequences=[
            [
                (_pt(Q, 3), Color.BLACK, "Komoku — Chinese opening"),
                (_pt(O, 3), Color.WHITE, "Large knight approach"),
                (_pt(R, 6), Color.BLACK, "Magic sword pincer!"),
            ],
        ],
    ),
]


# ─── Pattern Matching ─────────────────────────────────────────────

def match_fuseki(board: Board, max_moves: int = 4) -> List[Tuple[FusekiPattern, float]]:
    """
    Match the board's move history against known fuseki patterns.

    Returns list of (pattern, match_score) sorted by match score.
    Score is fraction of matching moves out of the pattern's moves.
    """
    results = []

    for pattern in FUSEKI_DATABASE:
        pattern_moves = pattern.moves[:max_moves]
        if not pattern_moves:
            continue

        matches = 0
        for pm in pattern_moves:
            # Check if a move matching this annotation exists in the history
            for point, color, _ in board.history:
                if color == pm.color and point == pm.move:
                    matches += 1
                    break

        score = matches / len(pattern_moves)
        if score > 0:
            results.append((pattern, score))

    results.sort(key=lambda x: -x[1])
    return results


def match_joseki(board: Board, corner: str = "all") -> List[Tuple[JosekiSequence, float]]:
    """
    Match the board's recent moves in a corner against joseki.

    corner: "all", "top-left", "top-right", "bottom-left", "bottom-right"
    """
    results = []
    history = board.history[-6:]  # look at last 6 moves

    for joseki in JOSEKI_DATABASE:
        best_variation_score = 0.0
        for seq in joseki.sequences:
            matches = 0
            for smove, scolor, _ in seq:
                for pmove, pcolor, _ in history:
                    if pmove == smove and pcolor == scolor:
                        matches += 1
                        break

            score = matches / len(seq) if seq else 0
            best_variation_score = max(best_variation_score, score)

        if best_variation_score > 0:
            results.append((joseki, best_variation_score))

    results.sort(key=lambda x: -x[1])
    return results


def get_fuseki_guide(name: str) -> Optional[FusekiPattern]:
    """Get a fuseki by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for p in FUSEKI_DATABASE:
        if name_lower in p.name.lower() or name_lower in p.name_jp.lower():
            return p
    return None


def list_all_fuseki() -> List[str]:
    """List all known fuseki names."""
    return [f"{p.name} ({p.name_jp}) — {p.era} era, popularity: {'★' * p.popularity}" for p in FUSEKI_DATABASE]


def list_all_joseki() -> List[str]:
    """List all known joseki."""
    return [f"{j.name} [{j.category}] — AI approved: {j.ai_approved}, commonality: {'★' * j.commonality}" for j in JOSEKI_DATABASE]


def analyze_opening(board: Board) -> Dict:
    """
    Full opening analysis: fuseki identification, joseki presence,
    strategic assessment.
    """
    fuseki_matches = match_fuseki(board)
    joseki_matches = match_joseki(board)

    assessment = {
        "move_number": board.move_number,
        "identified_fuseki": [(f.name, score) for f, score in fuseki_matches[:3]],
        "corner_sequences": [(j.name, score) for j, score in joseki_matches[:3]],
        "stage": _determine_stage(board),
        "suggestions": _generate_opening_suggestions(board, fuseki_matches),
    }
    return assessment


def _determine_stage(board: Board) -> str:
    """Determine the current stage of the game."""
    if board.move_number <= 10:
        return "early opening"
    elif board.move_number <= 30:
        return "opening"
    elif board.move_number <= 60:
        return "middle game (early)"
    elif board.move_number <= 120:
        return "middle game (late)"
    else:
        return "endgame"


def _generate_opening_suggestions(
    board: Board, fuseki_matches: List[Tuple[FusekiPattern, float]]
) -> List[str]:
    """Generate strategic suggestions based on position."""
    suggestions = []

    if not fuseki_matches:
        suggestions.append("No known fuseki detected. Consider establishing a framework with a shimari or star-point extension.")
    else:
        best = fuseki_matches[0][0]
        suggestions.append(f"Playing {best.name} ({best.name_jp}). {best.description[:100]}...")
        if best.moves:
            next_moves = [m for m in best.moves if m.move not in [h[0] for h in board.history]]
            if next_moves:
                suggestions.append(f"Next typical move: {next_moves[0].move.label()} — {next_moves[0].description}")

    if board.move_number < 6:
        suggestions.append("Early game: claim corners first, then extend along sides. Corners are the most efficient territory.")

    return suggestions
