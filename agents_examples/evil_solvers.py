import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.base import BaseSolverAgent, SolveResult


class InfiniteLoopSolver(BaseSolverAgent):
    name = "evil_infinite_loop"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        x = 0
        while True:  # sonsuz döngü -- CPU limiti veya hard timeout devreye girmeli
            x += 1


class MemoryBombSolver(BaseSolverAgent):
    name = "evil_memory_bomb"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        blobs = []
        while True:  # sürekli bellek ayır -- RLIMIT_AS devreye girmeli
            blobs.append(b"x" * (50 * 1024 * 1024))  # 50MB parçalar
