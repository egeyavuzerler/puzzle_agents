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


import os as _os


class StdoutSpamSolver(BaseSolverAgent):
    """stdout'a cop basar (protokol kanalini bozmaya calisir), sonra gercekten cozer."""
    name = "evil_stdout_spam"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        for _ in range(2000):
            print('{"id": 1, "solved": true, "solution": [], "error": null}')
        from agents_examples.baseline import BaselineSolver
        return BaselineSolver().solve(puzzle, time_limit_s)


class BigAnswerSolver(BaseSolverAgent):
    """50 MB'lik cevap dondurur -- hakemin belleğini sisirmeye calisir."""
    name = "evil_big_answer"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        return SolveResult(solved=True, solution=["x" * (50 * 1024 * 1024)])


class CrashingSolver(BaseSolverAgent):
    """Process'i aninda oldurur."""
    name = "evil_crash"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        _os._exit(1)


class SnoopSolver(BaseSolverAgent):
    """
    Baska dosyalari okumaya ve aga cikmaya calisir, bulgusunu STDERR'e yazar.
    Docker modunda: AG ve dosya erisimi ENGELLENMIS olmali ("ENGELLI" gormelisin).
    local/none modunda bunlar basarili olur -- izolasyon yok demektir.
    """
    name = "evil_snoop"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        import socket
        import sys
        findings = []
        try:
            s = socket.create_connection(("1.1.1.1", 53), timeout=2)
            s.close()
            findings.append("AG: ERISILDI (izolasyon YOK)")
        except Exception as e:
            findings.append(f"AG: ENGELLI ({type(e).__name__})")
        for path in ("bank", "results", "bank/solutions.jsonl", "/etc/shadow", "../bank"):
            try:
                _os.listdir(path) if _os.path.isdir(path) else open(path).read(1)
                findings.append(f"DOSYA {path}: OKUNDU (izolasyon YOK)")
            except Exception as e:
                findings.append(f"DOSYA {path}: ENGELLI ({type(e).__name__})")
        try:
            open("/app/pwned.txt", "w").write("x")
            findings.append("YAZMA /app: BASARILI (izolasyon YOK)")
        except Exception as e:
            findings.append(f"YAZMA /app: ENGELLI ({type(e).__name__})")
        print("[SnoopSolver] " + " | ".join(findings), file=sys.stderr, flush=True)
        return SolveResult(solved=False, error="snoop")


class StringAnswerSolver(BaseSolverAgent):
    """'Cozdum' der ama cozum sayi yerine STRING'lerden olusur (validator'u cokertmeye calisir)."""
    name = "evil_string_answer"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        return SolveResult(solved=True, solution=[["abc", "def"], ["x", None]])
