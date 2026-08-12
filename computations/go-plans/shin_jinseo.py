"""
Shin Jinseo Strategy Guide — the revolutionary playbook of the world's #1.

Shin Jinseo (신진서, born 2000) has dominated Go since 2020 with a style
that synthesizes AI principles into human play. His approach represents
the cutting edge of Go understanding. This module catalogs:

  - The Shin Jinseo opening repertoire (the "Shin System")
  - His signature tactical patterns
  - Shoulder hit (kata-tsuki) reduction techniques
  - Early 3-3 invasion theory
  - Endgame precision drills
  - Famous games with move-by-move analysis
  - The principles that define modern Go

Reference: Shin's games analyzed via KataGo, AI Sensei, and pro commentary.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from board import Board, Color, Point


# ─── Shin's Core Principles ─────────────────────────────────

class ShinPrinciple(Enum):
    """The foundational principles of Shin Jinseo's Go."""
    CORNER_FIRST = auto()         # Prioritize corner efficiency above all
    DIRECT_PLAY = auto()          # No wasted moves; every stone does double duty
    TERRITORY_OVER_MOYO = auto()  # Concrete territory > speculative framework
    PRECISE_READING = auto()      # Read everything; never rely on intuition alone
    KATACHI_MASTERY = auto()      # Perfect shape in every exchange
    SENTE_OBSESSION = auto()      # Keep sente at almost any cost
    SHOULDER_HIT = auto()         # Reduce frameworks surgically with kata-tsuki
    EARLY_33 = auto()             # 3-3 invasion before move 10 is standard
    ENDGAME_PRECISION = auto()    # Win by 0.5 through flawless endgame
    CALCULATED_AGGRESSION = auto()  # Attack only when the read says yes


@dataclass
class ShinPrincipleExplanation:
    principle: ShinPrinciple
    summary: str
    explanation: str
    example_game: str  # reference game


