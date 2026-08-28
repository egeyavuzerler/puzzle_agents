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


def _zip_free_cells_connected(free_cells: set[tuple[int, int]], rows: int, cols: int) -> bool:
    """games/zip/validator.py'deki _is_connected ile ayni mantik -- burada da
    kendi kontrolumuzu yapiyoruz ki blok yerlesimi grid'i ikiye bolmesin."""
    if not free_cells:
        return True
    start = next(iter(free_cells))
    visited = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (r + dr, c + dc)
            if nxt in free_cells and nxt not in visited:
                visited.add(nxt)
                stack.append(nxt)
    return visited == free_cells


def generate_zip(rng: random.Random, difficulty: int, max_block_attempts: int = 8,
                  max_path_attempts_per_block: int = 6, gen_max_expansions: int = 25000):
    """
    ONEMLI (hareket ettirilemez blok / immovable block ozelligi):
    Bu grid 10x10 sabit, ve generator OPSIYONEL olarak EN FAZLA 4 tane
    "blocked_cells" (hareket ettirilemez blok) yerlestirebilir -- bkz.
    README'deki kural. Bu ZORUNLU degil: n_blocks 0 da olabilir, katilimci
    kendi generator'inda hic blok kullanmayabilir.

    Blok varken artik duz boustrophedon (yilanvari) kisayolu KULLANILAMAZ,
    cunku bir hucreyi atlamak yol icindeki komsuluk (adjacency) kuralini
    bozar. Onun yerine zaten var olan ve KANITLANMIS solve_zip_warnsdorff
    solver'ini URETIM motoru olarak tersine cagiriyoruz: bir start/end cifti
    veriyoruz, o da bloklardan kacinarak serbest hucrelerin TAMAMINI
    kapsayan gercek bir Hamiltonian path buluyor.

    PERFORMANS ("merdiven" / ladder stratejisi): rastgele start/end
    ciftleri bazen Warnsdorff sezgiselini cok zorlayip aramayi saniyelerce
    suruklebiliyordu. Bunu iki sekilde sinirliyoruz:
      1. start/end adaylarini ONCE kose hucrelerinden secmeye calisiyoruz
         (kose-baslangicli Hamiltonian path aramasi bilinen sekilde cok
         daha az backtracking gerektirir).
      2. Her deneme icin dusuk bir max_expansions (gen_max_expansions)
         kullaniyoruz -- COZMEK icin degil, sadece "bu konfigurasyon
         kolayca cozuluyor mu" diye HIZLI test etmek icin. Basarisiz
         olursa once farkli start/end, sonra farkli blok yerlesimi, o da
         basarisiz olursa n_blocks'u BIR AZALTIP tekrar dener -- en kotu
         durumda n_blocks=0'a duser ki bu her zaman aninda basarili olan
         (blok yok, duz boustrophedon) garanti bir yol.

    Bulunan path hem checkpoint'lerin ornekleneceji kaynak, hem de witness
    cozum olarak donuyor -- yani uretilen HER puzzle otomatik olarak
    cozulebilirligi kanitlanmis oluyor (build_bank.py'daki validate_solution
    kontrolu de bunu ayrica dogruluyor, bu ikinci bir guvenlik katmani).
    """
    size = 10
    rows = cols = size
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    corners = [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]

    max_blocks = min(4, max(0, difficulty))
    n_blocks_target = rng.randint(0, max_blocks) if max_blocks > 0 else 0

    for n_blocks in range(n_blocks_target, -1, -1):  # basarisiz olursa blok sayisini azalt
        if n_blocks == 0:
            path = []
            for r in range(rows):
                col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
                for c in col_range:
                    path.append((r, c))
            blocked: set[tuple[int, int]] = set()
        else:
            path = None
            blocked = None
            for _block_attempt in range(max_block_attempts):
                candidate_blocked = set(rng.sample(all_cells, n_blocks))
                free_cells = set(all_cells) - candidate_blocked
                if not _zip_free_cells_connected(free_cells, rows, cols):
                    continue

                free_list = list(free_cells)
                corner_candidates = [c for c in corners if c in free_cells]
                endpoint_pool = corner_candidates if len(corner_candidates) >= 2 else free_list

                found = False
                for _path_attempt in range(max_path_attempts_per_block):
                    start, end = rng.sample(endpoint_pool, 2) if len(endpoint_pool) >= 2 else rng.sample(free_list, 2)
                    temp_puzzle = {
                        "size": [rows, cols],
                        "blocked_cells": [list(c) for c in candidate_blocked],
                        "checkpoints": [{"order": 1, "pos": list(start)}, {"order": 2, "pos": list(end)}],
                    }
                    result, _trace = solve_zip_warnsdorff(temp_puzzle, record_trace=False,
                                                           max_expansions=gen_max_expansions)
                    if result.solved:
                        path = [tuple(c) for c in result.solution]
                        blocked = candidate_blocked
                        found = True
                        break
                if found:
                    break
            if path is None:
                continue  # bu n_blocks seviyesinde basarili olamadik -- bir azalt

        n_checkpoints = min(5 + difficulty // 2, len(path))
        middle_indices = (rng.sample(range(1, len(path) - 1), max(0, n_checkpoints - 2))
                           if n_checkpoints > 2 else [])
        checkpoint_indices = sorted({0, len(path) - 1} | set(middle_indices))
        checkpoints = [
            {"order": i + 1, "pos": list(path[idx])}
            for i, idx in enumerate(checkpoint_indices)
        ]
        puzzle = {
            "game": "zip",
            "size": [rows, cols],
            "checkpoints": checkpoints,
            "blocked_cells": [list(c) for c in blocked],
        }
        solution = [list(cell) for cell in path]
        return puzzle, solution

    raise RuntimeError("generate_zip: n_blocks=0 fallback bile basarisiz oldu (olmamali)")