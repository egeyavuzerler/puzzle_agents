"""
games/yinyang/reference_agent.py

Yin-Yang icin referans generator + solver.

Uretim stratejisi: 2 tohum hucreden (biri siyah biri beyaz) MRV
(en az secenekli hucreyi once doldur) sirali backtracking ile TAM bir
gecerli boyama insa et, sonra cogunu gizle. NOT: 6x6 ve ustunde bu
yontem pratikte tikaniyor, bu yuzden sabit 5x5 kullaniyoruz.
"""

import random

from core.base import SolveResult


def _would_violate(grid, rows, cols, cell, color):
    r, c = cell
    grid[r][c] = color
    bad = False
    for dr, dc in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
        r0, c0 = r + dr, c + dc
        if 0 <= r0 and r0 + 1 < rows and 0 <= c0 and c0 + 1 < cols:
            block = [grid[r0][c0], grid[r0 + 1][c0], grid[r0][c0 + 1], grid[r0 + 1][c0 + 1]]
            if all(b is not None for b in block) and len(set(block)) == 1:
                bad = True
                break
    grid[r][c] = None
    return bad


def _neighbors(cell, rows, cols):
    r, c = cell
    return [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= r + dr < rows and 0 <= c + dc < cols]


def _build_full_board(rng, rows, cols, max_nodes=5000):
    grid = [[None] * cols for _ in range(rows)]
    total = rows * cols
    nodes = [0]

    def frontier_cells():
        f = set()
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] is not None:
                    for nb in _neighbors((r, c), rows, cols):
                        if grid[nb[0]][nb[1]] is None:
                            f.add(nb)
        return f

    colored = [2]

    def backtrack():
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if colored[0] == total:
            return True
        frontier = frontier_cells()
        if not frontier:
            return False
        options = {}
        for cell in frontier:
            valid_colors = [
                col for col in ("black", "white")
                if not _would_violate(grid, rows, cols, cell, col)
                and any(grid[nb[0]][nb[1]] == col for nb in _neighbors(cell, rows, cols))
            ]
            if valid_colors:
                options[cell] = valid_colors
        if not options:
            return False
        best_cell = min(options.keys(), key=lambda c: len(options[c]))
        colors = list(options[best_cell])
        rng.shuffle(colors)
        for color in colors:
            grid[best_cell[0]][best_cell[1]] = color
            colored[0] += 1
            if backtrack():
                return True
            grid[best_cell[0]][best_cell[1]] = None
            colored[0] -= 1
        return False

    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    seed_black = rng.choice(all_cells)
    remaining = [c for c in all_cells if c != seed_black]
    seed_white = rng.choice(remaining)
    grid[seed_black[0]][seed_black[1]] = "black"
    grid[seed_white[0]][seed_white[1]] = "white"

    if backtrack():
        return grid
    return None


def _validate_full_board(grid, rows, cols):
    for color in ("black", "white"):
        cells = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == color]
        if not cells:
            return False
        cellset = set(cells)
        start = cells[0]
        visited = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            for nb in _neighbors(u, rows, cols):
                if nb in cellset and nb not in visited:
                    visited.add(nb)
                    stack.append(nb)
        if len(visited) != len(cells):
            return False
    for r in range(rows - 1):
        for c in range(cols - 1):
            vals = {grid[r][c], grid[r + 1][c], grid[r][c + 1], grid[r + 1][c + 1]}
            if len(vals) == 1:
                return False
    return True


def generate_yinyang(rng: random.Random, difficulty: int, max_attempts: int = 2000) -> dict:
    rows = cols = 5

    full = None
    for _ in range(max_attempts):
        candidate = _build_full_board(rng, rows, cols)
        if candidate is not None and _validate_full_board(candidate, rows, cols):
            full = candidate
            break
    if full is None:
        raise RuntimeError(f"{max_attempts} denemede gecerli yinyang tahtasi uretilemedi")

    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    reveal_frac = max(0.15, 0.5 - difficulty * 0.03)
    n_reveal = max(3, int(len(all_cells) * reveal_frac))
    rng.shuffle(all_cells)
    prefilled = [{"pos": [r, c], "color": full[r][c]} for (r, c) in all_cells[:n_reveal]]

    puzzle = {"game": "yinyang", "size": [rows, cols], "prefilled": prefilled}
    solution = [row[:] for row in full]  # tam gecerli tahta -- witness cozum
    return puzzle, solution


def solve_yinyang_backtrack(puzzle: dict, on_step=None, max_nodes: int = 200000) -> SolveResult:
    rows, cols = puzzle["size"]
    prefilled = {tuple(c["pos"]): c["color"] for c in puzzle.get("prefilled", [])}
    grid = [[None] * cols for _ in range(rows)]
    for (r, c), color in prefilled.items():
        grid[r][c] = color

    undecided = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in prefilled]
    nodes = [0]

    def connectivity_ok():
        for color in ("black", "white"):
            cells = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == color]
            if not cells:
                return False
            cellset = set(cells)
            start = cells[0]
            visited = {start}
            stack = [start]
            while stack:
                u = stack.pop()
                for nb in _neighbors(u, rows, cols):
                    if nb in cellset and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            if len(visited) != len(cells):
                return False
        return True

    def backtrack(idx):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if idx == len(undecided):
            return connectivity_ok()
        r, c = undecided[idx]
        for color in ("black", "white"):
            if not _would_violate(grid, rows, cols, (r, c), color):
                grid[r][c] = color
                if on_step:
                    on_step([row[:] for row in grid], "push")
                if backtrack(idx + 1):
                    return True
                grid[r][c] = None
                if on_step:
                    on_step([row[:] for row in grid], "pop")
        return False

    if backtrack(0):
        return SolveResult(solved=True, solution=[row[:] for row in grid])
    reason = "max_nodes sinirina takildi" if nodes[0] > max_nodes else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_yinyang(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_yinyang_backtrack(puzzle)