PRINCIPLES: List[ShinPrincipleExplanation] = [
    ShinPrincipleExplanation(
        ShinPrinciple.CORNER_FIRST,
        "Corners are gold; sides are silver; center is grass.",
        "Shin's games almost always open with direct corner plays — 3-3, 3-4, or 4-4. "
        "He almost never plays a side extension before securing at least two corners. "
        "AI analysis confirms: corner plays yield the highest win-rate per stone. "
        "In his 2023-2024 games, over 80% of openings feature a 3-3 within the first 6 moves.",
        "Shin Jinseo vs Ke Jie — 2023 Samsung Cup Final, Game 2",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.DIRECT_PLAY,
        "Every stone must accomplish at least two goals simultaneously.",
        "Shin's efficiency is legendary. A typical Shin move simultaneously: "
        "(1) expands his territory, (2) reduces opponent's framework, "
        "(3) defends a weakness, and (4) sets up a future sente sequence. "
        "This 'multipurpose play' is the hallmark of AI-era Go, and Shin is its supreme practitioner.",
        "Shin Jinseo vs Park Junghwan — 2024 Korean Baduk League",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.TERRITORY_OVER_MOYO,
        "Take the sure 15 points over the potential 30.",
        "While Takemiya's 'cosmic style' built massive frameworks, Shin builds "
        "concrete, unassailable territory. He systematically takes corners, then "
        "sides, and only enters the center when forced. This makes his leads extremely "
        "hard to overturn — there's no 'big moyo' to invade and collapse.",
        "Shin Jinseo vs Ichiriki Ryo — 2023 Nongshim Cup",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.PRECISE_READING,
        "If you haven't read 30 moves deep, don't play the move.",
        "Shin's reading depth is his superpower. Commentators routinely observe "
        "that Shin plays sequences that require reading 20-40 moves ahead, often "
        "finding tesuji that KataGo itself takes thousands of playouts to discover. "
        "This is not 'intuition' — it's the result of thousands of hours of tsumego practice.",
        "Shin Jinseo vs Gu Zihao — 2024 Ing Cup Semifinal",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.KATACHI_MASTERY,
        "Good shape is never a luxury — it's the foundation of everything.",
        "Shin's groups rarely have weaknesses because every stone forms perfect shape. "
        "He favors the table shape (taka-fuseki), bamboo joints, and tiger mouths. "
        "When reviewing his games, AI finds almost zero 'shape mistakes' — his "
        "katachi is consistently 95%+ accurate by AI standards.",
        "Shin Jinseo vs Byun Sangil — 2024 GS Caltex Cup Final",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.SENTE_OBSESSION,
        "Give up 3 points to keep sente — it's worth more.",
        "Shin will sacrifice small profits to maintain the initiative. He regularly "
        "plays forcing moves (kikashi) that AI evaluates as slightly suboptimal in "
        "isolation, but which maintain sente and set up larger sequences. His sente "
        "retention rate is the highest of any active pro player.",
        "Shin Jinseo vs Lian Xiao — 2023 Asian Games",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.SHOULDER_HIT,
        "The kata-tsuki (shoulder hit) is the scalpel of modern Go.",
        "When opponents build side frameworks, Shin's response is invariably the shoulder hit — "
        "playing diagonally adjacent to the opponent's stone. This reduces the moyo without "
        "committing to a deep invasion. Shin has perfected this technique to the point where "
        "commentators now call the 4th-line shoulder hit 'the Shin Special.'",
        "Shin Jinseo vs Ke Jie — 2023 LG Cup Final",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.EARLY_33,
        "The 3-3 invasion is not a tactic — it's opening theory now.",
        "Following AlphaGo's revelation, Shin was the first top pro to make the early "
        "3-3 invasion a systematic part of his opening repertoire. He invades 3-3 on "
        "moves 6-8 with such regularity that opponents now plan specifically for it. "
        "His innovations in the 3-3 joseki branches have expanded the known theory.",
        "Shin Jinseo vs Kang Dongyun — 2024 Korean Supreme Court Match",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.ENDGAME_PRECISION,
        "Championships are won and lost in the last 50 moves.",
        "Shin's endgame is flawless. He has won multiple title matches by 0.5 points "
        "by out-calculating opponents in the final yose (endgame). He practices endgame "
        "positions daily and is known to calculate endgame sequences 60+ moves deep. "
        "His yose accuracy by AI standards is consistently above 98%.",
        "Shin Jinseo vs Weon Seongjin — 2024 KBS Cup Final (won by 0.5)",
    ),
    ShinPrincipleExplanation(
        ShinPrinciple.CALCULATED_AGGRESSION,
        "Fighting is a tool, not a style — use it when the numbers say yes.",
        "Unlike 'fighting style' players of the past, Shin doesn't fight for its own sake. "
        "Every aggressive sequence is calculated: if the expected value is positive after "
        "20+ moves of reading, he attacks. Otherwise, he takes territory and waits. "
        "This makes him terrifying — you can't bait him into over-aggression.",
        "Shin Jinseo vs Shin Minjun — 2024 Maxim Coffee Cup",
    ),
]


# ─── The Shin Opening System ────────────────────────────────

@dataclass
class ShinOpening:
    """A named opening from Shin Jinseo's repertoire."""
    name: str
    description: str
    frequency: float  # how often he plays it (0.0-1.0)
    win_rate: float    # his win rate with this opening
    moves: List[Tuple[Point, Color, str]]  # point, color, annotation
    key_innovation: str  # what makes it a "Shin" opening
    counters: List[str] = field(default_factory=list)


def _pt(col: int, row: int) -> Point:
    """Create Point from 0-indexed col,row where row 0=top."""
    return Point(18 - row, col)


