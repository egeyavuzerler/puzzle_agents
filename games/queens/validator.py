"""
games/queens/validator.py

QUEENS oyunu (resim 2'deki oyun):
  - size = [rows, cols] (genelde kare: rows == cols == bölge sayısı)
  - regions: rows x cols boyutunda 2D dizi, her hücrenin hangi renk
    bölgesine ait olduğunu gösteren tam sayı id'ler

Amaç: her satırda, her sütunda ve her renk bölgesinde TAM 1 kraliçe
olacak şekilde kraliçeleri yerleştir. İki kraliçe köşegen dahil
birbirine bitişik OLAMAZ.

Puzzle şeması:
{
  "game": "queens",
  "size": [8, 8],
  "regions": [[0,0,1,1,1,2,2,2], [0,0,1,1,3,3,2,2], ...]   # 8 satır, her biri 8 eleman
}

Solution şeması:
  solution = [[r0, c0], [r1, c1], ..., [r7, c7]]   # her satırdan tam 1 kraliçe pozisyonu
"""

from core.validator import BasePuzzleValidator


class QueensValidator(BasePuzzleValidator):
    game_name = "queens"

    # ---------- PUZZLE ŞEKLİ KONTROLÜ ----------
    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "queens":
            return False, "game alanı 'queens' değil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatında olmalı"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmalı"

        regions = puzzle.get("regions")
        if not regions or len(regions) != rows:
            return False, "regions satır sayısı size ile uyuşmuyor"
        for row in regions:
            if len(row) != cols:
                return False, "regions sütun sayısı size ile uyuşmuyor"

        distinct_regions = {rid for row in regions for rid in row}
        if len(distinct_regions) != rows:
            return False, (
                f"bölge sayısı ({len(distinct_regions)}) satır sayısına ({rows}) eşit olmalı "
                "(her satır/sütun/bölgede tam 1 kraliçe olabilmesi için)"
            )

        return True, None

    # ---------- ÇÖZÜM KONTROLÜ ----------
    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution or not isinstance(solution, list):
            return False, "solution boş ya da liste değil"

        rows, cols = puzzle["size"]
        regions = puzzle["regions"]

        if len(solution) != rows:
            return False, f"kraliçe sayısı {len(solution)}, beklenen {rows}"

        positions = [tuple(p) for p in solution]

        seen_rows, seen_cols, seen_regions = set(), set(), set()
        for (r, c) in positions:
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"{(r, c)} grid dışında"
            if r in seen_rows:
                return False, f"satır {r} içinde birden fazla kraliçe"
            if c in seen_cols:
                return False, f"sütun {c} içinde birden fazla kraliçe"
            region_id = regions[r][c]
            if region_id in seen_regions:
                return False, f"bölge {region_id} içinde birden fazla kraliçe"
            seen_rows.add(r)
            seen_cols.add(c)
            seen_regions.add(region_id)

        # komşuluk kontrolü (köşegen dahil)
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                r1, c1 = positions[i]
                r2, c2 = positions[j]
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    return False, f"{(r1, c1)} ve {(r2, c2)} birbirine bitişik (köşegen dahil)"

        return True, None
