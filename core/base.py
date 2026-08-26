"""
core/base.py

Hackathon'daki HERKESİN miras alacağı temel sözleşme (contract).
Katılımcılar bu iki soyut sınıftan kendi ajanlarını türetecek:

    class MyGenerator(BaseGeneratorAgent): ...
    class MySolver(BaseSolverAgent): ...

Bu dosyaya katılımcılar dokunmaz. Değişirse tüm sistem bozulur.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SolveResult:
    """Bir solver'ın bir puzzle için ürettiği sonucun standart zarfı."""
    solved: bool
    solution: Any = None          # oyuna özel format (validator'ın anlayacağı şekilde)
    time_seconds: float = 0.0
    steps_taken: int = 0          # opsiyonel: backtrack sayısı, iterasyon vs. (metrik için)
    error: str | None = None      # solver hata verirse (exception yakalanıp buraya yazılır)


class BaseGeneratorAgent(ABC):
    """
    Bir puzzle üretici ajan. `generate` bir puzzle sözlüğü (dict) döndürmeli,
    bu sözlük ilgili oyunun core/schema kurallarına uymalı
    (örn. games/zip/validator.py içindeki `validate_puzzle_shape`).
    """

    name: str = "unnamed_generator"

    @abstractmethod
    def generate(self, game: str, difficulty: int, seed: int | None = None) -> tuple[dict, Any]:
        """
        game: üretilecek oyun türünün adı (örn. "zip", "queens", ileride 18 tane daha).
              Katılımcı bunu bir if/elif ya da dict-dispatch ile kendi oyun-özel
              üretim fonksiyonlarına yönlendirir.
        difficulty: 1 (kolay) - 10 (zor) arası, katılımcı bunu istediği gibi yorumlar
        seed: verilirse üretim deterministik olmalı (aynı seed -> aynı puzzle)

        Dönüş: (puzzle, solution) ikilisi.

        ÖNEMLİ (unsolvable puzzle koruması): `solution`, bu puzzle'ın en az bir
        geçerli çözümü olduğunun TANIĞIDIR (witness). Üretim algoritman zaten
        neredeyse her oyunda önce tam bir çözüm inşa edip sonra bir kısmını
        gizliyor ("generate-then-hide") -- o çözümü burada AYRICA döndürmen
        yeterli, yeniden hesaplamana gerek yok. `solution`, ilgili oyunun
        validator'ının `validate_solution(puzzle, solution)` metodunun kabul
        edeceği formatta olmalı (örn. zip için hücre listesi, queens için
        kraliçe pozisyonları, vb. -- bkz. games/<oyun>/validator.py).

        `bank/build_bank.py` bu solution'ı validator'a karşı doğrular ve
        SADECE puzzle'ı bank'e yazar; solution asla solver'a sızmaz.

        Örnek dönüş (zip):
            (
              {
                "game": "zip",
                "size": [10, 10],
                "checkpoints": [{"order": 1, "pos": [7,5]}, ...],
                "blocked_cells": [[3,3], [3,4], ...]
              },
              [[0,0], [0,1], [1,1], ...]   # tam Hamiltonian path -- witness
            )
        """
        raise NotImplementedError

    def generate_and_verify(self, game: str, difficulty: int, seed: int | None,
                             validator, max_retries: int = 20) -> tuple[dict, Any]:
        """
        Yardımcı metod (opsiyonel kullanım): üretilen puzzle'ın hem ŞEKİL
        olarak (shape) hem de ÇÖZÜLEBİLİR olduğunu (döndürülen solution
        gerçekten geçerli mi) garantiler. İstemeyen katılımcı bunu override
        etmeyebilir / kullanmayabilir -- ama bank/build_bank.py zaten bu iki
        kontrolü kendi içinde ayrıca yapıyor, bu yüzden bu metod opsiyonel bir
        kolaylık, tek güvenlik katmanı DEĞİL.
        """
        last_err = None
        for attempt in range(max_retries):
            puzzle, solution = self.generate(game, difficulty, None if seed is None else seed + attempt)
            ok, err = validator.validate_puzzle_shape(puzzle)
            if not ok:
                last_err = f"shape: {err}"
                continue
            ok, err = validator.validate_solution(puzzle, solution)
            if not ok:
                last_err = f"solution: {err}"
                continue
            return puzzle, solution
        raise ValueError(f"generate_and_verify {max_retries} denemede geçerli+çözülebilir puzzle üretemedi: {last_err}")


class BaseSolverAgent(ABC):
    """
    Bir puzzle çözücü ajan. `solve` verilen puzzle dict'ini alır,
    SolveResult döndürür. Zaman limitini AŞMAMAYA solver kendisi dikkat etmeli
    (benchmark runner ayrıca dışarıdan da kesecek, ama iyi bir solver kendi
    içinde de zaman kontrolü yapmalı).
    """

    name: str = "unnamed_solver"

    @abstractmethod
    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        """
        puzzle: generator'dan (veya bank'tan) gelen dict, aynı şema.
        time_limit_s: solver bu süreyi aşmamaya çalışmalı.

        Dönüş: SolveResult
        """
        raise NotImplementedError