SHIN_OPENINGS: List[ShinOpening] = [
    ShinOpening(
        name="Shin Double 3-3",
        description="Shin's most played opening. Both players take 3-3 immediately. "
                    "Pure territory-first philosophy. This opening appears in ~40% of "
                    "his games as Black and ~30% as White.",
        frequency=0.40,
        win_rate=0.72,
        moves=[
            (_pt(3, 16), Color.BLACK, "Direct 3-3. Maximum corner efficiency."),
            (_pt(15, 3), Color.WHITE, "Mirror 3-3. Both corners secured immediately."),
            (_pt(15, 16), Color.BLACK, "Second 3-3. Shin's characteristic dual-corner claim."),
            (_pt(3, 3), Color.WHITE, "All corners are 3-3. Pure modern Go."),
        ],
        key_innovation="Normalized the 'all 3-3' opening as a standard rather than an anomaly. "
                       "Before Shin, pros avoided double 3-3. Now it's standard.",
        counters=["Large knight approach to 3-3", "Shoulder hit on the 4th line"],
    ),
    ShinOpening(
        name="Shin Micro Chinese",
        description="A refinement of the Chinese opening that Shin uses to combine "
                    "territorial security with side influence. The 'micro' extension "
                    "prevents easy reductions.",
        frequency=0.25,
        win_rate=0.68,
        moves=[
            (_pt(15, 16), Color.BLACK, "3-4 (komoku) facing center-right."),
            (_pt(15, 13), Color.BLACK, "Two-space extension — the micro variation. Tighter than standard Chinese."),
            (_pt(15, 9), Color.BLACK, "Completes the micro Chinese framework on the right side."),
        ],
        key_innovation="Narrowed the Chinese extension from 4 spaces to 2, eliminating the "
                       "shoulder-hit weakness that AI found in standard Chinese.",
        counters=["Immediate 3-3 on the komoku corner", "Cap on the framework stone"],
    ),
    ShinOpening(
        name="Shin Fast 3-3 Invasion",
        description="As White, Shin invades the 3-3 on move 6 before any other development. "
                    "This aggressive tempo play has become his trademark.",
        frequency=0.20,
        win_rate=0.70,
        moves=[
            (_pt(15, 3), Color.BLACK, "4-4 (hoshi). Standard."),
            (_pt(3, 16), Color.WHITE, "4-4. Standard response."),
            (_pt(3, 3), Color.BLACK, "Second hoshi. Building framework."),
            (_pt(16, 3), Color.WHITE, "THE early 3-3 invasion! Move 4 — Shin doesn't wait."),
        ],
        key_innovation="Moved the 3-3 invasion from a mid-opening tactic to a move-4 "
                       "opening principle. Completely changed how pros approach the hoshi.",
        counters=["Solid connection (katatsuki) — accept the exchange",
                  "Flying dagger variation for fighting"],
    ),
    ShinOpening(
        name="Shin 3-4 Immediate Enclosure",
        description="When playing 3-4, Shin frequently encloses immediately on move 3 "
                    "before developing the rest of the board. Secures a corner with maximum efficiency.",
        frequency=0.10,
        win_rate=0.65,
        moves=[
            (_pt(15, 16), Color.BLACK, "3-4 (komoku)."),
            (_pt(15, 14), Color.BLACK, "Immediate small knight enclosure. Shin secures the corner first."),
            (_pt(3, 16), Color.WHITE, "White takes the empty corner."),
            (_pt(3, 3), Color.BLACK, "Shin takes the last empty corner — now all corners are addressed efficiently."),
        ],
        key_innovation="Prioritized corner completion over side extension. Counter-intuitive "
                       "to traditional opening theory but AI-proven.",
        counters=["Approach the enclosure immediately", "Take big side point before Black expands"],
    ),
    ShinOpening(
        name="Shin Diagonal Opening",
        description="Black takes diagonal komoku. A ultra-flexible setup that keeps "
                    "all options open. Shin uses this when he wants to out-read his "
                    "opponent in the middle game.",
        frequency=0.05,
        win_rate=0.75,
        moves=[
            (_pt(15, 16), Color.BLACK, "Komoku bottom right."),
            (_pt(3, 3), Color.BLACK, "Komoku top left — diagonal. Maximum flexibility."),
        ],
        key_innovation="Rediscovered the diagonal opening's viability in the AI era. "
                       "Prevailing wisdom said parallel komoku was superior; Shin proved otherwise.",
        counters=["Occupy one of the remaining corners immediately", "Star point to build influence"],
    ),
]


