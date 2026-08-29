"""
games/lits/reference_agent.py

LITS icin referans generator + solver.

Uretim stratejisi: once bolgeleri RASTGELE BUYUTEREK olustur (min_cell-
max_cell arasi hucreli, "toparlak" -- ince seritlerden kacinarak, aksi
halde sadece I-tetromino sigar ve komsu bolgeler tikanir). Sonra bolge
komsuluk grafinde BFS sirasiyla, her bolge icin gecerli (2x2 yaratmayan,
ayni-tip-komsu olmayan) bir tetromino secmeye calisir; tikanirsa GERI
SARAR (backtracking). Son adimda TUM golgeli hucrelerin tek bagli
oldugunu dogrular.
"""

import random
from collections import defaultdict, deque

from core.base import SolveResult

_BASE_SHAPES = {
    "I": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "L": [(0, 0), (1, 0), (2, 0), (2, 1)],
    "T": [(0, 0), (0, 1), (0, 2), (1, 1)],
    "S": [(0, 1), (0, 2), (1, 0), (1, 1)],
}


def _normalize(cells):
    min_r = min(r for r, c in cells)
    min_c = min(c for r, c in cells)
    return frozenset((r - min_r, c - min_c) for r, c in cells)


def _rotate90(cells):
    return [(c, -r) for r, c in cells]


def _mirror(cells):
    return [(r, -c) for r, c in cells]


def _all_orientations(base):
    variants = set()
    shape = base
    for _ in range(4):
        variants.add(_normalize(shape))
        variants.add(_normalize(_mirror(shape)))
        shape = _rotate90(shape)
    return list(variants)


_TYPE_SHAPES = {name: _all_orientations(base) for name, base in _BASE_SHAPES.items()}


def _check_connected(shaded):
    if not shaded:
        return False
    start = next(iter(shaded))
    visited = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (u[0] + dr, u[1] + dc)
            if nb in shaded and nb not in visited:
                visited.add(nb)
                stack.append(nb)
    return len(visited) == len(shaded)


def _touches(cells_a, cells_b):
    for (r, c) in cells_a:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (r + dr, c + dc) in cells_b:
                return True
    return False


def _creates_2x2(shaded_set, new_cells):
    combined = shaded_set | new_cells
    for (r, c) in new_cells:
        for dr, dc in ((0, 0), (0, -1), (-1, 0), (-1, -1)):
            block = {(r + dr, c + dc), (r + dr + 1, c + dc), (r + dr, c + dc + 1), (r + dr + 1, c + dc + 1)}
            if block.issubset(combined):
                return True
    return False


def _candidates_for_region(cells):
    cellset = set(cells)
    out = []
    for typ, variants in _TYPE_SHAPES.items():
        for pattern in variants:
            for (r0, c0) in cells:
                placed = {(r0 + dr, c0 + dc) for dr, dc in pattern}
                if placed.issubset(cellset):
                    out.append((typ, frozenset(placed)))
    return out


def _region_adjacency(region_cells):
    adj = defaultdict(set)
    cell_to_region = {}
    for rid, cells in region_cells.items():
        for c in cells:
            cell_to_region[c] = rid
    for rid, cells in region_cells.items():
        for (r, c) in cells:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + dr, c + dc)
                if nb in cell_to_region and cell_to_region[nb] != rid:
                    adj[rid].add(cell_to_region[nb])
    return adj


