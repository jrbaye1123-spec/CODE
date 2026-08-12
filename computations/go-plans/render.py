"""
Terminal Renderer — beautiful ASCII/Unicode Go board display.

Features:
  - Full board rendering with Unicode stones
  - Territory shading
  - Influence heatmap overlay
  - Coordinate labels
  - Move markers (triangle, circle, square)
  - Last move highlight
  - Compact and large display modes
"""

from __future__ import annotations
from typing import List, Dict, Optional, Set, Tuple
from board import Board, Color, Point

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground colors
BLACK_FG = "\033[30m"
WHITE_FG = "\033[37m"
YELLOW_FG = "\033[33m"
CYAN_FG = "\033[36m"
GREEN_FG = "\033[32m"
RED_FG = "\033[31m"
BLUE_FG = "\033[34m"

# Background colors
BG_BLACK = "\033[40m"
BG_WHITE = "\033[47m"
BG_YELLOW = "\033[43m"
BG_CYAN = "\033[46m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_GRAY = "\033[100m"


# Stone characters
BLACK_STONE = "●"
WHITE_STONE = "○"
STAR_POINT = "╋"
GRID_POINT = "·"
INTERSECTION = "┼"

# Connector characters for larger displays
H_LINE = "─"
V_LINE = "│"
UL_CORNER = "┌"
UR_CORNER = "┐"
LL_CORNER = "└"
LR_CORNER = "┘"
T_DOWN = "┬"
T_UP = "┴"
T_RIGHT = "├"
T_LEFT = "┤"
CROSS = "┼"


def render_board(
    board: Board,
    *,
    last_move: Optional[Point] = None,
    markers: Optional[Dict[Point, str]] = None,
    territory: Optional[Dict[Color, Set[Point]]] = None,
    influence: Optional[List[List[float]]] = None,
    show_coordinates: bool = True,
    compact: bool = False,
    heatmap: bool = False,
) -> str:
    """
    Render a Go board to a terminal string.

    Args:
        board: The board to render.
        last_move: Highlight this point as the most recent move.
        markers: Dict mapping points to marker chars (△, □, ✕, etc.)
        territory: Pre-computed territory sets for shading.
        influence: Influence map for heatmap mode.
        show_coordinates: Show column/row labels.
        compact: Use compact single-character display.
        heatmap: Color-code points by influence.

    Returns:
        String suitable for terminal output.
    """
    lines = []

    # Column labels (top)
    if show_coordinates:
        col_labels = _col_labels(board.size)
        lines.append("    " + "   ".join(col_labels))

    for r in range(board.size):
        row_parts = []

        # Row label
        if show_coordinates:
            row_parts.append(f" {r + 1:2d} ")

        for c in range(board.size):
            p = Point(r, c)
            cell = _render_cell(board, p, last_move, markers, territory)

            if heatmap and influence and board.grid[r][c] is None:
                cell = _influence_color(influence[r][c], cell)

            row_parts.append(cell)

        lines.append("".join(row_parts))

    # Column labels (bottom)
    if show_coordinates:
        lines.append("    " + "   ".join(_col_labels(board.size)))

    return "\n".join(lines)


def _col_labels(size: int) -> List[str]:
    """Generate column labels A-T (skipping I)."""
    labels = []
    for c in range(size):
        ch = chr(ord('A') + c)
        if c >= 8:  # skip I
            ch = chr(ord('A') + c + 1)
        labels.append(ch)
    return labels


def _render_cell(
    board: Board,
    point: Point,
    last_move: Optional[Point],
    markers: Optional[Dict[Point, str]],
    territory: Optional[Dict[Color, Set[Point]]],
) -> str:
    """Render a single cell of the board."""
    r, c = point.row, point.col
    stone = board.grid[r][c]

    # Background shading for territory
    bg = ""
    if territory:
        for color, points in territory.items():
            if point in points:
                bg = _territory_bg(color)
                break

    if stone is not None:
        char = BLACK_STONE if stone == Color.BLACK else WHITE_STONE
        fg = WHITE_FG if stone == Color.BLACK else BLACK_FG

        # Last move highlight
        if last_move and point == last_move:
            return f"{bg}{YELLOW_FG}{BOLD}[{char}]{RESET}"

        return f"{bg}{fg} {char} {RESET}"

    # Empty point
    if markers and point in markers:
        char = markers[point]
        return f"{bg}{DIM}{char}{RESET}"

    # Star point
    star_points = _get_star_points(board.size)
    if (r, c) in star_points:
        return f"{bg}{DIM} ╋ {RESET}"

    return f"{bg}{DIM} · {RESET}"


def _territory_bg(color: Color) -> str:
    """Get background color for territory."""
    if color == Color.BLACK:
        return "\033[48;5;236m"  # dark gray
    else:
        return "\033[48;5;252m"  # light gray


def _influence_color(value: float, char: str) -> str:
    """Color a cell based on influence value."""
    if abs(value) < 0.1:
        return f"{DIM}{char}{RESET}"

    if value > 0:
        # Black influence: blue gradient
        intensity = min(abs(value) * 100, 80)
        return f"\033[38;5;{int(20 + intensity)}m{char}{RESET}"
    else:
        # White influence: warm gradient
        intensity = min(abs(value) * 100, 80)
        return f"\033[38;5;{int(200 + intensity / 2)}m{char}{RESET}"


def render_compact(
    board: Board,
    last_move: Optional[Point] = None,
    markers: Optional[Dict[Point, str]] = None,
) -> str:
    """Compact single-char-per-cell board for small terminals."""
    return render_board(
        board,
        last_move=last_move,
        markers=markers,
        compact=True,
    )


def render_influence(board: Board, influence: List[List[float]]) -> str:
    """Render board with influence heatmap overlay."""
    return render_board(
        board,
        influence=influence,
        heatmap=True,
    )


def render_with_annotations(
    board: Board,
    key_points: List[Tuple[Point, str, str]],  # (point, label, description)
    last_move: Optional[Point] = None,
) -> str:
    """
    Render board with annotated key points and a legend.

    key_points: list of (Point, "A"/"B"/..., "description")
    """
    markers = {kp[0]: kp[1] for kp in key_points}
    board_str = render_board(board, last_move=last_move, markers=markers)

    legend = []
    for pt, label, desc in key_points:
        legend.append(f"  {BOLD}{label}{RESET} — {pt.label()} : {desc}")

    return board_str + "\n\n" + "\n".join(legend)


def render_move_preview(board: Board, move: Point, color: Color,
                        description: str = "") -> str:
    """Preview how a move would look on the board."""
    # Create a copy and play the move
    preview = Board(size=board.size, komi=board.komi)
    preview.grid = [row[:] for row in board.grid]
    preview.current_player = color
    preview.captures = board.captures.copy()

    # Temporarily place the stone for display
    preview.grid[move.row][move.col] = color
    preview._recompute_groups()

    markers = {}
    # Show captured stones
    opponent = color.opponent
    for neighbor in preview.get_neighbors(move):
        if preview.at(neighbor) == opponent:
            if neighbor in preview.groups and preview.groups[neighbor].num_liberties == 0:
                for stone in preview.groups[neighbor].stones:
                    markers[stone] = f"{RED_FG}✕{RESET}"

    board_str = render_board(preview, last_move=move, markers=markers)

    lines = [f"  Preview: {color} at {move.label()}"]
    if description:
        lines.append(f"  {description}")
    lines.append(board_str)

    return "\n".join(lines)


def _get_star_points(size: int) -> Set[Tuple[int, int]]:
    """Return star points for the given board size."""
    if size == 9:
        return {(2, 2), (2, 6), (4, 4), (6, 2), (6, 6)}
    elif size == 13:
        return {(3, 3), (3, 6), (3, 9), (6, 3), (6, 6), (6, 9),
                (9, 3), (9, 6), (9, 9)}
    else:  # 19x19
        return {(3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15),
                (15, 3), (15, 9), (15, 15)}


def render_game_info(board: Board, black_name: str = "Black",
                     white_name: str = "White") -> str:
    """Render game info header."""
    captures_b = board.captures[Color.BLACK]
    captures_w = board.captures[Color.WHITE]

    lines = [
        f"  {BOLD}● {black_name:20s}{RESET}  vs  {BOLD}○ {white_name:20s}{RESET}",
        f"  Move: {board.move_number}  |  {'●' if board.current_player == Color.BLACK else '○'} to play",
        f"  Captures — Black: {captures_b}  White: {captures_w}  |  Komi: {board.komi}",
        "",
    ]
    return "\n".join(lines)