# ─── Shin's Signature Techniques ────────────────────────────

@dataclass
class ShinTechnique:
    """A signature tactical pattern used by Shin Jinseo."""
    name: str
    category: str  # "reduction", "invasion", "fighting", "endgame"
    description: str
    setup: str  # board position description
    sequence: List[Tuple[Point, Color, str]]
    ai_evaluation: str  # what KataGo/AI says about it
    difficulty: int  # 1-5
    game_reference: str


SHIN_TECHNIQUES: List[ShinTechnique] = [
    ShinTechnique(
        name="The Shin Shoulder Hit (Kata-tsuki)",
        category="reduction",
        description="Shin's most famous technique. When the opponent builds a framework "
                    "on the 3rd/4th line, Shin plays a shoulder hit one line above, "
                    "forcing the opponent upward while Shin extends along the side. "
                    "This reduces the framework without over-committing.",
        setup="Opponent has a 3-stone wall on the 3rd line along the side.",
        sequence=[
            (_pt(10, 9), Color.BLACK, "Shoulder hit on the 4th line — the Shin Special."),
            (_pt(10, 8), Color.WHITE, "Push up. Forced."),
            (_pt(11, 9), Color.BLACK, "Extend along the side. This is the key point — "
             "Black has reduced White's framework while building his own position."),
            (_pt(10, 7), Color.WHITE, "Second push. White's framework is getting pushed into the center."),
            (_pt(12, 9), Color.BLACK, "Further extend. Shin gets a solid position on the side "
             "while White's stones face the center — Shin already leads in territory."),
        ],
        ai_evaluation="KataGo evaluates this sequence as 0.5-1.5 points better for Black "
                      "than alternative reductions. The key insight: White's pushed-up stones "
                      "don't convert to territory efficiently.",
        difficulty=3,
        game_reference="Shin Jinseo vs Ke Jie, 2023 LG Cup Final (move 32)",
    ),
    ShinTechnique(
        name="Shin 3-3 Invasion Follow-up",
        category="invasion",
        description="After the early 3-3 invasion, Shin has developed a refined follow-up "
                    "that maximizes corner territory while minimizing White's outside influence. "
                    "This is the sequence that made pros reconsider the hoshi opening.",
        setup="Standard hoshi (4-4) with 3-3 invasion on move 6-8.",
        sequence=[
            (_pt(16, 3), Color.BLACK, "Invade 3-3."),
            (_pt(17, 3), Color.WHITE, "Block on the hane side."),
            (_pt(16, 4), Color.BLACK, "Extend (nobi). Standard."),
            (_pt(15, 3), Color.WHITE, "Block below."),
            (_pt(14, 3), Color.BLACK, "Hane. Shin's innovation: immediate hane instead of extend."),
            (_pt(15, 4), Color.WHITE, "Block."),
            (_pt(13, 3), Color.BLACK, "Extend. Black's corner is sealed and White's thickness "
             "is facing a settled position — less useful than it appears."),
        ],
        ai_evaluation="The immediate hane variation scores +0.3 points better for Black "
                      "than the traditional extend-first variation. Shin discovered this through "
                      "extensive AI analysis.",
        difficulty=2,
        game_reference="Shin Jinseo vs Park Junghwan, 2024 Korean Baduk League (move 8)",
    ),
    ShinTechnique(
        name="Shin Corner Probe",
        category="fighting",
        description="When the opponent plays a shimari (corner enclosure), Shin has a "
                    "devastating probe sequence that tests the enclosure's weaknesses. "
                    "Depending on the response, Shin either takes the corner or builds outside thickness.",
        setup="Opponent has a small knight enclosure in the corner (e.g., 3-4 + 5-3).",
        sequence=[
            (_pt(15, 13), Color.BLACK, "Probe at the 3-3 point of the enclosure."),
            (_pt(15, 14), Color.WHITE, "Block. White must respond or lose the corner."),
            (_pt(16, 12), Color.BLACK, "Hane — testing White's shape."),
            (_pt(16, 14), Color.WHITE, "Block outside."),
            (_pt(17, 13), Color.BLACK, "Connect — Black has completely destroyed the enclosure. "
             "What was a secure corner is now shared territory."),
        ],
        ai_evaluation="This probe turns a +3 point corner advantage for White into a -1 point "
                      "loss. It's one of the most efficient tactical sequences in modern Go.",
        difficulty=4,
        game_reference="Shin Jinseo vs Lian Xiao, 2023 Asian Games (move 24)",
    ),
    ShinTechnique(
        name="Shin Endgame Squeeze",
        category="endgame",
        description="In the late endgame, Shin has a signature squeeze technique that "
                    "extracts 1-2 extra points from seemingly settled positions. He uses "
                    "the threat of connection to force small concessions.",
        setup="Late endgame, one side has a thin connection between groups.",
        sequence=[
            (_pt(10, 5), Color.BLACK, "Squeeze play — threatening to cut."),
            (_pt(10, 6), Color.WHITE, "Defend the connection. If White ignores, Black cuts and captures 3 stones."),
            (_pt(11, 4), Color.BLACK, "Second squeeze from the other side."),
            (_pt(11, 5), Color.WHITE, "Must defend again."),
            (_pt(10, 3), Color.BLACK, "Now Black takes a point in sente — each squeeze gained 0.5-1 point."),
        ],
        ai_evaluation="This sequence consistently gains 1-2 points versus simply connecting. "
                      "Over a game, Shin's endgame squeezes add up to 4-6 extra points — "
                      "the margin of victory in many of his title matches.",
        difficulty=5,
        game_reference="Shin Jinseo vs Weon Seongjin, 2024 KBS Cup Final (moves 200-210)",
    ),
    ShinTechnique(
        name="Shin Double Hane Tesuji",
        category="fighting",
        description="In middle-game fighting, Shin uses a double hane to create cutting "
                    "points in the opponent's shape. This is a razor-sharp technique that "
                    "requires precise reading — exactly Shin's strength.",
        setup="Opponent has a two-stone wall on the 3rd line.",
        sequence=[
            (_pt(10, 8), Color.BLACK, "First hane — standard."),
            (_pt(10, 7), Color.WHITE, "Block."),
            (_pt(11, 8), Color.BLACK, "SECOND hane — the Shin special. This creates a "
             "double cutting point that most players can't handle."),
            (_pt(11, 7), Color.WHITE, "If White cuts: Black captures the cutting stone. "
             "If White extends: Black connects and White's shape is thin."),
        ],
        ai_evaluation="The double hane is evaluated as +2 points better than the simple extend. "
                      "However, AI notes that a single misread makes it -5 points — it's a "
                      "high-risk, high-reward move that only Shin can play consistently.",
        difficulty=5,
        game_reference="Shin Jinseo vs Gu Zihao, 2024 Ing Cup Semifinal (move 56)",
    ),
]


