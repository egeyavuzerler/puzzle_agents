"""
games/hashi/reference_agent.py

Hashiwokakero (Bridges) icin referans generator + solver.

Uretim stratejisi: adalari BUYUTEREK yerlestir -- her yeni ada, MEVCUT
bir adayla ayni satir/sutunda (aralarinda engelsiz) olacak sekilde eklenir.
Bu, bagli bir aday-kenar grafinin dogustan garanti olmasini saglar. Sonra
bu graf uzerinde (kesismeyen) bir spanning tree + birkac ekstra kenar
secilip koprulere donusturulur, ada degerleri bu koprulerden hesaplanir.
"""

import random
from collections import defaultdict, deque

from core.base import SolveResult


def _segments_cross(e1, e2) -> bool:
    p1, p2 = e1
    p3, p4 = e2

    def is_horiz(p, q):
        return p[0] == q[0]

    h1, h2 = is_horiz(p1, p2), is_horiz(p3, p4)
    if h1 == h2:
        if h1:
            if p1[0] != p3[0]:
                return False
            lo1, hi1 = sorted([p1[1], p2[1]])
            lo2, hi2 = sorted([p3[1], p4[1]])
            return not (hi1 <= lo2 or hi2 <= lo1)
        else:
            if p1[1] != p3[1]:
                return False
            lo1, hi1 = sorted([p1[0], p2[0]])
            lo2, hi2 = sorted([p3[0], p4[0]])
            return not (hi1 <= lo2 or hi2 <= lo1)
    else:
        horiz, vert = (e1, e2) if h1 else (e2, e1)
        hp1, hp2 = horiz
        hr = hp1[0]
        hc_lo, hc_hi = sorted([hp1[1], hp2[1]])
        vp1, vp2 = vert
        vc = vp1[1]
        vr_lo, vr_hi = sorted([vp1[0], vp2[0]])
        return hc_lo < vc < hc_hi and vr_lo < hr < vr_hi


def _neighbors_line_of_sight(islands_set, pos, rows, cols):
    r, c = pos
    result = []
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        rr, cc = r + dr, c + dc
        while 0 <= rr < rows and 0 <= cc < cols:
            if (rr, cc) in islands_set:
                result.append((rr, cc))
                break
            rr += dr
            cc += dc
    return result


def _grow_islands(rng, rows, cols, n_islands, max_attempts=800):
    islands = {(rng.randrange(rows), rng.randrange(cols))}
    attempts = 0
    while len(islands) < n_islands and attempts < max_attempts:
        attempts += 1
        base = rng.choice(list(islands))
        dr, dc = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
        r, c = base
        empty_along_ray = []
        rr, cc = r + dr, c + dc
        while 0 <= rr < rows and 0 <= cc < cols:
            if (rr, cc) in islands:
                break
            empty_along_ray.append((rr, cc))
            rr += dr
            cc += dc
        if not empty_along_ray:
            continue
        new_island = empty_along_ray[0] if rng.random() < 0.6 else rng.choice(empty_along_ray)
        islands.add(new_island)
    return islands


def _generate_once(rng, rows, cols, n_islands, max_extra_edges_ratio):
    islands = _grow_islands(rng, rows, cols, n_islands)
    if len(islands) < min(n_islands, 5):
        return None

    candidate_edges = set()
    for isl in islands:
        for other in _neighbors_line_of_sight(islands, isl, rows, cols):
            candidate_edges.add(tuple(sorted([isl, other])))
    if not candidate_edges:
        return None
    candidate_edges = list(candidate_edges)
    rng.shuffle(candidate_edges)

    parent = {isl: isl for isl in islands}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        parent[rx] = ry
        return True

    placed_edges = []

    def crosses_any(new_edge):
        for (a, b, _c) in placed_edges:
            if _segments_cross((a, b), new_edge):
                return True
        return False

    for (a, b) in candidate_edges:
        if find(a) == find(b):
            continue
        if crosses_any((a, b)):
            continue
        if union(a, b):
            count = rng.choice([1, 1, 2])
            placed_edges.append((a, b, count))

    if len({find(isl) for isl in islands}) != 1:
        return None

    n_extra_target = int(len(placed_edges) * max_extra_edges_ratio)
    extra_added = 0
    for (a, b) in candidate_edges:
        if extra_added >= n_extra_target:
            break
        if any((a == pa and b == pb) for (pa, pb, _c) in placed_edges):
            continue
        if crosses_any((a, b)):
            continue
        count = rng.choice([1, 2])
        placed_edges.append((a, b, count))
        extra_added += 1

    island_values = defaultdict(int)
    for (a, b, cnt) in placed_edges:
        island_values[a] += cnt
        island_values[b] += cnt
    for isl in islands:
        if island_values[isl] == 0 or island_values[isl] > 8:
            return None

    puzzle_islands = [{"pos": list(isl), "value": island_values[isl]} for isl in islands]
    puzzle = {"game": "hashi", "size": [rows, cols], "islands": puzzle_islands}
    solution = [{"from": list(a), "to": list(b), "count": cnt} for (a, b, cnt) in placed_edges]
    return puzzle, solution


