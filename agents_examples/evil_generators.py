"""
agents_examples/evil_generators.py

KOTU NIYETLI / HATALI generator ornekleri -- hakemin (build_bank.py) bunlara
karsi dayanikli oldugunu test etmek icin. Gercek bir yarismaci boyle bir kodu
kasten ya da kazara yazabilir; hakem hicbirinde DUSMEMELI, sadece o puzzle'i
reddetmeli (bkz. core/sandbox.py).
"""

import os

from agents_examples.baseline import BaselineGenerator, BaselineSolver  # noqa: F401 (BaselineSolver: --team icin)
from core.base import BaseGeneratorAgent


class HangingGenerator(BaseGeneratorAgent):
    """Sonsuz dongu -- timeout'suz hakemde tum bank uretimini kilitlerdi."""
    def generate(self, game, difficulty, seed=None):
        while True:
            pass


class CrashingGenerator(BaseGeneratorAgent):
    """Process'i aninda oldurur (segfault / os._exit benzeri)."""
    def generate(self, game, difficulty, seed=None):
        os._exit(1)


class RaisingGenerator(BaseGeneratorAgent):
    def generate(self, game, difficulty, seed=None):
        raise RuntimeError("bilerek hata")


class GarbageGenerator(BaseGeneratorAgent):
    """(puzzle, solution) ikilisi yerine anlamsiz deger doner."""
    def generate(self, game, difficulty, seed=None):
        return "bu bir puzzle degil"


class NotADictGenerator(BaseGeneratorAgent):
    def generate(self, game, difficulty, seed=None):
        return ["puzzle", "dict", "degil"], [1, 2, 3]


class NonSerializableGenerator(BaseGeneratorAgent):
    """Gecerli gorunen ama JSON'a cevrilemeyen (set iceren) puzzle."""
    def generate(self, game, difficulty, seed=None):
        puzzle, solution = BaselineGenerator().generate(game=game, difficulty=difficulty, seed=seed)
        puzzle = dict(puzzle)
        puzzle["gizli"] = {1, 2, 3}
        return puzzle, solution


class MemoryHogGenerator(BaseGeneratorAgent):
    """Makineyi sisirmeye calisir (RLIMIT_AS destekleyen sistemlerde MemoryError)."""
    def generate(self, game, difficulty, seed=None):
        hog = bytearray(64 * 1024 * 1024 * 1024)  # 64 GB
        return {"game": game}, hog


class FlakyGenerator(BaseGeneratorAgent):
    """seed cift ise sonsuz donguye girer, tek ise normal calisir.
    Hakem takilan cagriyi oldurup YENI worker ile devam etmeli."""
    def generate(self, game, difficulty, seed=None):
        if seed is not None and seed % 2 == 0:
            while True:
                pass
        return BaselineGenerator().generate(game=game, difficulty=difficulty, seed=seed)


class UnsolvableGenerator(BaseGeneratorAgent):
    """Sekil olarak GECERLI ama dogrulanabilir cozumu OLMAYAN puzzle (solution=None):
    'imkansiz puzzle ile bedava puan' hilesi. build_bank bunu REDDETMELI."""
    def generate(self, game, difficulty, seed=None):
        puzzle, _solution = BaselineGenerator().generate(game=game, difficulty=difficulty, seed=seed)
        return puzzle, None


class WrongSolutionGenerator(BaseGeneratorAgent):
    """Gercek puzzle + KESIN YANLIS solution (basina grid disi bir hucre eklenmis).
    NOT: 'dogru cozumden bir hucre cikarmak' kesin yanlis DEGILDIR -- puzzle'lar tek cozumlu
    olmak zorunda degil (ornegin Tapa), cikarilmis hali de gecerli bir cozum olabilir."""
    def generate(self, game, difficulty, seed=None):
        puzzle, solution = BaselineGenerator().generate(game=game, difficulty=difficulty, seed=seed)
        if isinstance(solution, list):
            return puzzle, [[10**6, 10**6]] + solution
        return puzzle, "yanlis"


class DuplicateSpamGenerator(BaseGeneratorAgent):
    """Seed VE zorluk parametrelerini yok sayip HEP AYNI (gecerli) puzzle'i uretir: havuzu tek
    puzzle'la sisirmeye calisir. Hakem tekrarlari eler; generator bankin eksik kismindan puan alamaz."""
    def generate(self, game, difficulty, seed=None):
        return BaselineGenerator().generate(game=game, difficulty=5, seed=0)