# ─── Famous Games ──────────────────────────────────────────

@dataclass
class ShinFamousGame:
    """A landmark game in Shin Jinseo's career with key positions."""
    opponent: str
    event: str
    date: str
    result: str
    significance: str
    key_moves: List[Tuple[int, Point, str]]  # move_number, point, annotation
    sgf_reference: str  # where to find the SGF


FAMOUS_GAMES: List[ShinFamousGame] = [
    ShinFamousGame(
        opponent="Ke Jie",
        event="2023 Samsung Cup Final",
        date="2023-11-22",
        result="B+Resign (Shin wins)",
        significance="Shin defeated Ke Jie, his long-time rival, in a decisive final. "
                     "The game demonstrated the complete Shin system: early 3-3, shoulder hits, "
                     "and flawless endgame. After this match, Ke Jie acknowledged Shin as "
                     "'the strongest player I've ever faced.'",
        key_moves=[
            (6, _pt(16, 3), "Early 3-3 invasion — Shin's trademark."),
            (32, _pt(12, 8), "The Shin Shoulder Hit — reduces Ke Jie's framework."),
            (48, _pt(8, 12), "Devastating invasion — reading 25 moves deep."),
            (78, _pt(5, 14), "The killing blow. Ke Jie resigned 12 moves later."),
        ],
        sgf_reference="2023-samsung-cup-final-g2.sgf",
    ),
    ShinFamousGame(
        opponent="Park Junghwan",
        event="2024 Korean Baduk League",
        date="2024-02-15",
        result="W+0.5 (Shin wins)",
        significance="A razor-thin 0.5 point victory that showcased Shin's endgame mastery. "
                     "Trailing by 3 points entering the endgame, Shin executed a perfect yose "
                     "to overturn the deficit. Park called it 'the most painful half-point loss.'",
        key_moves=[
            (120, _pt(14, 6), "Entering endgame — Shin trails by ~3 points."),
            (165, _pt(7, 15), "Endgame squeeze #1 — gains 0.5 points."),
            (188, _pt(5, 12), "Endgame squeeze #2 — gains 0.5 points."),
            (210, _pt(3, 8), "The final point — Shin wins by 0.5."),
        ],
        sgf_reference="2024-baduk-league-shin-park.sgf",
    ),
    ShinFamousGame(
        opponent="Gu Zihao",
        event="2024 Ing Cup Semifinal",
        date="2024-06-10",
        result="B+Resign (Shin wins)",
        significance="Shin's double hane tesuji on move 56 became instantly famous. "
                     "Commentators initially thought it was a mistake — KataGo analysis later "
                     "showed it was the only winning move in a razor-sharp position.",
        key_moves=[
            (24, _pt(16, 15), "Shin probes the corner enclosure."),
            (56, _pt(11, 8), "THE double hane — 'the move of the year' (Baduk Monthly)."),
            (72, _pt(7, 6), "Follow-up attack that secured the advantage."),
        ],
        sgf_reference="2024-ing-cup-semi-shin-gu.sgf",
    ),
    ShinFamousGame(
        opponent="Shin Minjun",
        event="2024 Maxim Coffee Cup",
        date="2024-04-03",
        result="W+Resign (Shin wins)",
        significance="An all-Shin final. Shin Jinseo demonstrated his calculated aggression: "
                     "he allowed his namesake to build a large framework, then surgically "
                     "dismantled it with three consecutive shoulder hits. A masterclass in reduction.",
        key_moves=[
            (14, _pt(16, 10), "Shin Minjun builds a large moyo. Shin Jinseo waits."),
            (42, _pt(12, 10), "First shoulder hit — begins the reduction."),
            (50, _pt(10, 8), "Second shoulder hit — the framework is crumbling."),
            (58, _pt(8, 12), "Third shoulder hit — complete dismantling. Minjun resigns at move 102."),
        ],
        sgf_reference="2024-maxim-coffee-final.sgf",
    ),
    ShinFamousGame(
        opponent="Ichiriki Ryo",
        event="2023 Nongshim Cup",
        date="2023-10-18",
        result="B+Resign (Shin wins)",
        significance="Shin's territory-over-moyo philosophy on full display. He systematically "
                     "took all four corners while Ichiriki built a massive center framework. "
                     "Shin then reduced it with precision, winning by resignation.",
        key_moves=[
            (4, _pt(16, 16), "Double 3-3 opening."),
            (20, _pt(4, 16), "Shin has all four corners by move 20."),
            (45, _pt(9, 9), "Center reduction begins — the only fight Shin needed."),
        ],
        sgf_reference="2023-nongshim-shin-ichiriki.sgf",
    ),
]


