"""
games/yinyang/validator.py

YIN-YANG:
  - size = [rows, cols]
  - prefilled: bazi hucreler bastan verilmis ipucu ({"pos":[r,c],"color":"black"|"white"})
  - Amac: TUM hucreleri siyah/beyaz boya:
      * TUM siyah hucreler kendi aralarinda bagli olmali
      * TUM beyaz hucreler kendi aralarinda bagli olmali (ikisi AYNI ANDA)
      * hicbir 2x2 alan tek renk olamaz

NOT: bu oyunun uretimi digerlerinden cok daha zor bir kombinatorik
problem cikti (basit backtracking 6x6 ve ustunde tikaniyor) -- bu yuzden
simdilik sabit 5x5 ile sinirli.
"""

from core.validator import BasePuzzleValidator


class YinYangValidator(BasePuzzleValidator):
    game_name = "yinyang"

    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "yinyang":
            return False, "game alani 'yinyang' degil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatinda olmali"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmali"

        prefilled = puzzle.get("prefilled", [])
        seen = set()
        for cell in prefilled:
            r, c = cell["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"prefilled {cell} grid disinda"
            if cell["color"] not in ("black", "white"):
                return False, f"prefilled {cell} color 'black'/'white' olmali"
            if (r, c) in seen:
                return False, f"prefilled hucre tekrar ediyor: {(r, c)}"
            seen.add((r, c))

        return True, None

    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution:
            return False, "solution bos"

        rows, cols = puzzle["size"]
        if len(solution) != rows or any(len(row) != cols for row in solution):
            return False, "solution boyutu size ile uyusmuyor"

        for r in range(rows):
            for c in range(cols):
                if solution[r][c] not in ("black", "white"):
                    return False, f"({r},{c}) degeri 'black'/'white' degil: {solution[r][c]}"

        for cell in puzzle.get("prefilled", []):
            r, c = cell["pos"]
            if solution[r][c] != cell["color"]:
                return False, f"prefilled ({r},{c})={cell['color']} ile cozum celisiyor"

        for color in ("black", "white"):
            cells = [(r, c) for r in range(rows) for c in range(cols) if solution[r][c] == color]
            if not cells:
                return False, f"'{color}' renginde hic hucre yok"
            cellset = set(cells)
            start = cells[0]
            visited = {start}
            stack = [start]
            while stack:
                u = stack.pop()
                r, c = u
                for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if nb in cellset and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            if len(visited) != len(cells):
                return False, f"'{color}' hucreleri tek bagli degil"

        for r in range(rows - 1):
            for c in range(cols - 1):
                vals = {solution[r][c], solution[r + 1][c], solution[r][c + 1], solution[r + 1][c + 1]}
                if len(vals) == 1:
                    return False, f"({r},{c}) koseli 2x2 alan tek renk"

        return True, None
