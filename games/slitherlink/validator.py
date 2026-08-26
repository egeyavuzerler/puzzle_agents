"""
games/slitherlink/validator.py

SLITHERLINK:
  - size = [rows, cols] -- rows x cols HUCRE (nokta grid'i (rows+1) x (cols+1))
  - clues: rows x cols'lik 2D dizi, her eleman 0-4 arasi bir sayi ya da null
  - Amac: nokta grid'i uzerinde TEK bir kapali dongu (loop) ciz. Her noktanin
    derecesi 0 ya da 2 olmali, dongu tek parca (bagli) olmali, her ipuclu
    hucrenin etrafindaki kenar sayisi ipucuyla eslesmeli.
"""

from collections import defaultdict

from core.validator import BasePuzzleValidator


class SlitherlinkValidator(BasePuzzleValidator):
    game_name = "slitherlink"

    def _cell_edges(self, r, c):
        top = frozenset([(r, c), (r, c + 1)])
        bottom = frozenset([(r + 1, c), (r + 1, c + 1)])
        left = frozenset([(r, c), (r + 1, c)])
        right = frozenset([(r, c + 1), (r + 1, c + 1)])
        return [top, bottom, left, right]

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "slitherlink":
            return False, "game alani 'slitherlink' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        clues = puzzle.get("clues")
        if not clues or len(clues) != rows:
            return False, "clues satir sayisi size ile uyusmuyor"
        for row in clues:
            if len(row) != cols:
                return False, "clues sutun sayisi size ile uyusmuyor"
            for v in row:
                if v is not None and v not in (0, 1, 2, 3, 4):
                    return False, f"gecersiz clue degeri: {v}"

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        clues = puzzle["clues"]

        edges = set()
        for e in solution:
            if len(e) != 2:
                return False, f"gecersiz kenar: {e}"
            (r1, c1), (r2, c2) = e[0], e[1]
            if not (0 <= r1 <= rows and 0 <= c1 <= cols and 0 <= r2 <= rows and 0 <= c2 <= cols):
                return False, f"kenar {e} grid disinda"
            if abs(r1 - r2) + abs(c1 - c2) != 1:
                return False, f"kenar {e} komsu olmayan noktalar arasinda"
            edges.add(frozenset([(r1, c1), (r2, c2)]))

        if not edges:
            return False, "hic kenar secilmemis"

        deg = defaultdict(int)
        adj = defaultdict(list)
        for e in edges:
            a, b = tuple(e)
            deg[a] += 1
            deg[b] += 1
            adj[a].append(b)
            adj[b].append(a)
        for dot, d in deg.items():
            if d not in (0, 2):
                return False, f"nokta {dot} derecesi {d} (0 ya da 2 olmali)"

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
            return False, "dongu tek parca (bagli) degil"
        if len(edges) != len(deg):
            return False, "kenar sayisi ile nokta sayisi eslesmiyor (tek basit dongu degil)"

        for r in range(rows):
            for c in range(cols):
                clue = clues[r][c]
                if clue is None:
                    continue
                cnt = sum(1 for e in self._cell_edges(r, c) if e in edges)
                if cnt != clue:
                    return False, f"hucre ({r},{c}): clue={clue} ama gercek kenar sayisi {cnt}"

        return True, None