def _build_regions_growth(rows, cols, rng, min_cell, max_cell):
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    n_regions_target = max(1, (rows * cols) // ((min_cell + max_cell) // 2))
    unassigned = set(all_cells)
    seeds = rng.sample(all_cells, min(n_regions_target, len(all_cells)))
    region_cells = {i: [s] for i, s in enumerate(seeds)}
    cell_region = {s: i for i, s in enumerate(seeds)}
    unassigned -= set(seeds)

    frontiers = {i: set() for i in region_cells}

    def update_frontier(rid):
        f = set()
        for (r, c) in region_cells[rid]:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + dr, c + dc)
                if nb in unassigned:
                    f.add(nb)
        frontiers[rid] = f

    for rid in region_cells:
        update_frontier(rid)

    active = [rid for rid in region_cells if len(region_cells[rid]) < max_cell and frontiers[rid]]
    while unassigned and active:
        rng.shuffle(active)
        progressed = False
        for rid in list(active):
            if len(region_cells[rid]) >= max_cell or not frontiers[rid]:
                continue
            cell = rng.choice(list(frontiers[rid]))
            if cell not in unassigned:
                frontiers[rid].discard(cell)
                continue
            region_cells[rid].append(cell)
            cell_region[cell] = rid
            unassigned.discard(cell)
            progressed = True
            frontiers[rid].discard(cell)
            r, c = cell
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + dr, c + dc)
                if nb in unassigned:
                    frontiers[rid].add(nb)
        active = [rid for rid in region_cells if len(region_cells[rid]) < max_cell and frontiers[rid]]
        if not progressed:
            break

    changed = True
    while unassigned and changed:
        changed = False
        for cell in list(unassigned):
            r, c = cell
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + dr, c + dc)
                if nb in cell_region:
                    rid = cell_region[nb]
                    region_cells[rid].append(cell)
                    cell_region[cell] = rid
                    unassigned.discard(cell)
                    changed = True
                    break
    if unassigned:
        return None

    changed = True
    while changed:
        changed = False
        adj = _region_adjacency(region_cells)
        for rid in list(region_cells.keys()):
            if len(region_cells[rid]) < min_cell:
                nbs = list(adj[rid])
                if not nbs:
                    continue
                target = rng.choice(nbs)
                for cell in region_cells[rid]:
                    cell_region[cell] = target
                region_cells[target].extend(region_cells[rid])
                del region_cells[rid]
                changed = True
                break

    for rid, cells in region_cells.items():
        if len(cells) > max_cell + 4 or len(cells) < 4:
            return None

    region_grid = [[None] * cols for _ in range(rows)]
    final_regions = {}
    for new_id, (rid, cells) in enumerate(region_cells.items()):
        final_regions[new_id] = cells
        for (r, c) in cells:
            region_grid[r][c] = new_id
    return region_grid, final_regions


def _generate_once(rng, rows, cols, min_cell, max_cell, max_nodes):
    result = _build_regions_growth(rows, cols, rng, min_cell, max_cell)
    if result is None:
        return None
    region_grid, region_cells = result
    if len(region_cells) < 4:
        return None
    adj = _region_adjacency(region_cells)

    all_regions = list(region_cells.keys())
    start = rng.choice(all_regions)
    order = [start]
    visited = {start}
    q = deque([start])
    while q:
        u = q.popleft()
        nbs = list(adj[u])
        rng.shuffle(nbs)
        for v in nbs:
            if v not in visited:
                visited.add(v)
                order.append(v)
                q.append(v)
    for rid in all_regions:
        if rid not in visited:
            order.append(rid)
            visited.add(rid)

    all_cands = {}
    for rid in order:
        cands = _candidates_for_region(region_cells[rid])
        rng.shuffle(cands)
        all_cands[rid] = cands

    placed = {}
    shaded = set()
    region_type = {}
    nodes = [0]

    def backtrack(idx):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if idx == len(order):
            return _check_connected(shaded)
        rid = order[idx]
        cands = all_cands[rid]
        if idx > 0:
            cands = sorted(cands, key=lambda tc: 0 if _touches(tc[1], shaded) else 1)
        for (typ, pcells) in cands:
            if _creates_2x2(shaded, pcells):
                continue
            bad = False
            for nb_rid in adj[rid]:
                if nb_rid in placed and region_type[nb_rid] == typ and _touches(pcells, placed[nb_rid][1]):
                    bad = True
                    break
            if bad:
                continue
            placed[rid] = (typ, pcells)
            region_type[rid] = typ
            shaded.update(pcells)
            if backtrack(idx + 1):
                return True
            shaded.difference_update(pcells)
            del placed[rid]
            del region_type[rid]
        return False

    if backtrack(0):
        # ONEMLI (zorunlu hucre / forced_shaded ozelligi): backtracking
        # BASARILI oldu, yani `placed` artik her bolge icin secilen gercek
        # tetromino hucrelerini iceriyor. Bu NOKTADAN itibaren rastgele
        # birkac bolgeden (region basina EN FAZLA 1 hucre) birer hucreyi
        # "kesinlikle golgeli" diye acik ediyoruz. Bu OPSIYONEL bir kural --
        # katilimci kendi generator'inda hic forced_shaded kullanmayabilir.
        # Bu hucreler zaten BULUNMUS witness cozumden secildigi icin ekstra
        # bir dogrulamaya gerek yok -- otomatik olarak tutarli.
        forced_shaded = []
        region_ids = list(placed.keys())
        rng.shuffle(region_ids)
        n_forced = rng.randint(0, min(3, len(region_ids)))
        for rid in region_ids[:n_forced]:
            _typ, pcells = placed[rid]
            forced_shaded.append(list(rng.choice(sorted(pcells))))
        return region_grid, [list(cell) for cell in shaded], forced_shaded
    return None


