"""
games/lits/validator.py

LITS:
  - size = [rows, cols]
  - regions: rows x cols'lik 2D dizi, her hucrenin hangi bolgeye ait
    oldugunu gosteren id (her bolge en az 4 hucre icermeli)
  - Amac: HER bolgede TAM 4 hucreyi golgele, golgelenen 4 hucre L, I, T
    ya da S tetromino sekillerinden birini olusturmali (donusler VE
    yansimalar serbest -- yani "L" hem L hem J seklini, "S" hem S hem Z
    seklini kapsar). Ek kisitlar:
      * TUM golgeli hucreler (bolge sinirlari boyunca) TEK bir bagli
        butun olusturmali
      * hicbir 2x2 alan tamamen golgeli olamaz
      * birbirine komsu (dokunan) iki tetromino AYNI TIPTE olamaz

  - forced_shaded (OPSIYONEL): [[r,c], ...] -- bu hucrelerin COZUMDE
    KESINLIKLE golgeli olmasi zorunludur. Hangi tetromino'ya ait olduklari
    ya da hangi tipte olduklari SOYLENMEZ -- sadece "bu hucre kesinlikle
    golgeli" bilgisi verilir. Bu, cozum uzayini daraltir ama HANGI sekle
    ait oldugunu ve komsu bolgelerle nasil uyusmasi gerektigini bulmak
    yine de katilimciya kalir.
"""

from collections import defaultdict

from core.validator import BasePuzzleValidator

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
    return variants


_SHAPE_TO_TYPE = {}
for _type_name, _base in _BASE_SHAPES.items():
    for _variant in _all_orientations(_base):
        _SHAPE_TO_TYPE[_variant] = _type_name


def _classify(cells):
    """4 hucrelik bir kumenin L/I/T/S'den hangisi oldugunu dondurur,
    hicbiri degilse None (orn. O-sekli/kare tetromino)."""
    return _SHAPE_TO_TYPE.get(_normalize(cells))


def _touches(cells_a, cells_b):
    for (r, c) in cells_a:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (r + dr, c + dc) in cells_b:
                return True
    return False


class LitsValidator(BasePuzzleValidator):
    game_name = "lits"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "lits":
            return False, "game alani 'lits' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        regions = puzzle.get("regions")
        if not regions or len(regions) != rows:
            return False, "regions satir sayisi size ile uyusmuyor"
        for row in regions:
            if len(row) != cols:
                return False, "regions sutun sayisi size ile uyusmuyor"

        region_sizes = defaultdict(int)
        for r in range(rows):
            for c in range(cols):
                region_sizes[regions[r][c]] += 1
        for rid, sz in region_sizes.items():
            if sz < 4:
                return False, f"bolge {rid} sadece {sz} hucreli (en az 4 olmali)"
        if len(region_sizes) < 4:
            return False, "en az 4 bolge olmali"

        forced_shaded = puzzle.get("forced_shaded", [])
        seen_forced = set()
        for cell in forced_shaded:
            r, c = cell
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"forced_shaded hucresi {cell} grid disinda"
            if (r, c) in seen_forced:
                return False, f"forced_shaded hucresi {cell} tekrar ediyor"
            seen_forced.add((r, c))

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        regions = puzzle["regions"]

        shaded = set()
        for cell in solution:
            r, c = cell
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"hucre {cell} grid disinda"
            if (r, c) in shaded:
                return False, f"hucre {cell} tekrar ediyor"
            shaded.add((r, c))

        for cell in puzzle.get("forced_shaded", []):
            if tuple(cell) not in shaded:
                return False, f"forced_shaded hucresi {tuple(cell)} golgeli degil (zorunlu)"

        for r in range(rows - 1):
            for c in range(cols - 1):
                if all((r + dr, c + dc) in shaded for dr in (0, 1) for dc in (0, 1)):
                    return False, f"({r},{c}) koseli 2x2 alan tamamen golgeli"

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
        if len(visited) != len(shaded):
            return False, "golgeli hucreler tek bagli degil"

        region_shaded = defaultdict(set)
        for (r, c) in shaded:
            region_shaded[regions[r][c]].add((r, c))

        all_region_ids = {regions[r][c] for r in range(rows) for c in range(cols)}
        for rid in all_region_ids:
            cells = region_shaded.get(rid)
            if not cells or len(cells) != 4:
                return False, f"bolge {rid}: {len(cells) if cells else 0} golgeli hucre (tam 4 olmali)"
            shape_type = _classify(cells)
            if shape_type is None:
                return False, f"bolge {rid}'deki sekil L/I/T/S degil: {sorted(cells)}"
            region_shaded[rid] = (cells, shape_type)

        region_ids = list(region_shaded.keys())
        for i in range(len(region_ids)):
            for j in range(i + 1, len(region_ids)):
                cells_a, type_a = region_shaded[region_ids[i]]
                cells_b, type_b = region_shaded[region_ids[j]]
                if type_a == type_b and _touches(cells_a, cells_b):
                    return False, f"bolge {region_ids[i]} ve {region_ids[j]} ayni tip ({type_a}) ve komsu"

        return True, None
