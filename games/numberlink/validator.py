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

  - portals (OPSIYONEL): [[[r1,c1],[r2,c2]], ...] -- her ikili, birbirine
    "isinlanma" ile baglanan iki hucreyi belirtir. Bir renk yolu bu iki
    hucreyi (GRID KOMSULUGU OLMADAN) ardisik olarak kullanirsa, bu ikisi
    o rengin yolunda birbirine BAGLI sayilir (normal grid-komsulugu gibi).
    Bu, path-bazli mantigi degistirmeden yeni bir baglanti imkani sunar --
    dogru cozumu bulmak icin artik SADECE yerel/fiziksel komsuluk yeterli
    degil, portallari da hesaba katmak gerekir.
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

        portals = puzzle.get("portals", [])
        seen_portal_cells = set()
        for portal in portals:
            if not (isinstance(portal, (list, tuple)) and len(portal) == 2):
                return False, f"portal {portal} tam 2 hucreden olusmali"
            a, b = tuple(portal[0]), tuple(portal[1])
            if a == b:
                return False, f"portal {portal} ayni hucreyi kendine bagliyor"
            for cell in (a, b):
                r, c = cell
                if not (0 <= r < rows and 0 <= c < cols):
                    return False, f"portal hucresi {cell} grid disinda"
                if cell in seen_portal_cells:
                    return False, f"portal hucresi {cell} birden fazla portalde kullaniliyor"
                seen_portal_cells.add(cell)

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

        portal_partner = {}
        for portal in puzzle.get("portals", []):
            a, b = tuple(portal[0]), tuple(portal[1])
            portal_partner[a] = b
            portal_partner[b] = a

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
                partner = portal_partner.get((r, c))
                if partner is not None and partner in cellset:
                    d += 1
                    adj[(r, c)].append(partner)
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
