"""Pure game logic. Must not import gui, solver or analysis."""
from minesweeper.core.board import Board, Cell, neighbors
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, GameStats, PlayerView, RevealResult, Status

__all__ = [
    "Board", "Cell", "neighbors",
    "PRESETS", "FirstClick", "FloodFill", "GameConfig",
    "CellState", "Game", "GameStats", "PlayerView", "RevealResult", "Status",
]
