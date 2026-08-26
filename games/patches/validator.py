"""
games/patches/validator.py

PATCHES (LinkedIn oyunu, Shikaku varyasyonu):
  - size = [rows, cols]
  - clues: her biri {"pos": [r,c], "area": N, "shape": "square"|"wide"|"tall"|"any"}
  - Amac: izgarayi dikdortgenlere (patch) bolmek. Her patch TAM BIR clue
    icermeli, clue'nun area'si kadar hucre kaplamali, shape kisitina uymali.
    Bosluk yok, cakisma yok, tum izgara kaplanmali.
"""

from core.validator import BasePuzzleValidator


class PatchesValidator(BasePuzzleValidator):
    game_name = "patches"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "patches":
            return False, "game alani 'patches' degil"

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
        total_area = 0
        for clue in clues:
            r, c = clue["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"clue {clue} grid disinda"
            if (r, c) in positions:
                return False, f"clue pozisyonu tekrar ediyor: {(r, c)}"
            positions.add((r, c))

            area = clue["area"]
            if not (1 <= area <= rows * cols):
                return False, f"clue {clue} area'si gecersiz"
            if clue["shape"] not in ("square", "wide", "tall", "any"):
                return False, f"clue {clue} shape 'square'/'wide'/'tall'/'any' olmali"
            total_area += area

        if total_area != rows * cols:
            return False, f"clue area'lari toplami ({total_area}) grid alanina ({rows*cols}) esit degil"

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        clues = puzzle["clues"]
        if len(solution) != len(clues):
            return False, f"dikdortgen sayisi {len(solution)}, beklenen {len(clues)} (clue sayisi)"

        clue_positions = [tuple(c["pos"]) for c in clues]

        rects = []
        for i, rect in enumerate(solution):
            r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
            if not (0 <= r0 <= r1 < rows and 0 <= c0 <= c1 < cols):
                return False, f"dikdortgen {i} grid disinda ya da gecersiz: {rect}"
            rects.append((r0, c0, r1, c1))

            height = r1 - r0 + 1
            width = c1 - c0 + 1
            area = height * width
            clue = clues[i]
            if area != clue["area"]:
                return False, f"dikdortgen {i} alani {area}, clue area'si {clue['area']}"

            shape = clue["shape"]
            if shape == "square" and width != height:
                return False, f"dikdortgen {i} 'square' olmaliydi ama {width}x{height}"
            if shape == "wide" and width <= height:
                return False, f"dikdortgen {i} 'wide' olmaliydi ama {width}x{height}"
            if shape == "tall" and height <= width:
                return False, f"dikdortgen {i} 'tall' olmaliydi ama {width}x{height}"

            cr, cc = clue_positions[i]
            if not (r0 <= cr <= r1 and c0 <= cc <= c1):
                return False, f"dikdortgen {i} kendi clue'sunu ({cr},{cc}) icermiyor"

            for j, (or_, oc) in enumerate(clue_positions):
                if j == i:
                    continue
                if r0 <= or_ <= r1 and c0 <= oc <= c1:
                    return False, f"dikdortgen {i} baska bir clue'yu ({or_},{oc}) da iceriyor"

        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                r0a, c0a, r1a, c1a = rects[i]
                r0b, c0b, r1b, c1b = rects[j]
                overlap = not (r1a < r0b or r1b < r0a or c1a < c0b or c1b < c0a)
                if overlap:
                    return False, f"dikdortgen {i} ve {j} cakisiyor"

        total_area = sum((r1 - r0 + 1) * (c1 - c0 + 1) for (r0, c0, r1, c1) in rects)
        if total_area != rows * cols:
            return False, f"toplam kaplanan alan ({total_area}) grid alanina ({rows*cols}) esit degil"

        return True, None
