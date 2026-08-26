"""
games/tango/validator.py

TANGO (LinkedIn oyunu) - bloklu (dokunulmaz) hucre destekli versiyon.
  - size = [rows, cols]
  - blocked_cells: DOKUNULMAZ hucreler (sun/moon konulamaz, bos kalir)
  - her hucre (bloklu olmayan) "sun" ya da "moon"
  - her satir/sutunda (bloklu haric, SERBEST hucreler arasinda) esit sayida
    sun/moon -- bu yuzden her satir/sutunun serbest hucre sayisi CIFT olmali
  - yan yana/alt alta 3 ayni sembol OLAMAZ
  - constraints: bazi komsu (ikisi de serbest) hucre ciftleri arasinda
    "equal"/"opposite" kisiti
  - prefilled: bazi serbest hucreler bastan verilmis ipucu
"""

from core.validator import BasePuzzleValidator


class TangoValidator(BasePuzzleValidator):
    game_name = "tango"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "tango":
            return False, "game alani 'tango' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
        for (r, c) in blocked:
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"blocked_cell {(r, c)} grid disinda"

        for r in range(rows):
            free_in_row = cols - sum(1 for c in range(cols) if (r, c) in blocked)
            if free_in_row % 2 != 0:
                return False, f"satir {r}: serbest hucre sayisi ({free_in_row}) tek -- esit dagilim imkansiz"
        for c in range(cols):
            free_in_col = rows - sum(1 for r in range(rows) if (r, c) in blocked)
            if free_in_col % 2 != 0:
                return False, f"sutun {c}: serbest hucre sayisi ({free_in_col}) tek -- esit dagilim imkansiz"

        prefilled_positions = set()
        for cell in puzzle.get("prefilled", []):
            r, c = cell["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"prefilled {cell} grid disinda"
            if (r, c) in blocked:
                return False, f"prefilled {cell} bloklu bir hucrede"
            if cell["value"] not in ("sun", "moon"):
                return False, f"prefilled {cell} value 'sun'/'moon' olmali"
            if (r, c) in prefilled_positions:
                return False, f"prefilled hucre tekrar ediyor: {(r, c)}"
            prefilled_positions.add((r, c))

        for con in puzzle.get("constraints", []):
            r1, c1 = con["cell1"]
            r2, c2 = con["cell2"]
            if not (0 <= r1 < rows and 0 <= c1 < cols and 0 <= r2 < rows and 0 <= c2 < cols):
                return False, f"constraint {con} grid disinda"
            if (r1, c1) in blocked or (r2, c2) in blocked:
                return False, f"constraint {con} bloklu bir hucreye degiyor"
            if abs(r1 - r2) + abs(c1 - c2) != 1:
                return False, f"constraint {con} komsu olmayan hucreler arasinda"
            if con["type"] not in ("equal", "opposite"):
                return False, f"constraint {con} type 'equal'/'opposite' olmali"

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        blocked = {tuple(c) for c in puzzle.get("blocked_cells", [])}
        if len(solution) != rows or any(len(row) != cols for row in solution):
            return False, "solution boyutu size ile uyusmuyor"

        for r in range(rows):
            for c in range(cols):
                val = solution[r][c]
                if (r, c) in blocked:
                    if val != "blocked":
                        return False, f"({r},{c}) bloklu ama solution'da '{val}' yaziyor, 'blocked' olmali"
                elif val not in ("sun", "moon"):
                    return False, f"({r},{c}) degeri 'sun'/'moon' degil: {val}"

        for cell in puzzle.get("prefilled", []):
            r, c = cell["pos"]
            if solution[r][c] != cell["value"]:
                return False, f"prefilled ({r},{c})={cell['value']} ile cozum celisiyor"

        for r in range(rows):
            free_in_row = cols - sum(1 for c in range(cols) if (r, c) in blocked)
            suns = sum(1 for c in range(cols) if solution[r][c] == "sun")
            if suns != free_in_row // 2:
                return False, f"satir {r}: {suns} sun, beklenen {free_in_row // 2}"
        for c in range(cols):
            free_in_col = rows - sum(1 for r in range(rows) if (r, c) in blocked)
            suns = sum(1 for r in range(rows) if solution[r][c] == "sun")
            if suns != free_in_col // 2:
                return False, f"sutun {c}: {suns} sun, beklenen {free_in_col // 2}"

        for r in range(rows):
            for c in range(cols - 2):
                if solution[r][c] in ("sun", "moon") and solution[r][c] == solution[r][c + 1] == solution[r][c + 2]:
                    return False, f"satir {r}, sutun {c}-{c+2}: 3 art arda ayni sembol"
        for c in range(cols):
            for r in range(rows - 2):
                if solution[r][c] in ("sun", "moon") and solution[r][c] == solution[r + 1][c] == solution[r + 2][c]:
                    return False, f"sutun {c}, satir {r}-{r+2}: 3 art arda ayni sembol"

        for con in puzzle.get("constraints", []):
            r1, c1 = con["cell1"]
            r2, c2 = con["cell2"]
            v1, v2 = solution[r1][c1], solution[r2][c2]
            if con["type"] == "equal" and v1 != v2:
                return False, f"constraint {con}: '=' ama {v1} != {v2}"
            if con["type"] == "opposite" and v1 == v2:
                return False, f"constraint {con}: 'x' ama {v1} == {v2}"

        return True, None
