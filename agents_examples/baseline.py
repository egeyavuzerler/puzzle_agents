"""
agents_examples/baseline.py

Bu dosya bir HAKEM ya da CEKIRDEK parcasi DEGIL -- sadece "boyle bir agent
yazacaksiniz" ornegi. Gercek generator/solver kodu games/<oyun>/reference_agent.py
icinde; bu dosya sadece "game" adina gore dogru fonksiyona yonlendiren
INCE bir dispatch katmani.
"""

import random

from core.base import BaseGeneratorAgent, BaseSolverAgent, SolveResult

from games.zip.reference_agent import generate_zip, solve_zip
from games.queens.reference_agent import generate_queens, solve_queens
from games.tango.reference_agent import generate_tango, solve_tango
from games.patches.reference_agent import generate_patches, solve_patches
from games.slitherlink.reference_agent import generate_slitherlink, solve_slitherlink
from games.numberlink.reference_agent import generate_numberlink, solve_numberlink
from games.hashi.reference_agent import generate_hashi, solve_hashi
from games.lits.reference_agent import generate_lits, solve_lits
from games.yinyang.reference_agent import generate_yinyang, solve_yinyang
from games.tapa.reference_agent import generate_tapa, solve_tapa

_GENERATORS = {
    "zip": generate_zip,
    "queens": generate_queens,
    "tango": generate_tango,
    "patches": generate_patches,
    "slitherlink": generate_slitherlink,
    "numberlink": generate_numberlink,
    "hashi": generate_hashi,
    "lits": generate_lits,
    "yinyang": generate_yinyang,
    "tapa": generate_tapa,
}

_SOLVERS = {
    "zip": solve_zip,
    "queens": solve_queens,
    "tango": solve_tango,
    "patches": solve_patches,
    "slitherlink": solve_slitherlink,
    "numberlink": solve_numberlink,
    "hashi": solve_hashi,
    "lits": solve_lits,
    "yinyang": solve_yinyang,
    "tapa": solve_tapa,
}


class BaselineGenerator(BaseGeneratorAgent):
    name = "baseline_generator"

    def generate(self, game: str, difficulty: int, seed: int | None = None):
        if game not in _GENERATORS:
            raise NotImplementedError(f"BaselineGenerator '{game}' uretmiyor")
        rng = random.Random(seed)
        return _GENERATORS[game](rng, difficulty)  # artik (puzzle, solution) doner


class BaselineSolver(BaseSolverAgent):
    name = "baseline_solver"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        game = puzzle.get("game")
        if game not in _SOLVERS:
            return SolveResult(solved=False, error=f"BaselineSolver '{game}' cozmuyor")
        return _SOLVERS[game](puzzle, time_limit_s=time_limit_s)
