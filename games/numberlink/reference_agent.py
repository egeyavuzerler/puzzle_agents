"""
games/numberlink/reference_agent.py

Numberlink icin referans generator + solver.

Uretim stratejisi: her renk icin, "kendi kendine degmeyen" bir yolu GREEDY
(geri donussuz) rastgele buyuterek olustur. Bir deneme yetersiz uzunlukta
bir renk uretirse (ya da tikanirsa) TUM uretimi bastan dener.
"""

import random
from collections import defaultdict

from core.base import SolveResult


def _neighbors(cell, rows, cols):
    r, c = cell
    result = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            result.append((nr, nc))
    return result


def _grow_path_greedy(rng, start, occupied, rows, cols, target_length):
    path = [start]
    used = {start}
    while len(path) < target_length:
        candidates = []
        for cand in _neighbors(path[-1], rows, cols):
            if cand in occupied or cand in used:
                continue
            ok = True
            for nb in _neighbors(cand, rows, cols):
                if (nb in used or nb in occupied) and nb != path[-1]:
                    ok = False
                    break
            if ok:
                candidates.append(cand)
        if not candidates:
            break
        nxt = rng.choice(candidates)
        path.append(nxt)
        used.add(nxt)
    return path


def _try_generate_once(rng, rows, cols, n_colors, min_len):
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    occupied = set()
    colors = []
    max_len = max(min_len, (rows * cols) // n_colors)

    for _color_id in range(n_colors):
        candidates_start = [c for c in all_cells if c not in occupied]
        if not candidates_start:
            return None
        start = rng.choice(candidates_start)
        target_length = rng.randint(min_len, max_len)
        path = _grow_path_greedy(rng, start, occupied, rows, cols, target_length)
        if len(path) < 2:
            return None
        colors.append(path)
        occupied.update(path)

    endpoints = []
    solution_grid = [[None] * cols for _ in range(rows)]
    for color_id, seg in enumerate(colors):
        endpoints.append({"color": color_id, "pos": list(seg[0])})
        endpoints.append({"color": color_id, "pos": list(seg[-1])})
        for (r, c) in seg:
            solution_grid[r][c] = color_id
    puzzle = {"game": "numberlink", "size": [rows, cols], "endpoints": endpoints}
    return puzzle, solution_grid


def generate_numberlink(rng: random.Random, difficulty: int, max_attempts: int = 150):
    rows = cols = 8
    n_colors = min(4 + difficulty // 2, 10)
    min_len = 3

    for _ in range(max_attempts):
        puzzle = _try_generate_once(rng, rows, cols, n_colors, min_len)
        if puzzle is not None:
            return puzzle
    raise RuntimeError(f"{max_attempts} denemede gecerli numberlink puzzle uretilemedi")


def solve_numberlink(puzzle: dict, time_limit_s: float = 30.0, max_expansions: int = 200000,
                      on_step=None) -> SolveResult:
    """
    on_step verilirse her hucre push/pop'unda on_step(grid_snapshot, event)
    cagrilir -- canli gorsellestirme icin.
    """
    rows, cols = puzzle["size"]
    endpoints = puzzle["endpoints"]
    ep_by_color = defaultdict(list)
    for e in endpoints:
        ep_by_color[e["color"]].append(tuple(e["pos"]))

    colors = sorted(
        ep_by_color.keys(),
        key=lambda c: abs(ep_by_color[c][0][0] - ep_by_color[c][1][0]) + abs(ep_by_color[c][0][1] - ep_by_color[c][1][1]),
    )

    occupied = {}
    for c in colors:
        for p in ep_by_color[c]:
            occupied[p] = c

    color_grid = [[None] * cols for _ in range(rows)]

    def emit(event):
        if on_step:
            on_step([row[:] for row in color_grid], event)

    result_paths = {}
    expansions = [0]

    def find_path(color, start, end):
        path = [start]
        used = {start}
        color_grid[start[0]][start[1]] = color
        emit("push")

        def backtrack():
            expansions[0] += 1
            if expansions[0] > max_expansions:
                return False
            if path[-1] == end:
                return True
            cands = []
            for nb in _neighbors(path[-1], rows, cols):
                if nb != end and (nb in occupied or nb in used):
                    continue
                ok = True
                for nb2 in _neighbors(nb, rows, cols):
                    if (nb2 in used or (nb2 in occupied and nb2 != end)) and nb2 != path[-1]:
                        ok = False
                        break
                if ok:
                    cands.append(nb)
            for cand in cands:
                path.append(cand)
                used.add(cand)
                color_grid[cand[0]][cand[1]] = color
                emit("push")
                if backtrack():
                    return True
                path.pop()
                used.discard(cand)
                color_grid[cand[0]][cand[1]] = None
                emit("pop")
            return False

        return path if backtrack() else None

    for color in colors:
        start, end = ep_by_color[color]
        del occupied[start]
        if end in occupied:
            del occupied[end]
        path = find_path(color, start, end)
        occupied[start] = color
        occupied[end] = color
        if path is None:
            return SolveResult(solved=False, error=f"renk {color} icin yol bulunamadi (acgozlu siralama yetersiz kaldi)")
        result_paths[color] = path
        for cell in path:
            occupied[cell] = color

    for color, path in result_paths.items():
        for (r, c) in path:
            color_grid[r][c] = color

    return SolveResult(solved=True, solution=color_grid)
