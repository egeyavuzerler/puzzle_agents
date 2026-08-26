"""
games/tapa/reference_agent.py

Tapa icin referans generator + solver.

Uretim stratejisi: once rastgele bir boyali bolge buyut (2x2-yasak
kontrolu ile), sonra bolgeye komsu olan hucrelerin bir kismini clue
olarak sec ve gercek komsuluk desenlerinden numaralarini turet.
"""

import random
from collections import deque

from core.base import SolveResult

_CLOCKWISE_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


def _ordered_neighbors(pos, rows, cols):
    r, c = pos
    result = []
    for dr, dc in _CLOCKWISE_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            result.append((nr, nc))
    return result


def _cyclic_runs(bool_list):
    n = len(bool_list)
    if n == 0:
        return []
    if all(bool_list):
        return [n]
    if not any(bool_list):
        return []
    start = bool_list.index(False)
    rotated = bool_list[start:] + bool_list[:start]
    runs = []
    cur = 0
    for v in rotated:
        if v:
            cur += 1
        else:
            if cur > 0:
                runs.append(cur)
            cur = 0
    if cur > 0:
        runs.append(cur)
    return runs


def _is_cyclic_rotation(a, b):
    if len(a) != len(b):
        return False
    if not a:
        return True
    doubled = a + a
    for i in range(len(a)):
        if doubled[i:i + len(a)] == b:
            return True
    return False


def _grow_shaded(rng, rows, cols, target_size):
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    start = rng.choice(all_cells)
    shaded = {start}
    frontier = set()

    def add_frontier(cell):
        r, c = cell
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (r + dr, c + dc)
            if 0 <= nb[0] < rows and 0 <= nb[1] < cols and nb not in shaded:
                frontier.add(nb)

    add_frontier(start)

    def would_make_2x2(cell):
        combined = shaded | {cell}
        r, c = cell
        for dr, dc in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
            r0, c0 = r + dr, c + dc
            block = {(r0, c0), (r0 + 1, c0), (r0, c0 + 1), (r0 + 1, c0 + 1)}
            if block.issubset(combined):
                return True
        return False

    attempts = 0
    while len(shaded) < target_size and frontier and attempts < target_size * 20:
        attempts += 1
        cell = rng.choice(list(frontier))
        frontier.discard(cell)
        if would_make_2x2(cell):
            continue
        shaded.add(cell)
        add_frontier(cell)
    return shaded


def _validate_shaded(rows, cols, shaded):
    if not shaded:
        return False, "bos"
    start = next(iter(shaded))
    visited = {start}
    q = deque([start])
    while q:
        u = q.popleft()
        r, c = u
        for nb in [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]:
            if nb in shaded and nb not in visited:
                visited.add(nb)
                q.append(nb)
    if len(visited) != len(shaded):
        return False, "bagli degil"
    for r in range(rows - 1):
        for c in range(cols - 1):
            if all((r + dr, c + dc) in shaded for dr in (0, 1) for dc in (0, 1)):
                return False, f"2x2 dolu ({r},{c})"
    return True, None


def _make_clue_numbers(pos, shaded, rows, cols):
    nbs = _ordered_neighbors(pos, rows, cols)
    bools = [nb in shaded for nb in nbs]
    runs = _cyclic_runs(bools)
    return runs if runs else [0]


def generate_tapa(rng: random.Random, difficulty: int, max_attempts: int = 30) -> dict:
    rows = cols = 10

    for _ in range(max_attempts):
        target = rng.randint(rows * cols // 3, rows * cols // 2)
        shaded = _grow_shaded(rng, rows, cols, target)
        ok, _err = _validate_shaded(rows, cols, shaded)
        if not ok:
            continue

        unshaded = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in shaded]
        reveal_frac = max(0.30, 0.75 - difficulty * 0.04)
        n_reveal = max(4, int(len(unshaded) * reveal_frac))
        rng.shuffle(unshaded)
        chosen = unshaded[:n_reveal]

        clues = []
        for cell in chosen:
            numbers = _make_clue_numbers(cell, shaded, rows, cols)
            clues.append({"pos": list(cell), "numbers": numbers})

        puzzle = {"game": "tapa", "size": [rows, cols], "clues": clues}
        solution = [list(cell) for cell in shaded]  # witness cozum
        return puzzle, solution

    raise RuntimeError(f"{max_attempts} denemede gecerli tapa puzzle uretilemedi")


