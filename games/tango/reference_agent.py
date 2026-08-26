"""
games/tango/reference_agent.py

Tango icin referans generator + solver.
"""

import random

from core.base import SolveResult


def _tango_full_board(rows: int, cols: int, blocked: set, rng: random.Random):
    board = [[None] * cols for _ in range(rows)]
    for (r, c) in blocked:
        board[r][c] = "blocked"

    row_target = [(cols - sum(1 for c in range(cols) if (r, c) in blocked)) // 2 for r in range(rows)]
    col_target = [(rows - sum(1 for r in range(rows) if (r, c) in blocked)) // 2 for c in range(cols)]

    free_cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in blocked]

    def valid(r, c, val):
        suns_row = sum(1 for cc in range(cols) if board[r][cc] == "sun")
        moons_row = sum(1 for cc in range(cols) if board[r][cc] == "moon")
        if val == "sun" and suns_row >= row_target[r]:
            return False
        if val == "moon" and moons_row >= row_target[r]:
            return False
        suns_col = sum(1 for rr in range(rows) if board[rr][c] == "sun")
        moons_col = sum(1 for rr in range(rows) if board[rr][c] == "moon")
        if val == "sun" and suns_col >= col_target[c]:
            return False
        if val == "moon" and moons_col >= col_target[c]:
            return False
        if c >= 2 and board[r][c - 1] == val and board[r][c - 2] == val:
            return False
        if r >= 2 and board[r - 1][c] == val and board[r - 2][c] == val:
            return False
        return True

    def backtrack(i):
        if i == len(free_cells):
            return True
        r, c = free_cells[i]
        vals = ["sun", "moon"]
        rng.shuffle(vals)
        for val in vals:
            if valid(r, c, val):
                board[r][c] = val
                if backtrack(i + 1):
                    return True
                board[r][c] = None
        return False

    if not backtrack(0):
        raise RuntimeError(f"{rows}x{cols} tango tahtasi (bloklu) uretilemedi")
    return board


def solve_tango_backtrack(puzzle: dict, on_step=None) -> SolveResult:
    rows, cols = puzzle["size"]
    blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
    prefilled = {tuple(cell["pos"]): cell["value"] for cell in puzzle.get("prefilled", [])}
    constraints_by_cell = {}
    for con in puzzle.get("constraints", []):
        c1, c2 = tuple(con["cell1"]), tuple(con["cell2"])
        constraints_by_cell.setdefault(c1, []).append((c2, con["type"]))
        constraints_by_cell.setdefault(c2, []).append((c1, con["type"]))

    grid = [[None] * cols for _ in range(rows)]
    for (r, c) in blocked:
        grid[r][c] = "blocked"

    row_target = [(cols - sum(1 for c in range(cols) if (r, c) in blocked)) // 2 for r in range(rows)]
    col_target = [(rows - sum(1 for r in range(rows) if (r, c) in blocked)) // 2 for c in range(cols)]

    free_cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in blocked]

    def valid(r, c, val):
        suns_row = sum(1 for cc in range(cols) if grid[r][cc] == "sun")
        moons_row = sum(1 for cc in range(cols) if grid[r][cc] == "moon")
        if val == "sun" and suns_row >= row_target[r]:
            return False
        if val == "moon" and moons_row >= row_target[r]:
            return False
        suns_col = sum(1 for rr in range(rows) if grid[rr][c] == "sun")
        moons_col = sum(1 for rr in range(rows) if grid[rr][c] == "moon")
        if val == "sun" and suns_col >= col_target[c]:
            return False
        if val == "moon" and moons_col >= col_target[c]:
            return False
        if c >= 2 and grid[r][c - 1] == val and grid[r][c - 2] == val:
            return False
        if r >= 2 and grid[r - 1][c] == val and grid[r - 2][c] == val:
            return False
        for (other_pos, ctype) in constraints_by_cell.get((r, c), []):
            other_val = grid[other_pos[0]][other_pos[1]]
            if other_val is None:
                continue
            if ctype == "equal" and other_val != val:
                return False
            if ctype == "opposite" and other_val == val:
                return False
        return True

    def backtrack(i):
        if i == len(free_cells):
            return True
        r, c = free_cells[i]
        if (r, c) in prefilled:
            val = prefilled[(r, c)]
            if not valid(r, c, val):
                return False
            grid[r][c] = val
            if on_step:
                on_step([row[:] for row in grid], "push")
            if backtrack(i + 1):
                return True
            grid[r][c] = None
            if on_step:
                on_step([row[:] for row in grid], "pop")
            return False

        for val in ("sun", "moon"):
            if valid(r, c, val):
                grid[r][c] = val
                if on_step:
                    on_step([row[:] for row in grid], "push")
                if backtrack(i + 1):
                    return True
                grid[r][c] = None
                if on_step:
                    on_step([row[:] for row in grid], "pop")
        return False

    if backtrack(0):
        return SolveResult(solved=True, solution=[row[:] for row in grid])
    return SolveResult(solved=False, error="backtracking ile cozum bulunamadi")


def solve_tango(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_tango_backtrack(puzzle)


def generate_tango(rng: random.Random, difficulty: int) -> dict:
    rows = cols = 10

    n_blocks = 1 + difficulty // 4
    blocked = set()
    attempts = 0
    while len(blocked) < n_blocks * 4 and attempts < 200:
        attempts += 1
        br = rng.randint(0, rows - 2)
        bc = rng.randint(0, cols - 2)
        candidate = {(br, bc), (br, bc + 1), (br + 1, bc), (br + 1, bc + 1)}
        if candidate & blocked:
            continue
        blocked |= candidate

    board = _tango_full_board(rows, cols, blocked, rng)

    free_cells_list = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in blocked]
    n_prefilled = max(3, 14 - difficulty)
    n_constraints = max(2, 8 - difficulty // 2)

    rng.shuffle(free_cells_list)
    prefilled_cells = free_cells_list[:n_prefilled]
    prefilled = [{"pos": [r, c], "value": board[r][c]} for r, c in prefilled_cells]

    adjacent_pairs = []
    for r in range(rows):
        for c in range(cols):
            if (r, c) in blocked:
                continue
            if c + 1 < cols and (r, c + 1) not in blocked:
                adjacent_pairs.append(((r, c), (r, c + 1)))
            if r + 1 < rows and (r + 1, c) not in blocked:
                adjacent_pairs.append(((r, c), (r + 1, c)))
    rng.shuffle(adjacent_pairs)
    constraints = []
    for (p1, p2) in adjacent_pairs[:n_constraints]:
        v1, v2 = board[p1[0]][p1[1]], board[p2[0]][p2[1]]
        ctype = "equal" if v1 == v2 else "opposite"
        constraints.append({"cell1": list(p1), "cell2": list(p2), "type": ctype})

    puzzle = {
        "game": "tango",
        "size": [rows, cols],
        "blocked_cells": [list(c) for c in blocked],
        "prefilled": prefilled,
        "constraints": constraints,
    }
    solution = [row[:] for row in board]  # tam dolu tahta -- witness cozum
    return puzzle, solution