def generate_hashi(rng: random.Random, difficulty: int, max_attempts: int = 40) -> dict:
    """difficulty arttikca daha fazla ada + daha az 'fazladan' kenar
    (daha az yedeklilik = daha belirsiz/zor)."""
    rows = cols = 10
    n_islands = min(14 + difficulty, 34)
    extra_ratio = max(0.03, 0.30 - difficulty * 0.025)

    for _ in range(max_attempts):
        puzzle = _generate_once(rng, rows, cols, n_islands, extra_ratio)
        if puzzle is not None:
            return puzzle
    raise RuntimeError(f"{max_attempts} denemede gecerli hashi puzzle uretilemedi")


class _Contradiction(Exception):
    pass


def solve_hashi_backtrack(puzzle: dict, on_step=None, max_expansions: int = 200000) -> SolveResult:
    rows, cols = puzzle["size"]
    islands = {tuple(i["pos"]): i["value"] for i in puzzle["islands"]}
    island_positions = set(islands.keys())

    candidate_edges = set()
    for isl in island_positions:
        for other in _neighbors_line_of_sight(island_positions, isl, rows, cols):
            candidate_edges.add(tuple(sorted([isl, other])))
    candidate_edges = list(candidate_edges)

    edges_of = defaultdict(list)
    for (a, b) in candidate_edges:
        edges_of[a].append((a, b))
        edges_of[b].append((a, b))

    state = {}
    expansions = [0]

    def sum_at(isl):
        return sum(state.get(e, 0) for e in edges_of[isl])

    def slack_at(isl):
        return [e for e in edges_of[isl] if e not in state]

    def crosses_existing(e, val):
        if val == 0:
            return False
        for e2, v2 in state.items():
            if v2 > 0 and e != e2 and _segments_cross(e, e2):
                return True
        return False

    def set_edge(e, val, q):
        if e in state:
            if state[e] != val:
                raise _Contradiction()
            return
        if crosses_existing(e, val):
            raise _Contradiction()
        state[e] = val
        if on_step and val > 0:
            on_step([{"from": list(x[0]), "to": list(x[1]), "count": v}
                      for x, v in state.items() if v > 0], "push")
        q.append(e[0])
        q.append(e[1])

    def propagate(seed_queue):
        q = deque(seed_queue)
        while q:
            isl = q.popleft()
            cur_sum = sum_at(isl)
            target = islands[isl]
            undecided = slack_at(isl)
            if cur_sum > target:
                raise _Contradiction()
            if cur_sum + 2 * len(undecided) < target:
                raise _Contradiction()
            if not undecided:
                if cur_sum != target:
                    raise _Contradiction()
                continue
            remaining = target - cur_sum
            if remaining == 2 * len(undecided):
                for e in undecided:
                    set_edge(e, 2, q)
            elif remaining == 0:
                for e in undecided:
                    set_edge(e, 0, q)
            elif len(undecided) == 1:
                set_edge(undecided[0], remaining, q)

    try:
        propagate(list(island_positions))
    except _Contradiction:
        return SolveResult(solved=False, error="on isleme sirasinda celiski")

    def snapshot():
        return dict(state)

    def restore(s):
        state.clear()
        state.update(s)

    def check_final():
        adj = defaultdict(set)
        for e, v in state.items():
            if v > 0:
                adj[e[0]].add(e[1])
                adj[e[1]].add(e[0])
        for isl in island_positions:
            if sum_at(isl) != islands[isl]:
                return False
        start = next(iter(island_positions))
        visited = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        return len(visited) == len(island_positions)

    def backtrack():
        expansions[0] += 1
        if expansions[0] > max_expansions:
            return False
        undecided_edges = [e for e in candidate_edges if e not in state]
        if not undecided_edges:
            return check_final()

        best_e = undecided_edges[0]
        best_slack = 99
        for e in undecided_edges[:20]:
            for isl in e:
                target = islands[isl]
                cur = sum_at(isl)
                undec = len(slack_at(isl))
                slack = min(target - cur, 2 * undec - (target - cur))
                if slack < best_slack:
                    best_slack = slack
                    best_e = e

        for val in (1, 2, 0):
            snap = snapshot()
            try:
                q = []
                set_edge(best_e, val, q)
                propagate(q)
                if backtrack():
                    return True
            except _Contradiction:
                pass
            restore(snap)
            if on_step:
                on_step([{"from": list(x[0]), "to": list(x[1]), "count": v}
                          for x, v in state.items() if v > 0], "pop")
        return False

    found = backtrack()
    if found:
        sol = [{"from": list(e[0]), "to": list(e[1]), "count": state[e]}
               for e in candidate_edges if state.get(e, 0) > 0]
        return SolveResult(solved=True, solution=sol)
    reason = "max_expansions sinirina takildi" if expansions[0] > max_expansions else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_hashi(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_hashi_backtrack(puzzle)