def generate_lits(rng: random.Random, difficulty: int, max_outer_attempts: int = 150):
    """difficulty arttikca bolgeler biraz kuculur (daha fazla, daha kucuk
    bolge = daha fazla tetromino secimi = daha zor)."""
    rows = cols = 9
    max_cell = max(6, 10 - difficulty // 2)
    min_cell = max(4, max_cell - 4)

    for _ in range(max_outer_attempts):
        result = _generate_once(rng, rows, cols, min_cell, max_cell, max_nodes=15000)
        if result is not None:
            region_grid, solution, forced_shaded = result
            puzzle = {"game": "lits", "size": [rows, cols], "regions": region_grid,
                      "forced_shaded": forced_shaded}
            return puzzle, solution
    raise RuntimeError(f"{max_outer_attempts} denemede gecerli lits puzzle uretilemedi")


def solve_lits_backtrack(puzzle: dict, on_step=None, max_nodes: int = 300000) -> SolveResult:
    rows, cols = puzzle["size"]
    regions = puzzle["regions"]

    region_cells = defaultdict(list)
    for r in range(rows):
        for c in range(cols):
            region_cells[regions[r][c]].append((r, c))

    # ONEMLI (zorunlu hucre / forced_shaded ozelligi): bir bolgede zorunlu
    # golgeli hucre varsa, o bolge icin SADECE bu hucreyi iceren
    # tetromino adaylarini dene -- hem arama uzayini daraltir (performans)
    # hem de dogrulugu garanti eder (validate_solution'daki forced_shaded
    # kontrolunu otomatik gecer).
    forced_by_region = {}
    for cell in puzzle.get("forced_shaded", []):
        r, c = cell
        forced_by_region[regions[r][c]] = (r, c)

    adj = _region_adjacency(region_cells)
    all_cands = {}
    for rid, cells in region_cells.items():
        cands = _candidates_for_region(cells)
        forced_cell = forced_by_region.get(rid)
        if forced_cell is not None:
            cands = [tc for tc in cands if forced_cell in tc[1]]
        all_cands[rid] = cands
    order = sorted(region_cells.keys(), key=lambda rid: len(all_cands[rid]))

    placed = {}
    shaded = set()
    region_type = {}
    nodes = [0]

    def backtrack(idx):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        if idx == len(order):
            return _check_connected(shaded)
        rid = order[idx]
        cands = sorted(all_cands[rid], key=lambda tc: 0 if _touches(tc[1], shaded) else 1)
        for (typ, pcells) in cands:
            if _creates_2x2(shaded, pcells):
                continue
            bad = False
            for nb in adj[rid]:
                if nb in placed and region_type[nb] == typ and _touches(pcells, placed[nb][1]):
                    bad = True
                    break
            if bad:
                continue
            placed[rid] = (typ, pcells)
            region_type[rid] = typ
            shaded.update(pcells)
            if on_step:
                on_step([list(x) for x in shaded], "push")
            if backtrack(idx + 1):
                return True
            shaded.difference_update(pcells)
            del placed[rid]
            del region_type[rid]
            if on_step:
                on_step([list(x) for x in shaded], "pop")
        return False

    if backtrack(0):
        return SolveResult(solved=True, solution=[list(c) for c in shaded])
    reason = "max_nodes sinirina takildi" if nodes[0] > max_nodes else "arama tukendi"
    return SolveResult(solved=False, error=f"backtracking cozum bulamadi ({reason})")


def solve_lits(puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
    """BaseSolverAgent.solve() imzasina uyan basit sarmalayici."""
    return solve_lits_backtrack(puzzle)
