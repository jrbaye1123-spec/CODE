"""
SGF Parser — Smart Game Format reader/writer for Go.

Handles the SGF (FF[4]) specification for Go game records.
Supports:
  - Full game tree parsing
  - Multi-branch games (variations)
  - Comments and annotations
  - Export to SGF with variations
"""

from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from board import Board, Color, Point


@dataclass
class SGFNode:
    """A node in an SGF game tree (represents a position)."""
    properties: Dict[str, List[str]] = field(default_factory=dict)
    children: List[SGFNode] = field(default_factory=list)
    parent: Optional[SGFNode] = None
    move_number: int = 0

    def get(self, prop: str, default: Any = None) -> Optional[List[str]]:
        return self.properties.get(prop, default)

    def get_first(self, prop: str, default: Any = None) -> Optional[str]:
        vals = self.properties.get(prop)
        return vals[0] if vals else default

    def set(self, prop: str, values: List[str]) -> None:
        self.properties[prop] = values


@dataclass
class SGFGame:
    """A complete SGF game with metadata and game tree."""
    root: SGFNode
    size: int = 19
    komi: float = 6.5
    result: str = ""
    black_player: str = ""
    white_player: str = ""
    date: str = ""
    event: str = ""
    comment: str = ""

    @property
    def moves(self) -> List[Tuple[Optional[Point], Color, Optional[str]]]:
        """
        Extract all moves in the main line.
        Returns list of (point, color, comment).
        Pass moves have point=None.
        """
        moves = []
        node = self.root
        move_count = 0

        while node:
            for prop in ["B", "W"]:
                if prop in node.properties:
                    color = Color.BLACK if prop == "B" else Color.WHITE
                    coord = node.properties[prop][0]
                    if coord == "" or coord == "tt":
                        point = None  # pass
                    else:
                        point = _sgf_to_point(coord, self.size)
                    comment = node.get_first("C")
                    moves.append((point, color, comment))
                    move_count += 1

            if node.children:
                node = node.children[0]  # follow main line
            else:
                break

        return moves

    def to_board(self) -> Board:
        """Replay the game onto a Board object."""
        board = Board(size=self.size, komi=self.komi)
        for point, color, _ in self.moves:
            board.play(point)
        return board


def _point_to_sgf(point: Optional[Point], size: int) -> str:
    """Convert Point to SGF coordinate string."""
    if point is None:
        return ""  # pass
    col = chr(ord('a') + point.col)
    row = chr(ord('a') + (size - 1 - point.row))
    return f"{col}{row}"


def _sgf_to_point(sgf_coord: str, size: int) -> Point:
    """Convert SGF coordinate string to Point."""
    if len(sgf_coord) < 2:
        raise ValueError(f"Invalid SGF coordinate: {sgf_coord}")
    col = ord(sgf_coord[0]) - ord('a')
    row = size - 1 - (ord(sgf_coord[1]) - ord('a'))
    return Point(row, col)


def parse_sgf(sgf_text: str) -> SGFGame:
    """
    Parse an SGF string into an SGFGame object.
    Handles FF[4] Go game records.
    """
    sgf_text = sgf_text.strip()

    if not (sgf_text.startswith("(") and sgf_text.endswith(")")):
        raise ValueError("Invalid SGF: must be enclosed in parentheses")

    # Remove outer parentheses and parse
    # Find the game tree
    game = SGFGame(root=SGFNode())
    _parse_node(sgf_text[1:-1].strip(), game.root)

    # Extract metadata
    game.size = int(game.root.get_first("SZ", "19"))
    game.komi = float(game.root.get_first("KM", "6.5"))
    game.result = game.root.get_first("RE", "")
    game.black_player = game.root.get_first("PB", "Black")
    game.white_player = game.root.get_first("PW", "White")
    game.date = game.root.get_first("DT", "")
    game.event = game.root.get_first("EV", "")
    game.comment = game.root.get_first("C", "")

    return game


