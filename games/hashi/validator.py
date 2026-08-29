"""
games/hashi/validator.py

HASHIWOKAKERO (Bridges):
  - size = [rows, cols]
  - islands: her biri {"pos": [r,c], "value": N} -- N, o adaya baglanmasi
    gereken TOPLAM kopru sayisi
  - Amac: adalari yatay/dikey koprulerle (1 ya da 2 telli) bagla:
      * kopruler sadece ayni satir/sutundaki, ARADA BASKA ADA OLMAYAN
        iki ada arasinda olabilir
      * bir baglantida en fazla 2 kopru olabilir
      * kopruler birbirini KESEMEZ
      * her adanin uzerindeki kopru sayisi toplami, adanin degerine esit olmali
      * TUM adalar, kopruler araciligiyla TEK bir bagli ag olusturmali

  - forbidden_connections (OPSIYONEL): [[[r,c],[r,c]], ...] -- her ikili,
    aralarinda GORUS HATTI olan (yani normalde kopru kurulabilecek) iki
    adayi belirtir, ama bu ikisi arasinda COZUMDE KESINLIKLE kopru
    OLAMAZ. Bu, katilimciyi o "kesik hat"i goz ardi edip adalari BASKA
    bir yoldan baglamaya zorlar.
"""

from collections import defaultdict

from core.validator import BasePuzzleValidator


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


class HashiValidator(BasePuzzleValidator):
    game_name = "hashi"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "hashi":
            return False, "game alani 'hashi' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        islands = puzzle.get("islands")
        if not islands or len(islands) < 3:
            return False, "en az 3 ada olmali"

        positions = set()
        for isl in islands:
            r, c = isl["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"ada {isl} grid disinda"
            if (r, c) in positions:
                return False, f"ada pozisyonu tekrar ediyor: {(r, c)}"
            positions.add((r, c))
            if not (1 <= isl["value"] <= 8):
                return False, f"ada {isl} value'su 1-8 araliginda olmali"

        seen_forbidden = set()
        for pair in puzzle.get("forbidden_connections", []):
            if len(pair) != 2:
                return False, f"forbidden_connections ciftinde {pair} 2 ada olmali"
            a, b = tuple(pair[0]), tuple(pair[1])
            if a == b:
                return False, f"forbidden_connections {pair} ayni adayi kendine bagliyor"
            if a not in positions or b not in positions:
                return False, f"forbidden_connections {pair} gecerli bir ada pozisyonuna isaret etmiyor"
            key = frozenset([a, b])
            if key in seen_forbidden:
                return False, f"forbidden_connections {pair} tekrar ediyor"
            seen_forbidden.add(key)

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        islands = {tuple(i["pos"]): i["value"] for i in puzzle["islands"]}
        island_positions = set(islands.keys())

        forbidden = {frozenset([tuple(pair[0]), tuple(pair[1])]) for pair in puzzle.get("forbidden_connections", [])}

        edges = []
        for b in solution:
            a, bb = tuple(b["from"]), tuple(b["to"])
            cnt = b["count"]
            if a not in island_positions or bb not in island_positions:
                return False, f"kenar {a}-{bb} ada olmayan noktalara degiyor"
            if a[0] != bb[0] and a[1] != bb[1]:
                return False, f"kenar {a}-{bb} duz (yatay/dikey) degil"
            if cnt not in (1, 2):
                return False, f"kenar {a}-{bb} count degeri gecersiz: {cnt}"
            if frozenset([a, bb]) in forbidden:
                return False, f"kenar {a}-{bb} forbidden_connections'da yasakli"
            if a[0] == bb[0]:
                r = a[0]
                c1, c2 = sorted([a[1], bb[1]])
                for cc in range(c1 + 1, c2):
                    if (r, cc) in island_positions:
                        return False, f"kenar {a}-{bb} arasinda baska ada var"
            else:
                c = a[1]
                r1, r2 = sorted([a[0], bb[0]])
                for rr in range(r1 + 1, r2):
                    if (rr, c) in island_positions:
                        return False, f"kenar {a}-{bb} arasinda baska ada var"
            edges.append((a, bb, cnt))

        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                a1, b1, _ = edges[i]
                a2, b2, _ = edges[j]
                if (a1, b1) == (a2, b2) or (a1, b1) == (b2, a2):
                    continue
                if _segments_cross((a1, b1), (a2, b2)):
                    return False, f"kenarlar kesisiyor: {a1}-{b1} ve {a2}-{b2}"

        sums = defaultdict(int)
        adj = defaultdict(set)
        for (a, b, cnt) in edges:
            sums[a] += cnt
            sums[b] += cnt
            adj[a].add(b)
            adj[b].add(a)
        for pos, val in islands.items():
            if sums[pos] != val:
                return False, f"ada {pos}: baglanti toplami {sums[pos]}, beklenen {val}"

        start = next(iter(island_positions))
        visited = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        if len(visited) != len(island_positions):
            return False, "adalar tek bagli ag olusturmuyor"

        return True, None
