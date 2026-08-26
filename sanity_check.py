import sys
sys.path.insert(0, ".")

from core.registry import _auto_register_defaults, get_validator

_auto_register_defaults()

# ---------- ZIP testi: 3x3 grid, ortada 1 blok yok (basit), sonra blocked_cells'li ----------
zip_validator = get_validator("zip")

zip_puzzle = {
    "game": "zip",
    "size": [3, 3],
    "checkpoints": [{"order": 1, "pos": [0, 0]}, {"order": 2, "pos": [2, 2]}],
    "blocked_cells": [],
}
ok, err = zip_validator.validate_puzzle_shape(zip_puzzle)
print("ZIP shape (bloksuz):", ok, err)

# boustrophedon (S şeklinde) tam kapsayan yol, checkpoint sırasına uyuyor
zip_solution = [[0,0],[0,1],[0,2],[1,2],[1,1],[1,0],[2,0],[2,1],[2,2]]
ok, err = zip_validator.validate_solution(zip_puzzle, zip_solution)
print("ZIP solution (doğru olmalı):", ok, err)

bad_solution = [[2,2],[2,1],[2,0],[1,0],[1,1],[1,2],[0,2],[0,1],[0,0]]  # checkpoint2 (2,2) checkpoint1'den ONCE ziyaret ediliyor -> sıra ihlali
ok, err = zip_validator.validate_solution(zip_puzzle, bad_solution)
print("ZIP solution (checkpoint sırası bozuk, hatalı olmalı):", ok, err)

# blocked_cells ile bağlantıyı bozan puzzle (generator hatası simülasyonu)
zip_puzzle_broken = {
    "game": "zip",
    "size": [3, 3],
    "checkpoints": [{"order": 1, "pos": [0, 0]}, {"order": 2, "pos": [2, 2]}],
    "blocked_cells": [[0,1],[1,0],[1,1],[1,2],[2,1]],  # ortayı ve kenarları kapatıp (0,0)'ı izole eder
}
ok, err = zip_validator.validate_puzzle_shape(zip_puzzle_broken)
print("ZIP shape (bağlantısı bozuk, hatalı olmalı):", ok, err)

print()

# ---------- QUEENS testi: 4x4, 4 bölge ----------
queens_validator = get_validator("queens")

queens_puzzle = {
    "game": "queens",
    "size": [4, 4],
    "regions": [
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [2, 0, 0, 0],
        [0, 0, 3, 0],
    ],
}
ok, err = queens_validator.validate_puzzle_shape(queens_puzzle)
print("QUEENS shape:", ok, err)

# önceden brute-force doğrulanmış geçerli çözüm
queens_solution = [[0, 1], [1, 3], [2, 0], [3, 2]]
ok, err = queens_validator.validate_solution(queens_puzzle, queens_solution)
print("QUEENS solution (doğru olmalı):", ok, err)

bad_queens_solution = [[0, 1], [1, 2], [2, 0], [3, 2]]  # (1,2)-(0,1) çapraz bitişik -> hatalı olmalı
ok, err = queens_validator.validate_solution(queens_puzzle, bad_queens_solution)
print("QUEENS solution (muhtemelen hatalı):", ok, err)
