"""
games/zip/validator.py

ZIP oyunu (resim 1'deki oyun):
  - size = [rows, cols] ızgara
  - checkpoints: sırayla ziyaret edilmesi gereken noktalar (order=1,2,3,...)
  - blocked_cells: üzerinden GEÇİLEMEYEN hücreler (senin istediğin engel özelliği)

Amaç: ızgaradaki her BLOKLU-OLMAYAN hücreden TAM 1 kez geçen tek bir yol
(Hamiltonian path) bul; bu yol checkpoint'leri numara sırasına göre
(1 önce, 2 sonra, ...) ziyaret etmeli. Checkpoint'ler arasında sırayı
bozmadığı sürece istediği hücrelerden geçebilir.

Puzzle şeması:
{
  "game": "zip",
  "size": [10, 10],
  "checkpoints": [{"order": 1, "pos": [7, 5]}, {"order": 2, "pos": [0, 1]}, ...],
  "blocked_cells": [[3, 3], [3, 4], [4, 3], [4, 4]]
}

Solution şeması (solver'ın döndürmesi gereken format):
  solution = [[r0, c0], [r1, c1], ..., [rk, ck]]   # ziyaret sırasına göre hücre listesi
"""

from collections import deque

from core.validator import BasePuzzleValidator


class ZipValidator(BasePuzzleValidator):
    game_name = "zip"

    # ---------- PUZZLE ŞEKLİ KONTROLÜ ----------
    def validate_puzzle_shape(self, puzzle: dict) -> tuple[bool, str | None]:
        if puzzle.get("game") != "zip":
            return False, "game alanı 'zip' değil"

        size = puzzle.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) == 2):
            return False, "size [rows, cols] formatında olmalı"
        rows, cols = size
        if rows <= 0 or cols <= 0:
            return False, "size pozitif olmalı"

        blocked = puzzle.get("blocked_cells", [])
        blocked_set = set()
        for cell in blocked:
            r, c = cell
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"blocked_cell {cell} grid dışında"
            blocked_set.add((r, c))

        checkpoints = puzzle.get("checkpoints")
        if not checkpoints or len(checkpoints) < 2:
            return False, "en az 2 checkpoint olmalı"

        orders = sorted(cp["order"] for cp in checkpoints)
        if orders != list(range(1, len(checkpoints) + 1)):
            return False, "checkpoint order'ları 1..N ardışık olmalı"

        seen_pos = set()
        for cp in checkpoints:
            r, c = cp["pos"]
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"checkpoint {cp} grid dışında"
            if (r, c) in blocked_set:
                return False, f"checkpoint {cp} bloklu bir hücrede"
            if (r, c) in seen_pos:
                return False, f"checkpoint pozisyonu tekrar ediyor: {cp}"
            seen_pos.add((r, c))

        # Sağlamlık kontrolü: bloklu olmayan hücreler bağlı (connected) mı?
        # Değilse Hamiltonian path zaten imkansızdır -- generator hatası sayılır.
        free_cells = {(r, c) for r in range(rows) for c in range(cols)} - blocked_set
        if free_cells and not self._is_connected(free_cells, rows, cols):
            return False, "blocked_cells serbest alanı parçalara bölüyor (bağlı değil)"

        return True, None

    @staticmethod
    def _is_connected(free_cells: set[tuple[int, int]], rows: int, cols: int) -> bool:
        start = next(iter(free_cells))
        visited = {start}
        q = deque([start])
        while q:
            r, c = q.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (r + dr, c + dc)
                if nxt in free_cells and nxt not in visited:
                    visited.add(nxt)
                    q.append(nxt)
        return visited == free_cells

    # ---------- ÇÖZÜM KONTROLÜ ----------
    def validate_solution(self, puzzle: dict, solution) -> tuple[bool, str | None]:
        if not solution or not isinstance(solution, list):
            return False, "solution boş ya da liste değil"

        rows, cols = puzzle["size"]
        blocked_set = {tuple(c) for c in puzzle.get("blocked_cells", [])}
        path = [tuple(cell) for cell in solution]

        free_cell_count = rows * cols - len(blocked_set)
        if len(path) != free_cell_count:
            return False, f"yol uzunluğu {len(path)}, beklenen {free_cell_count}"

        if len(set(path)) != len(path):
            return False, "yol bir hücreyi birden fazla ziyaret ediyor"

        for (r, c) in path:
            if not (0 <= r < rows and 0 <= c < cols):
                return False, f"{(r, c)} grid dışında"
            if (r, c) in blocked_set:
                return False, f"yol bloklu hücreden geçiyor: {(r, c)}"

        for i in range(len(path) - 1):
            r1, c1 = path[i]
            r2, c2 = path[i + 1]
            if abs(r1 - r2) + abs(c1 - c2) != 1:
                return False, f"{path[i]} -> {path[i+1]} bitişik değil (çapraz/atlama yasak)"

        # checkpoint sırası korunuyor mu?
        checkpoints = sorted(puzzle["checkpoints"], key=lambda cp: cp["order"])
        path_index = {cell: i for i, cell in enumerate(path)}
        last_idx = -1
        for cp in checkpoints:
            pos = tuple(cp["pos"])
            if pos not in path_index:
                return False, f"checkpoint {cp} yol üzerinde değil"
            idx = path_index[pos]
            if idx <= last_idx:
                return False, f"checkpoint {cp['order']} sıra dışı ziyaret edildi"
            last_idx = idx

        # yol İLK checkpoint'te başlamalı, SON checkpoint'te bitmeli
        # (orijinal "Zip" oyunundaki gibi: noktalar sırayla bağlanır, yol
        # ilk noktadan başlar, son noktada biter)
        first_cp_pos = tuple(checkpoints[0]["pos"])
        last_cp_pos = tuple(checkpoints[-1]["pos"])
        if path[0] != first_cp_pos:
            return False, f"yol ilk checkpoint'te ({first_cp_pos}) başlamıyor, {path[0]}'da başlıyor"
        if path[-1] != last_cp_pos:
            return False, f"yol son checkpoint'te ({last_cp_pos}) bitmiyor, {path[-1]}'da bitiyor"

        return True, None
