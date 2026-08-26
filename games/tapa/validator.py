"""
games/tapa/validator.py

TAPA:
  - size = [rows, cols]
  - clues: her biri {"pos": [r,c], "numbers": [n1, n2, ...]} -- clue
    hucreleri ASLA boyanmaz
  - Amac: geri kalan hucreleri boya/boyama, oyle ki:
      * her clue hucresinin cevresindeki (en fazla 8) komsuda, SAAT
        YONUNDE ardisik boyali bloklarin uzunluklari, clue'nun sayi
        listesiyle (dairesel/rotasyon bagimsiz) eslesmeli
        ("numbers": [0] -> hic boyali komsu yok)
      * TUM boyali hucreler TEK bagli butun olusturmali
      * hicbir 2x2 alan tamamen boyali olamaz
"""

from core.validator import BasePuzzleValidator

_CLOCKWISE_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


def _ordered_neighbors(pos, rows, cols):
    r, c = pos
    result = []
    for dr, dc in _CLOCKWISE_OFFSETS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            result.append((nr, nc))
    return result


def _cyclic_runs(bool_list):
    n = len(bool_list)
    if n == 0:
        return []
    if all(bool_list):
        return [n]
    if not any(bool_list):
        return []
    start = bool_list.index(False)
    rotated = bool_list[start:] + bool_list[:start]
    runs = []
    cur = 0
    for v in rotated:
        if v:
            cur += 1
        else:
            if cur > 0:
                runs.append(cur)
            cur = 0
    if cur > 0:
        runs.append(cur)
    return runs


def _is_cyclic_rotation(a, b):
    if len(a) != len(b):
        return False
    if not a:
        return True
    doubled = a + a
    for i in range(len(a)):
        if doubled[i:i + len(a)] == b:
            return True
    return False


class TapaValidator(BasePuzzleValidator):
    game_name = "tapa"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "tapa":
            return False, "game alani 'tapa' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        clues = puzzle.get("clues")
        if not clues:
            return False, "en az 1 clue olmali"

        positions = set()
        for clue in clues:
            r, c = clue["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"clue {clue} grid disinda"
            if (r, c) in positions:
                return False, f"clue pozisyonu tekrar ediyor: {(r, c)}"
            positions.add((r, c))
            numbers = clue["numbers"]
            if not numbers:
                return False, f"clue {clue} numbers bos olamaz"
            if numbers == [0]:
                continue
            if any(n < 1 or n > 8 for n in numbers):
                return False, f"clue {clue} numbers 1-8 araliginda olmali"
            n_neighbors = len(_ordered_neighbors((r, c), rows, cols))
            k = len(numbers)
            min_needed = sum(numbers) if k == 1 else sum(numbers) + k
            if min_needed > n_neighbors:
                return False, f"clue {clue} bu pozisyon icin imkansiz (komsu sayisi yetersiz)"

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        clue_positions = {tuple(c["pos"]): c["numbers"] for c in puzzle["clues"]}

        shaded = set()
        for cell in solution:
            r, c = cell
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"hucre {cell} grid disinda"
            if (r, c) in clue_positions:
                return False, f"clue hucresi boyali: {(r, c)}"
            if (r, c) in shaded:
                return False, f"hucre {cell} tekrar ediyor"
            shaded.add((r, c))

        if not shaded:
            return False, "hic boyali hucre yok"

        for r in range(rows - 1):
            for c in range(cols - 1):
                if all((r + dr, c + dc) in shaded for dr in (0, 1) for dc in (0, 1)):
                    return False, f"({r},{c}) koseli 2x2 alan tamamen boyali"

        start = next(iter(shaded))
        visited = {start}
        stack = [start]
        while stack:
            u = stack.pop()
            r, c = u
            for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if nb in shaded and nb not in visited:
                    visited.add(nb)
                    stack.append(nb)
        if len(visited) != len(shaded):
            return False, "boyali hucreler tek bagli degil"

        for pos, expected in clue_positions.items():
            nbs = _ordered_neighbors(pos, rows, cols)
            bools = [nb in shaded for nb in nbs]
            runs = _cyclic_runs(bools)
            if runs == []:
                if expected != [0]:
                    return False, f"clue {pos}: boyali komsu yok ama {expected} bekleniyordu"
            elif not _is_cyclic_rotation(runs, expected):
                return False, f"clue {pos}: gercek desen {runs}, beklenen {expected}"

        return True, None
