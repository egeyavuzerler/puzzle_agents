"""
games/queens/reference_agent.py

Queens icin referans generator + solver.
"""

import random

from core.base import SolveResult


def solve_queens_backtrack(puzzle: dict, on_step=None) -> SolveResult:
    """
    Klasik satir-satir backtracking. on_step verilirse her push/pop'ta
    on_step(placement_list, event) cagrilir -- canli gorsellestirme icin.
    """
    rows, cols = puzzle["size"]
    regions = puzzle["regions"]
    n = rows

    used_cols, used_regions = set(), set()
    placement = []

    def touches_prev(r, c):
        return placement and abs(placement[-1][0] - r) <= 1 and abs(placement[-1][1] - c) <= 1

    def backtrack(row):
        if row == n:
            return True
        for c in range(cols):
            region = regions[row][c]
            if c in used_cols or region in used_regions:
                continue
            if touches_prev(row, c):
                continue
            placement.append((row, c))
            used_cols.add(c)
            used_regions.add(region)
            if on_step:
                on_step(list(placement), "push")
            if backtrack(row + 1):
                return True
            placement.pop()
            used_cols.discard(c)
            used_regions.discard(region)
            if on_step:
                on_step(list(placement), "pop")
        return False

    if backtrack(0):
        return SolveResult(solved=True, solution=[list(p) for p in placement])
    return SolveResult(solved=False, error="backtracking ile cozum bulunamadi")


def solve_queens(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_queens_backtrack(puzzle)


def solve_n_queens_any(n: int, rng: random.Random) -> list[tuple[int, int]]:
    """Rastgele, komsuluk-kisitli (Queens oyunundaki gibi) bir N-Queens
    cozumu uretir. Generator'in region'lari turetmesi icin kullanilir."""
    solution = []

    def backtrack(row: int, used_cols: set, diag1: set, diag2: set) -> bool:
        if row == n:
            return True
        candidates = list(range(n))
        rng.shuffle(candidates)
        for c in candidates:
            if c in used_cols or (row - c) in diag1 or (row + c) in diag2:
                continue
            if solution and max(abs(row - 1 - solution[-1][0]), abs(c - solution[-1][1])) <= 1 \
                    and solution[-1][0] == row - 1:
                continue
            solution.append((row, c))
            used_cols.add(c)
            diag1.add(row - c)
            diag2.add(row + c)
            if backtrack(row + 1, used_cols, diag1, diag2):
                return True
            solution.pop()
            used_cols.discard(c)
            diag1.discard(row - c)
            diag2.discard(row + c)
        return False

    ok = backtrack(0, set(), set(), set())
    if not ok:
        raise RuntimeError(f"{n}-queens (bitisiklik kisitli) cozum bulunamadi")
    return solution


def generate_queens(rng: random.Random, difficulty: int) -> dict:
    """Once N-Queens coz (klasik backtracking), sonra her kralice
    hucresine ayri bir region id ver, kalan hucreleri en yakin kralicenin
    region'ina ata (basit "Voronoi" mantigi)."""
    n = 10
    solution = solve_n_queens_any(n, rng)

    regions = [[-1] * n for _ in range(n)]
    for r in range(n):
        for c in range(n):
            best_q, best_dist = None, None
            for qi, (qr, qc) in enumerate(solution):
                d = max(abs(r - qr), abs(c - qc))
                if best_dist is None or d < best_dist:
                    best_dist, best_q = d, qi
            regions[r][c] = best_q

    puzzle = {"game": "queens", "size": [n, n], "regions": regions}
    witness = [list(pos) for pos in solution]  # solve_n_queens_any'nin uzerine kurdugumuz cozum
    return puzzle, witness