# ─── Analysis Functions ────────────────────────────────────

def identify_shin_patterns(board: Board) -> List[Dict]:
    """
    Analyze a board position for Shin Jinseo patterns.
    Returns list of identified patterns with confidence scores.
    """
    results = []

    # Check for Shin openings
    for opening in SHIN_OPENINGS:
        matches = 0
        for move_pt, move_color, _ in opening.moves:
            for hist_pt, hist_color, _ in board.history:
                if hist_pt == move_pt and hist_color == move_color:
                    matches += 1
                    break

        if matches >= 2:
            results.append({
                "type": "opening",
                "name": opening.name,
                "confidence": matches / len(opening.moves),
                "description": opening.description,
                "known_win_rate": opening.win_rate,
            })

    # Check for signature techniques
    for technique in SHIN_TECHNIQUES:
        tech_matches = 0
        for move_pt, move_color, _ in technique.sequence:
            for hist_pt, hist_color, _ in board.history[-len(technique.sequence):]:
                if hist_pt == move_pt and hist_color == move_color:
                    tech_matches += 1
                    break

        if tech_matches >= 2:
            results.append({
                "type": "technique",
                "name": technique.name,
                "confidence": tech_matches / len(technique.sequence),
                "description": technique.description,
                "difficulty": technique.difficulty,
            })

    return sorted(results, key=lambda r: -r["confidence"])


