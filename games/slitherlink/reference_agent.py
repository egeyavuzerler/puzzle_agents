"""
games/slitherlink/reference_agent.py

Slitherlink icin referans generator + solver.

Uretim stratejisi: rastgele "deliksiz, bagli" bir hucre bolgesi buyut,
bolgenin SINIRI otomatik olarak TEK bir basit dongu olur (topolojik gercek:
basit-bagli bir poliomino'nun siniri her zaman tek dongudur) -- boylece
uretim HER ZAMAN gecerli bir cozume sahip.
"""

import random
from collections import defaultdict, deque

from core.base import SolveResult


def _cell_edge_list(r, c):
    top = frozenset([(r, c), (r, c + 1)])
    bottom = frozenset([(r + 1, c), (r + 1, c + 1)])
    left = frozenset([(r, c), (r + 1, c)])
    right = frozenset([(r, c + 1), (r + 1, c + 1)])
    return [top, bottom, left, right]


def _check_single_loop(edges) -> tuple[bool, str | None]:
    deg = defaultdict(int)
    adj = defaultdict(list)
    for e in edges:
        a, b = tuple(e)
        deg[a] += 1
        deg[b] += 1
        adj[a].append(b)
        adj[b].append(a)
    if not deg:
        return False, "bos"
    if any(d != 2 for d in deg.values()):
        return False, "derece 2 degil"
    start = next(iter(deg))
    visited = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                stack.append(v)
    if len(visited) != len(deg):
        return False, "bagli degil"
    if len(edges) != len(deg):
        return False, "kenar sayisi != dugum sayisi"
    return True, None


def _grow_region(rows, cols, rng, target_size):
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    start = rng.choice(all_cells)
    region = {start}
    frontier = set()

    def add_frontier(cell):
        r, c = cell
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in region:
                frontier.add((nr, nc))

    add_frontier(start)
    while len(region) < target_size and frontier:
        cell = rng.choice(list(frontier))
        frontier.discard(cell)
        region.add(cell)
        add_frontier(cell)
    return region


def _fill_holes(rows, cols, region):
    outside_reachable = set()
    q = deque()
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in region and (r == 0 or r == rows - 1 or c == 0 or c == cols - 1):
                if (r, c) not in outside_reachable:
                    outside_reachable.add((r, c))
                    q.append((r, c))
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in region and (nr, nc) not in outside_reachable:
                outside_reachable.add((nr, nc))
                q.append((nr, nc))
    all_cells = {(r, c) for r in range(rows) for c in range(cols)}
    holes = all_cells - region - outside_reachable
    return region | holes


def _boundary_edges(rows, cols, region):
    edges = set()
    for r in range(rows):
        for c in range(cols):
            in_region = (r, c) in region
            right_in = (r, c + 1) in region if c + 1 < cols else False
            if in_region != right_in:
                edges.add(frozenset([(r, c + 1), (r + 1, c + 1)]))
            down_in = (r + 1, c) in region if r + 1 < rows else False
            if in_region != down_in:
                edges.add(frozenset([(r + 1, c), (r + 1, c + 1)]))
            left_in = (r, c - 1) in region if c - 1 >= 0 else False
            if in_region != left_in:
                edges.add(frozenset([(r, c), (r + 1, c)]))
            up_in = (r - 1, c) in region if r - 1 >= 0 else False
            if in_region != up_in:
                edges.add(frozenset([(r, c), (r, c + 1)]))
    return edges


