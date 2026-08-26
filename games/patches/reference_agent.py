"""
games/patches/reference_agent.py

Patches icin referans generator + solver.
"""

import random

from core.base import SolveResult


def _patches_recursive_split(r0, c0, r1, c1, rng, min_cell=2, stop_prob=0.15):
    height, width = r1 - r0 + 1, c1 - c0 + 1
    area = height * width
    if area <= min_cell or (area <= 12 and rng.random() < stop_prob):
        return [(r0, c0, r1, c1)]

    can_h, can_v = height >= 2, width >= 2
    if not can_h and not can_v:
        return [(r0, c0, r1, c1)]
    direction = rng.choice(["h", "v"]) if (can_h and can_v) else ("h" if can_h else "v")

    if direction == "h":
        split_r = rng.randint(r0, r1 - 1)
        return (_patches_recursive_split(r0, c0, split_r, c1, rng, min_cell, stop_prob)
                + _patches_recursive_split(split_r + 1, c0, r1, c1, rng, min_cell, stop_prob))
    else:
        split_c = rng.randint(c0, c1 - 1)
        return (_patches_recursive_split(r0, c0, r1, split_c, rng, min_cell, stop_prob)
                + _patches_recursive_split(r0, split_c + 1, r1, c1, rng, min_cell, stop_prob))


def _patches_rect_shape(r0, c0, r1, c1) -> str:
    h, w = r1 - r0 + 1, c1 - c0 + 1
    if w == h:
        return "square"
    return "wide" if w > h else "tall"


def solve_patches_backtrack(puzzle: dict, on_step=None, max_nodes: int = 500000) -> SolveResult:
    rows, cols = puzzle["size"]
    clues = puzzle["clues"]
    clue_positions = [tuple(c["pos"]) for c in clues]

    def candidates_for(i):
        r, c = clue_positions[i]
        area = clues[i]["area"]
        shape = clues[i]["shape"]
        cands = []
        for h in range(1, rows + 1):
            if area % h != 0:
                continue
            w = area // h
            if w > cols:
                continue
            if shape == "square" and w != h:
                continue
            if shape == "wide" and w <= h:
                continue
            if shape == "tall" and h <= w:
                continue
            r0_min, r0_max = max(0, r - h + 1), min(r, rows - h)
            c0_min, c0_max = max(0, c - w + 1), min(c, cols - w)
            for r0 in range(r0_min, r0_max + 1):
                for c0 in range(c0_min, c0_max + 1):
                    r1, c1 = r0 + h - 1, c0 + w - 1
                    ok = True
                    for j, (orr, occ) in enumerate(clue_positions):
                        if j == i:
                            continue
                        if r0 <= orr <= r1 and c0 <= occ <= c1:
                            ok = False
                            break
                    if ok:
                        cands.append((r0, c0, r1, c1))
        return cands

    all_cands = [candidates_for(i) for i in range(len(clues))]
    order = sorted(range(len(clues)), key=lambda i: len(all_cands[i]))

    occupied = [[False] * cols for _ in range(rows)]
    result = [None] * len(clues)
    nodes = [0]

    def can_place(r0, c0, r1, c1):
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                if occupied[rr][cc]:
                    return False
        return True

    def place(r0, c0, r1, c1, val):
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                occupied[rr][cc] = val

    def backtrack(k):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if k == len(order):
            return True
        i = order[k]
        for (r0, c0, r1, c1) in all_cands[i]:
            if can_place(r0, c0, r1, c1):
                place(r0, c0, r1, c1, True)
                result[i] = {"r0": r0, "c0": c0, "r1": r1, "c1": c1}
                if on_step:
                    on_step(list(result), "push")
                if backtrack(k + 1):
                    return True
                place(r0, c0, r1, c1, False)
                result[i] = None
                if on_step:
                    on_step(list(result), "pop")
        return False

    if backtrack(0):
        return SolveResult(solved=True, solution=result)
    reason = "max_nodes sinirina takildi" if nodes[0] > max_nodes else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_patches(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_patches_backtrack(puzzle)


def generate_patches(rng: random.Random, difficulty: int) -> dict:
    rows = cols = 10

    stop_prob = max(0.03, 0.20 - difficulty * 0.015)
    rects = _patches_recursive_split(0, 0, rows - 1, cols - 1, rng, min_cell=2, stop_prob=stop_prob)

    any_prob = 0.15
    clues = []
    for (r0, c0, r1, c1) in rects:
        cr = rng.randint(r0, r1)
        cc = rng.randint(c0, c1)
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        shape = _patches_rect_shape(r0, c0, r1, c1)
        if shape != "square" and rng.random() < any_prob:
            shape = "any"
        clues.append({"pos": [cr, cc], "area": area, "shape": shape})

    puzzle = {"game": "patches", "size": [rows, cols], "clues": clues}
    solution = [{"r0": r0, "c0": c0, "r1": r1, "c1": c1} for (r0, c0, r1, c1) in rects]
    return puzzle, solution