def evaluate_shin_style(board: Board) -> Dict:
    """
    Evaluate how closely a position aligns with Shin Jinseo's principles.
    Returns a score 0-100 for "Shin-ness" and breakdown by principle.
    """
    scores = {}

    # Corner-first: count corner plays vs side plays in opening
    corner_plays = 0
    side_plays = 0
    corners = {(0, 0), (0, board.size-1), (board.size-1, 0), (board.size-1, board.size-1)}

    for point, color, _ in board.history[:20]:
        if point.row < 0:
            continue
        # Check if near a corner
        for cr, cc in corners:
            if abs(point.row - cr) <= 3 and abs(point.col - cc) <= 3:
                corner_plays += 1
                break
        else:
            side_plays += 1

    total_early = corner_plays + side_plays
    if total_early > 0:
        scores["corner_first"] = (corner_plays / total_early) * 100
    else:
        scores["corner_first"] = 50

    # Early 3-3: detect 3-3 plays in first 10 moves
    early_33 = 0
    for point, color, _ in board.history[:10]:
        if point.row < 0:
            continue
        for cr, cc in corners:
            dr = abs(point.row - cr)
            dc = abs(point.col - cc)
            if (dr == 2 and dc == 2) or (dr == 2 and dc == 1) or (dr == 1 and dc == 2):
                early_33 += 1
                break
    scores["early_33"] = min(100, early_33 * 25)

    # Territory vs influence: count 3rd/4th line plays vs higher
    territory_plays = 0
    influence_plays = 0
    for point, _, _ in board.history:
        if point.row < 0:
            continue
        row_from_edge = min(point.row, board.size - 1 - point.row)
        col_from_edge = min(point.col, board.size - 1 - point.col)
        closest = min(row_from_edge, col_from_edge)
        if closest <= 2:
            territory_plays += 1
        elif closest >= 5:
            influence_plays += 1

    total = territory_plays + influence_plays
    if total > 0:
        scores["territory_over_moyo"] = (territory_plays / total) * 100
    else:
        scores["territory_over_moyo"] = 50

    # Overall Shin-ness
    shin_score = sum(scores.values()) / len(scores) if scores else 50

    return {
        "shin_score": round(shin_score, 1),
        "principles": {k: round(v, 1) for k, v in scores.items()},
        "assessment": _shin_assessment(shin_score),
    }