def solve_tapa_backtrack(puzzle: dict, on_step=None, max_nodes: int = 300000) -> SolveResult:
    rows, cols = puzzle["size"]
    clue_positions = {tuple(c["pos"]): c["numbers"] for c in puzzle["clues"]}
    clue_set = set(clue_positions.keys())

    all_cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in clue_set]

    def clue_adjacency_count(cell):
        return sum(1 for nb in _ordered_neighbors(cell, rows, cols) if nb in clue_set)

    all_cells.sort(key=lambda c: -clue_adjacency_count(c))

    state = {}
    nodes = [0]
    clue_neighbors = {pos: _ordered_neighbors(pos, rows, cols) for pos in clue_set}

    def would_make_2x2(cell, val):
        if not val:
            return False
        r, c = cell
        state[cell] = True
        bad = False
        for dr, dc in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
            r0, c0 = r + dr, c + dc
            if 0 <= r0 and r0 + 1 < rows and 0 <= c0 and c0 + 1 < cols:
                cells4 = [(r0, c0), (r0 + 1, c0), (r0, c0 + 1), (r0 + 1, c0 + 1)]
                ok = True
                vals = []
                for cc in cells4:
                    if cc in clue_set:
                        ok = False
                        break
                    v = state.get(cc)
                    if v is None:
                        ok = False
                        break
                    vals.append(v)
                if ok and all(vals):
                    bad = True
                    break
        del state[cell]
        return bad

    def clue_check(pos, allow_partial=True):
        nbs = clue_neighbors[pos]
        vals = [False if nb in clue_set else state.get(nb) for nb in nbs]
        if all(v is not None for v in vals):
            bools = [bool(v) for v in vals]
            runs = _cyclic_runs(bools)
            expected = clue_positions[pos]
            if not runs:
                return expected == [0]
            return _is_cyclic_rotation(runs, expected)
        if not allow_partial:
            return True
        shaded_count = sum(1 for v in vals if v is True)
        max_needed = sum(clue_positions[pos])
        return shaded_count <= max_needed

    def backtrack(idx):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if idx == len(all_cells):
            for pos in clue_set:
                if not clue_check(pos, allow_partial=False):
                    return False
            shaded_cells = {c for c, v in state.items() if v}
            if not shaded_cells:
                return False
            start = next(iter(shaded_cells))
            visited = {start}
            stack = [start]
            while stack:
                u = stack.pop()
                r, c = u
                for nb in [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]:
                    if nb in shaded_cells and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            return len(visited) == len(shaded_cells)

        cell = all_cells[idx]
        for val in (False, True):
            if would_make_2x2(cell, val):
                continue
            state[cell] = val
            ok = True
            for nb in _ordered_neighbors(cell, rows, cols):
                if nb in clue_set and not clue_check(nb):
                    ok = False
                    break
            if ok:
                if on_step:
                    on_step([list(c) for c, v in state.items() if v], "push")
                if backtrack(idx + 1):
                    return True
            del state[cell]
            if on_step:
                on_step([list(c) for c, v in state.items() if v], "pop")
        return False

    if backtrack(0):
        shaded = [list(c) for c, v in state.items() if v]
        return SolveResult(solved=True, solution=shaded)
    reason = "max_nodes sinirina takildi" if nodes[0] > max_nodes else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_tapa(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_tapa_backtrack(puzzle)