def _parse_node(text: str, node: SGFNode) -> str:
    """
    Parse an SGF node. Returns remaining text after node and its subtree.
    A node is: ;Prop[Value]Prop[Value]...
    Bare ; nodes that follow form a main-line chain (parent->child).
    Parenthesized (...) nodes are variations (siblings in the tree).
    """
    text = text.strip()

    if not text.startswith(";"):
        return text

    # Skip the semicolon
    text = text[1:].strip()

    # Parse properties until we see ; ( ) or end
    while text and text[0] not in ";)":
        # Read property name (uppercase letters)
        prop_end = 0
        while prop_end < len(text) and text[prop_end].isupper():
            prop_end += 1
        prop_name = text[:prop_end]
        text = text[prop_end:].strip()

        # Read values (one or more [value] pairs)
        values = []
        while text and text[0] == "[":
            # Find matching ]
            depth = 1
            i = 1
            while i < len(text) and depth > 0:
                if text[i] == "[":
                    depth += 1
                elif text[i] == "]":
                    depth -= 1
                if text[i] == "\\" and i + 1 < len(text):
                    i += 1  # skip escaped char
                i += 1
            value = text[1:i-1]
            values.append(value)
            text = text[i:].strip()

        if values:
            node.properties[prop_name] = values

    # Parse children. Two kinds:
    #   ( ... )  = variation (sibling), parsed as child then we
    #              continue at this level
    #   ; ...    = next move in main line (chained as child), and
    #              we stop at this level (the chain continues down)

    while text and text[0] == "(":
        # Find matching )
        depth = 1
        i = 1
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        child_text = text[1:i-1]
        text = text[i:].strip()
        child = SGFNode(parent=node)
        node.children.append(child)
        _parse_node(child_text, child)

    # Chain: next bare ; becomes the main-line child
    if text and text[0] == ";":
        child = SGFNode(parent=node)
        node.children.append(child)
        text = _parse_node(text, child)

    return text


def export_sgf(game: SGFGame) -> str:
    """Export an SGFGame to SGF string."""
    return f"({_node_to_sgf(game.root)})"


def _node_to_sgf(node: SGFNode) -> str:
    """Convert an SGFNode to SGF string."""
    parts = [";"]
    for prop, values in node.properties.items():
        parts.append(prop)
        for v in values:
            parts.append(f"[{v}]")
    for child in node.children:
        parts.append(f"({_node_to_sgf(child)})")
    return "".join(parts)


def board_to_sgf(board: Board, black_name: str = "Black",
                 white_name: str = "White", result: str = "",
                 event: str = "") -> str:
    """Export a Board's move history as SGF."""
    node = SGFNode()
    node.set("SZ", [str(board.size)])
    node.set("KM", [str(board.komi)])
    node.set("PB", [black_name])
    node.set("PW", [white_name])
    if result:
        node.set("RE", [result])
    if event:
        node.set("EV", [event])

    current = node
    for point, color, _ in board.history:
        prop = "B" if color == Color.BLACK else "W"
        sgf_coord = _point_to_sgf(point if point.row >= 0 else None, board.size)
        child = SGFNode(parent=current)
        child.set(prop, [sgf_coord])
        current.children.append(child)
        current = child

    game = SGFGame(root=node)
    return export_sgf(game)


def sgf_from_moves(moves: List[Tuple[str, str]], size: int = 19,
                   komi: float = 6.5) -> str:
    """
    Create SGF from a list of ("B"/"W", "D4"/"Q16"/"pass") move strings.
    """
    node = SGFNode()
    node.set("SZ", [str(size)])
    node.set("KM", [str(komi)])

    current = node
    for color_str, coord in moves:
        if color_str not in ("B", "W"):
            continue

        sgf_coord = ""
        if coord.lower() != "pass":
            col = ord(coord[0].upper()) - ord('A')
            if col >= 8:  # skip I
                col -= 1
            row = int(coord[1:]) - 1
            sgf_coord = _point_to_sgf(Point(size - 1 - row, col), size)

        child = SGFNode(parent=current)
        child.set(color_str, [sgf_coord])
        current.children.append(child)
        current = child

    game = SGFGame(root=node)
    return export_sgf(game)
