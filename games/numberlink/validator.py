"""
games/numberlink/validator.py

NUMBERLINK (Flow tarzi):
  - size = [rows, cols]
  - endpoints: her renk icin TAM 2 tane {"color": id, "pos": [r,c]}
  - Amac: her rengin iki endpoint'ini, KENDI KENDINE DEGMEYEN basit bir
    yolla birlestir. Farkli renklerin hucreleri birbirine komsu olabilir,
    ama bir rengin kendi hucreleri arasinda fazladan komsuluk OLAMAZ.
  - NOT: bu varyant "Flow" tarzidir -- izgaranin HER hucresinin dolu olmasi
    SART DEGIL (bazi hucreler bos kalabilir).
"""

from collections import defaultdict

from core.validator import BasePuzzleValidator


class NumberlinkValidator(BasePuzzleValidator):
    game_name = "numberlink"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "numberlink":
            return False, "game alani 'numberlink' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        endpoints = puzzle.get("endpoints")
        if not endpoints or len(endpoints) < 4:
            return False, "en az 2 renk (4 endpoint) olmali"

        by_color = defaultdict(list)
        seen_positions = set()
        for e in endpoints:
            r, c = e["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"endpoint {e} grid disinda"
            if (r, c) in seen_positions:
                return False, f"endpoint pozisyonu tekrar ediyor: {(r, c)}"
            seen_positions.add((r, c))
            by_color[e["color"]].append((r, c))

        for color, positions in by_color.items():
            if len(positions) != 2:
                return False, f"renk {color}: {len(positions)} endpoint var, tam 2 olmali"

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        if len(solution) != rows or any(len(row) != cols for row in solution):
            return False, "solution boyutu size ile uyusmuyor"

        endpoints = puzzle["endpoints"]
        ep_by_color = defaultdict(list)
        for e in endpoints:
            ep_by_color[e["color"]].append(tuple(e["pos"]))

        for color, positions in ep_by_color.items():
            for (r, c) in positions:
                if solution[r][c] != color:
                    return False, f"endpoint ({r},{c}) solution'da renk {solution[r][c]}, beklenen {color}"

        colors_present = {solution[r][c] for r in range(rows) for c in range(cols) if solution[r][c] is not None}

        for color in colors_present:
            if color not in ep_by_color:
                return False, f"solution'da tanimsiz bir renk var: {color}"

        for color, eps in ep_by_color.items():
            cells = [(r, c) for r in range(rows) for c in range(cols) if solution[r][c] == color]
            eps_set = set(eps)
            if not eps_set.issubset(set(cells)):
                return False, f"renk {color}'in endpoint'leri kendi yolunda degil"

            cellset = set(cells)
            deg = {}
            adj = defaultdict(list)
            for (r, c) in cells:
                d = 0
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (r + dr, c + dc)
                    if nb in cellset:
                        d += 1
                        adj[(r, c)].append(nb)
                deg[(r, c)] = d

            for cell in cells:
                expected = 1 if cell in eps_set else 2
                if deg[cell] != expected:
                    return False, f"renk {color} hucre {cell}: derece {deg[cell]}, beklenen {expected}"

            start = cells[0]
            visited = {start}
            stack = [start]
            while stack:
                u = stack.pop()
                for v in adj[u]:
                    if v not in visited:
                        visited.add(v)
                        stack.append(v)
            if len(visited) != len(cells):
                return False, f"renk {color} tek parca (bagli) degil"

        return True, None