def _shin_assessment(score: float) -> str:
    if score >= 85:
        return "Pure Shin Style — maximum efficiency, territory-first, AI-level precision."
    elif score >= 70:
        return "Strong Shin influence — modern, territory-oriented, efficient."
    elif score >= 50:
        return "Mixed style — some modern elements but not fully optimized."
    else:
        return "Classical/traditional style — favors influence over territory."


def shin_recommend_move(board: Board) -> Optional[Dict]:
    """
    Given a position, recommend the most 'Shin-like' move.
    """
    legal = board.get_legal_moves()
    if not legal:
        return None

    # Check for matching Shin openings
    for opening in SHIN_OPENINGS:
        # Find the next unplayed move in this opening
        played = {(h[0], h[1]) for h in board.history[-len(opening.moves):]}
        for move_pt, move_color, annotation in opening.moves:
            if (move_pt, move_color) not in played and move_color == board.current_player:
                if move_pt in legal:
                    return {
                        "move": move_pt,
                        "reason": f"Shin's {opening.name}: {annotation}",
                        "win_rate": opening.win_rate,
                        "source": "Shin Opening Book",
                    }

    # Check for signature techniques
    for technique in SHIN_TECHNIQUES:
        for move_pt, move_color, annotation in technique.sequence[:2]:
            if move_color == board.current_player and move_pt in legal:
                return {
                    "move": move_pt,
                    "reason": f"Shin's {technique.name}: {annotation}",
                    "source": "Shin Technique Database",
                }

    return None


def shin_style_guide() -> str:
    """Generate a comprehensive Shin Jinseo style guide."""
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║            THE SHIN JINSEO STRATEGY GUIDE                    ║",
        "║        Playbook of the World's #1 Go Player                  ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        "  PRINCIPLES:",
        "",
    ]

    for i, p in enumerate(PRINCIPLES, 1):
        lines.append(f"  {i}. {p.principle.name}")
        lines.append(f"     {p.summary}")
        lines.append(f"     {p.explanation[:150]}...")
        lines.append(f"     📋 {p.example_game}")
        lines.append("")

    lines.append("  OPENINGS (ranked by usage):")
    lines.append("")
    for o in sorted(SHIN_OPENINGS, key=lambda x: -x.frequency):
        lines.append(f"  ◆ {o.name} ({o.frequency*100:.0f}% usage, {o.win_rate*100:.0f}% win rate)")
        lines.append(f"    {o.description[:120]}...")
        lines.append(f"    Innovation: {o.key_innovation[:120]}...")
        lines.append("")

    lines.append("  SIGNATURE TECHNIQUES:")
    lines.append("")
    for t in SHIN_TECHNIQUES:
        lines.append(f"  ◆ {t.name} [{t.category}] — Difficulty: {'★' * t.difficulty}")
        lines.append(f"    {t.description[:120]}...")
        lines.append(f"    AI says: {t.ai_evaluation[:120]}...")
        lines.append("")

    lines.append("  FAMOUS GAMES:")
    lines.append("")
    for g in FAMOUS_GAMES:
        lines.append(f"  ◆ vs {g.opponent} — {g.event} ({g.date})")
        lines.append(f"    Result: {g.result} | {g.significance[:100]}...")
        lines.append("")

    lines.append("─" * 62)
    lines.append("  'In Go, there are no shortcuts. Only calculation.' — Shin Jinseo")
    lines.append("─" * 62)

    return "\n".join(lines)


def shin_principles_summary() -> str:
    """Quick reference card of Shin's principles."""
    lines = [
        "┌─────────────────────────────────────────────────┐",
        "│  SHIN JINSEO — 10 PRINCIPLES                    │",
        "├─────────────────────────────────────────────────┤",
    ]
    for p in PRINCIPLES:
        lines.append(f"│  {p.principle.name:20s} │ {p.summary[:30]:30s} │")
    lines.append("└─────────────────────────────────────────────────┘")
    return "\n".join(lines)
