"""
games/zip/reference_agent.py

Zip icin referans generator + solver. Hackathon katilimcilari kendi
generator/solver'larini boyle bir dosyada yazacak (BaseGeneratorAgent /
BaseSolverAgent'tan miras alarak -- bkz. agents_examples/baseline.py).
"""

import random

from core.base import SolveResult


def solve_zip_warnsdorff(puzzle: dict, record_trace: bool = False, max_expansions: int = 300000,
                          on_step=None):
    """
    Warnsdorff sezgiseli + backtracking: her adimda, kalan komsular arasinda
    EN AZ secenegi olana git.

    on_step: verilirse, HER push/pop adiminda on_step(path_list, event) ile
    cagrilir (event = "push" ya da "pop"). CANLI gorsellestirme icin bu
    kullanilir -- bkz. arena/run_live.py.

    max_expansions: guvenlik payi -- bu kadar dugum denendikten sonra hala
    cozum bulunamadiysa pes eder.

    Donus: (SolveResult, trace_or_None)
    """
    rows, cols = puzzle["size"]
    blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
    checkpoints = sorted(puzzle["checkpoints"], key=lambda cp: cp["order"])
    free_total = rows * cols - len(blocked)

    def neighbors(cell):
        r, c = cell
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in blocked:
                yield (nr, nc)

    start = tuple(checkpoints[0]["pos"])
    last_cp_pos = tuple(checkpoints[-1]["pos"])
    checkpoint_positions = {tuple(cp["pos"]) for cp in checkpoints}

    visited = {start}
    path = [start]
    trace = [list(path)] if record_trace else None
    if on_step:
        on_step(list(path), "push")
    expansions = [0]

    def onward_degree(cell) -> int:
        return sum(1 for n in neighbors(cell) if n not in visited)

    def backtrack(cell, cp_idx):
        if expansions[0] >= max_expansions:
            return False
        expansions[0] += 1

        if len(path) == free_total:
            return cp_idx == len(checkpoints) and path[-1] == last_cp_pos

        candidates = []
        for nxt in neighbors(cell):
            if nxt in visited:
                continue
            if nxt in checkpoint_positions:
                expected = tuple(checkpoints[cp_idx]["pos"]) if cp_idx < len(checkpoints) else None
                if nxt != expected:
                    continue
                if nxt == last_cp_pos and (len(path) + 1) != free_total:
                    continue
            candidates.append(nxt)

        visited_set = visited
        def degree_key(n):
            visited_set.add(n)
            d = onward_degree(n)
            visited_set.discard(n)
            return d
        candidates.sort(key=degree_key)

        for nxt in candidates:
            next_cp_idx = cp_idx + 1 if nxt in checkpoint_positions else cp_idx
            visited.add(nxt)
            path.append(nxt)
            if record_trace:
                trace.append(list(path))
            if on_step:
                on_step(list(path), "push")
            if backtrack(nxt, next_cp_idx):
                return True
            path.pop()
            visited.discard(nxt)
            if record_trace:
                trace.append(list(path))
            if on_step:
                on_step(list(path), "pop")
            if expansions[0] >= max_expansions:
                return False
        return False

    found = backtrack(start, 1)
    if found:
        result = SolveResult(solved=True, solution=[list(c) for c in path])
    else:
        reason = "max_expansions sinirina takildi" if expansions[0] >= max_expansions else "arama tukendi"
        result = SolveResult(solved=False, error=f"Warnsdorff+backtracking cozum bulamadi ({reason})")
    return result, trace


def solve_zip(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici (trace atilir)."""
    result, _trace = solve_zip_warnsdorff(puzzle, record_trace=False)
    return result


def generate_zip(rng: random.Random, difficulty: int) -> dict:
    """Once rastgele bir Hamiltonian path (yilanvari yuruyus) ciz, sonra
    uzerine checkpoint'ler serp."""
    size = 10
    rows = cols = size

    path = []
    for r in range(rows):
        col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
        for c in col_range:
            path.append((r, c))

    n_checkpoints = min(5 + difficulty // 2, len(path))
    middle_indices = rng.sample(range(1, len(path) - 1), max(0, n_checkpoints - 2)) if n_checkpoints > 2 else []
    checkpoint_indices = sorted({0, len(path) - 1} | set(middle_indices))
    checkpoints = [
        {"order": i + 1, "pos": list(path[idx])}
        for i, idx in enumerate(checkpoint_indices)
    ]

    puzzle = {
        "game": "zip",
        "size": [rows, cols],
        "checkpoints": checkpoints,
        "blocked_cells": [],
    }
    solution = [list(cell) for cell in path]  # tam Hamiltonian path -- witness cozum
    return puzzle, solution