def generate_slitherlink(rng: random.Random, difficulty: int) -> dict:
    rows = cols = 7

    target = rng.randint(rows * cols // 3, rows * cols * 2 // 3)
    region = _grow_region(rows, cols, rng, target)
    region = _fill_holes(rows, cols, region)
    edges = _boundary_edges(rows, cols, region)

    all_counts = {}
    for r in range(rows):
        for c in range(cols):
            all_counts[(r, c)] = sum(1 for e in _cell_edge_list(r, c) if e in edges)

    reveal_prob = max(0.35, 0.80 - difficulty * 0.045)
    clues = [[None] * cols for _ in range(rows)]
    for (r, c), cnt in all_counts.items():
        if rng.random() < reveal_prob:
            clues[r][c] = cnt

    # ONEMLI (zorunlu/yasak kenar ozelligi): witness dongumuz (edges) zaten
    # elimizde -- ondan rastgele 0-2 kenari "required_edges" (dongude
    # KESINLIKLE olmali) diye, dongu DISINDAKI (yani tum olasi kenarlar -
    # edges) rastgele 0-2 kenari da "forbidden_edges" (dongude KESINLIKLE
    # OLAMAZ) diye acik ediyoruz. Ikisi de OPSIYONEL -- generator hic
    # kullanmayabilir (0 secilebilir). Witness zaten bu kenarlarla tutarli
    # oldugu icin ekstra bir dogrulamaya gerek yok.
    all_possible_edges = ({frozenset([(r, c), (r, c + 1)]) for r in range(rows + 1) for c in range(cols)} |
                           {frozenset([(r, c), (r + 1, c)]) for r in range(rows) for c in range(cols + 1)})
    non_loop_edges = list(all_possible_edges - edges)
    loop_edges = list(edges)

    n_required = rng.randint(0, min(2, len(loop_edges)))
    n_forbidden = rng.randint(0, min(2, len(non_loop_edges)))
    required_sample = rng.sample(loop_edges, n_required) if n_required else []
    forbidden_sample = rng.sample(non_loop_edges, n_forbidden) if n_forbidden else []

    required_edges = [sorted([list(p) for p in e]) for e in required_sample]
    forbidden_edges = [sorted([list(p) for p in e]) for e in forbidden_sample]

    puzzle = {
        "game": "slitherlink", "size": [rows, cols], "clues": clues,
        "required_edges": required_edges, "forbidden_edges": forbidden_edges,
    }
    solution = [[list(pt) for pt in edge] for edge in edges]  # tek kapali dongu -- witness cozum
    return puzzle, solution


class _Contradiction(Exception):
    pass


def solve_slitherlink_backtrack(puzzle: dict, on_step=None, max_expansions: int = 300000) -> SolveResult:
    rows, cols = puzzle["size"]
    clues = puzzle["clues"]

    all_edges = list({frozenset([(r, c), (r, c + 1)]) for r in range(rows + 1) for c in range(cols)} |
                      {frozenset([(r, c), (r + 1, c)]) for r in range(rows) for c in range(cols + 1)})

    edge_to_cells = defaultdict(list)
    for r in range(rows):
        for c in range(cols):
            if clues[r][c] is not None:
                e4 = _cell_edge_list(r, c)
                for e in e4:
                    edge_to_cells[e].append((clues[r][c], e4))

    edge_to_dots = {e: tuple(e) for e in all_edges}
    dot_to_edges = defaultdict(list)
    for e in all_edges:
        a, b = tuple(e)
        dot_to_edges[a].append(e)
        dot_to_edges[b].append(e)

    state = {}
    dot_deg = defaultdict(int)
    adj = defaultdict(set)
    total_true = [0]
    loop_closed = [False]

    def _reach(a, b):
        if a not in adj:
            return False
        visited = {a}
        stack = [a]
        while stack:
            u = stack.pop()
            if u == b:
                return True
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        return False

    def _comp_edge_count(a):
        if a not in adj:
            return 0
        visited = {a}
        stack = [a]
        ecount = 0
        while stack:
            u = stack.pop()
            for v in adj[u]:
                ecount += 1
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        return ecount // 2

    def set_edge(e, val, queue):
        if e in state:
            if state[e] != val:
                raise _Contradiction()
            return
        a, b = edge_to_dots[e]
        if val:
            if dot_deg[a] >= 2 or dot_deg[b] >= 2:
                raise _Contradiction()
            if loop_closed[0]:
                raise _Contradiction()
            if _reach(a, b):
                comp_edges = _comp_edge_count(a)
                if comp_edges != total_true[0]:
                    raise _Contradiction()
                loop_closed[0] = True
            state[e] = True
            dot_deg[a] += 1
            dot_deg[b] += 1
            adj[a].add(b)
            adj[b].add(a)
            total_true[0] += 1
            if on_step:
                on_step([list(x) for x in all_edges if state.get(x, False)], "push")
        else:
            state[e] = False
        queue.append(a)
        queue.append(b)
        for (clue, e4) in edge_to_cells.get(e, []):
            queue.append(("cell", tuple(e4), clue))

    def propagate(seed_queue):
        queue = deque(seed_queue)
        while queue:
            item = queue.popleft()
            if isinstance(item, tuple) and item and item[0] == "cell":
                _, e4, clue = item
                cnt_true = sum(1 for e in e4 if state.get(e) is True)
                cnt_false = sum(1 for e in e4 if state.get(e) is False)
                undec = [e for e in e4 if e not in state]
                if cnt_true > clue or cnt_true + len(undec) < clue:
                    raise _Contradiction()
                if cnt_true == clue and undec:
                    for e in undec:
                        q2 = deque()
                        set_edge(e, False, q2)
                        queue.extend(q2)
                elif cnt_true + len(undec) == clue and undec:
                    for e in undec:
                        q2 = deque()
                        set_edge(e, True, q2)
                        queue.extend(q2)
            else:
                dot = item
                d_true = dot_deg[dot]
                d_edges = dot_to_edges[dot]
                undec = [e for e in d_edges if e not in state]
                if d_true == 2 and undec:
                    for e in undec:
                        q2 = deque()
                        set_edge(e, False, q2)
                        queue.extend(q2)
                elif d_true == 1 and len(undec) == 1:
                    q2 = deque()
                    set_edge(undec[0], True, q2)
                    queue.extend(q2)

    try:
        init_queue = []
        for r in range(rows):
            for c in range(cols):
                if clues[r][c] is not None:
                    init_queue.append(("cell", tuple(_cell_edge_list(r, c)), clues[r][c]))
        propagate(init_queue)

        # ONEMLI (zorunlu/yasak kenar ozelligi): required_edges/forbidden_edges
        # varsa, cozume baslamadan ONCE bu kenarlari sabitliyoruz -- boylece
        # hem dogru cozum garanti edilir hem de arama uzayi daralir.
        for raw in puzzle.get("required_edges", []):
            e = frozenset([tuple(raw[0]), tuple(raw[1])])
            q = deque()
            set_edge(e, True, q)
            propagate(q)
        for raw in puzzle.get("forbidden_edges", []):
            e = frozenset([tuple(raw[0]), tuple(raw[1])])
            q = deque()
            set_edge(e, False, q)
            propagate(q)
    except _Contradiction:
        return SolveResult(solved=False, error="on isleme sirasinda celiski (gecersiz puzzle olabilir)")

    expansions = [0]

    def snapshot():
        return (dict(state), dict(dot_deg), {k: set(v) for k, v in adj.items()}, total_true[0], loop_closed[0])

    def restore(snap):
        s, d, a, t, lc = snap
        state.clear()
        state.update(s)
        dot_deg.clear()
        dot_deg.update(d)
        adj.clear()
        adj.update(a)
        total_true[0] = t
        loop_closed[0] = lc

    def backtrack():
        expansions[0] += 1
        if expansions[0] > max_expansions:
            return False
        remaining = [e for e in all_edges if e not in state]
        if not remaining:
            true_edges = {e for e in all_edges if state.get(e, False)}
            if not true_edges:
                return False
            ok, _err = _check_single_loop(true_edges)
            return ok

        e = remaining[0]
        best_slack = None
        for cand_e in remaining[:30]:
            slack = 99
            for (clue, e4) in edge_to_cells.get(cand_e, []):
                cnt_true = sum(1 for x in e4 if state.get(x) is True)
                cnt_false = sum(1 for x in e4 if state.get(x) is False)
                undec = 4 - cnt_true - cnt_false
                s = min(clue - cnt_true, undec - (clue - cnt_true))
                slack = min(slack, s)
            if best_slack is None or slack < best_slack:
                best_slack = slack
                e = cand_e

        for val in (True, False):
            snap = snapshot()
            try:
                q = deque()
                set_edge(e, val, q)
                propagate(q)
                if backtrack():
                    return True
            except _Contradiction:
                pass
            restore(snap)
            if on_step:
                on_step([list(x) for x in all_edges if state.get(x, False)], "pop")
        return False

    found = backtrack()
    if found:
        true_edges = [list(e) for e in all_edges if state.get(e, False)]
        return SolveResult(solved=True, solution=true_edges)
    reason = "max_expansions sinirina takildi" if expansions[0] > max_expansions else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_slitherlink(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_slitherlink_backtrack(puzzle)
