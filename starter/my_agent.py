"""
starter/my_agent.py -- BASLANGIC SABLONU

Bu dosyayi kopyalayip kendi takim adinizla yeniden adlandirin
(ornegin takim_x/agent.py) ve asagidaki iki sinifi doldurun.

Su haliyle HEMEN CALISIR: referans (baseline) ajanlara yonlendirir, yani
10 oyunun hepsi icin gecerli puzzle uretir ve cozmeye calisir. Siz tek tek
oyunlari kendi kodunuzla degistirerek ilerleyin.

Gonderiminizi kontrol edin:
    python3 arena/check_submission.py \
        --generator starter.my_agent:MyGenerator --solver starter.my_agent:MySolver

SOZLESME (ozet; ayrinti README'de):
  - generate(game, difficulty, seed) -> (puzzle, solution)
      * ikisi de JSON'a cevrilebilir olmali (dict/list/int/str/bool/None; numpy dizisi ya da set DEGIL)
      * solution, puzzle'in gecerli bir cozumu olmali (witness) -- yoksa puzzle havuza girmez
      * ayni seed ayni puzzle'i uretmeli (tekrar uretilebilirlik)
      * generate() cagrisi basina sure siniri vardir (varsayilan 20 sn)
  - solve(puzzle, time_limit_s) -> SolveResult(solved=..., solution=...)
      * time_limit_s'yi asmamaya calisin; asarsaniz o puzzle "cozulemedi" sayilir
      * solution JSON'a cevrilebilir olmali
"""

import random

from agents_examples.baseline import BaselineGenerator, BaselineSolver
from core.base import BaseGeneratorAgent, BaseSolverAgent, SolveResult


class MyGenerator(BaselineGenerator):
    name = "takim_x_generator"

    def generate(self, game: str, difficulty: int, seed: int | None = None):
        # ORNEK: bir oyunu kendi kodunuzla degistirin, gerisi baseline'a kalsin:
        #
        # if game == "queens":
        #     return my_generate_queens(random.Random(seed), difficulty)   # (puzzle, solution)
        #
        return super().generate(game, difficulty, seed)


class MySolver(BaselineSolver):
    name = "takim_x_solver"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        # ORNEK: bir oyunu kendi kodunuzla degistirin, gerisi baseline'a kalsin:
        #
        # if puzzle["game"] == "queens":
        #     solution = my_solve_queens(puzzle, time_limit_s)
        #     return SolveResult(solved=solution is not None, solution=solution)
        #
        return super().solve(puzzle, time_limit_s)
