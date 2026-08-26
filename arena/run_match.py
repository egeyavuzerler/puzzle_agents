"""
arena/run_match.py

Bir SOLVER agent'ını, önceden üretilmiş bir bank.jsonl dosyasına (bir
katılımcının 10.000'lik puzzle havuzuna) karşı koşturur.

GÜVENLİK NOTU: Katılımcı kodları (solve()) senin/Google'ın makinesinde
çalışacağı için her puzzle çözümü AYRI bir process'te, SERT bir duvar-saati
zaman aşımıyla (hard_timeout_s) çalıştırılır. Solver bu süreyi aşarsa
process terminate edilir ve o puzzle "çözülemedi" sayılır -- sonsuz döngüye
giren bir solver tüm turnuvayı kilitleyemez.

Kullanım:
    python arena/run_match.py --solver my_agents.team_b:TeamBSolver \
                               --bank bank/team_a_bank.jsonl \
                               --time-limit 10 \
                               --out results/teamB_vs_teamA.json
"""

import argparse
import importlib
import json
import multiprocessing as mp
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.registry import _auto_register_defaults, get_validator
from core.base import SolveResult

try:
    import resource  # Unix/macOS only -- Windows'ta yok
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False


def load_solver_class(spec: str):
    module_path, class_name = spec.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _apply_resource_limits(memory_mb: int, cpu_seconds: int) -> None:
    """
    Worker process başında çağrılır. Katılımcı kodunun (solve()) makineyi
    zorlamasını engelleyen sert donanım limitleri koyar:
      - RLIMIT_AS: adres alanı (bellek) limiti -- aşılırsa MemoryError fırlar
      - RLIMIT_CPU: CPU saniyesi limiti -- aşılırsa SIGXCPU ile process öldürülür
        (duvar-saati timeout'undan FARKLI: bu, CPU'yu gerçekten ne kadar
        kullandığını sınırlar, sonsuz döngüde bile devreye girer)
    Windows'ta resource modülü yok; o durumda sadece dış hard_timeout korumaya kalır.
    """
    if not _HAS_RESOURCE:
        return
    try:
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError):
        pass  # macOS bazı sistemlerde RLIMIT_AS'i desteklemeyebilir, sessizce geç
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except (ValueError, OSError):
        pass


def _worker(solver, puzzle: dict, time_limit_s: float, memory_mb: int, cpu_seconds: int,
            q: mp.Queue) -> None:
    """Ayrı process içinde çalışır. Hata da versin, sonuç da versin, queue'ya koyar."""
    _apply_resource_limits(memory_mb, cpu_seconds)
    t0 = time.time()
    try:
        result = solver.solve(puzzle, time_limit_s=time_limit_s)
        result.time_seconds = time.time() - t0
        q.put(result)
    except MemoryError:
        q.put(SolveResult(solved=False, time_seconds=time.time() - t0,
                           error=f"BELLEK LİMİTİ AŞILDI ({memory_mb}MB)"))
    except Exception as e:
        q.put(SolveResult(solved=False, time_seconds=time.time() - t0,
                           error=f"{type(e).__name__}: {e}"))


def run_one(solver, puzzle: dict, time_limit_s: float, hard_timeout_s: float,
            memory_mb: int = 1024, cpu_seconds: int = 60) -> SolveResult:
    q: mp.Queue = mp.Queue()
    p = mp.Process(target=_worker, args=(solver, puzzle, time_limit_s, memory_mb, cpu_seconds, q))
    p.start()
    p.join(hard_timeout_s)

    if p.is_alive():
        p.terminate()
        p.join(2)
        if p.is_alive():
            p.kill()
        return SolveResult(solved=False, time_seconds=hard_timeout_s,
                            error=f"HARD TIMEOUT ({hard_timeout_s}s) -- process sonlandırıldı")

    if not q.empty():
        return q.get()

    # process bitti ama kuyrukta hiçbir şey yok -> muhtemelen crash (segfault,
    # RLIMIT_CPU SIGXCPU ile öldürüldü, os.kill vs.)
    exitcode_note = f" (exitcode={p.exitcode})" if p.exitcode not in (0, None) else ""
    return SolveResult(solved=False, error=f"process kuyruğa sonuç bırakmadan sonlandı{exitcode_note}")


def run_match(solver, bank_path: str, time_limit_s: float, hard_timeout_s: float,
              memory_mb: int = 1024, cpu_seconds: int = 60,
              max_puzzles: int | None = None) -> dict:
    _auto_register_defaults()

    per_game = {}
    total = 0
    total_solved = 0
    total_time = 0.0

    with open(bank_path) as f:
        for line_no, line in enumerate(f):
            if max_puzzles is not None and line_no >= max_puzzles:
                break
            record = json.loads(line)
            game = record["game"]
            puzzle = record["puzzle"]
            validator = get_validator(game)

            per_game.setdefault(game, {"total": 0, "solved": 0, "invalid_solution": 0,
                                        "timeout_or_error": 0, "total_time": 0.0})
            stat = per_game[game]
            stat["total"] += 1
            total += 1

            result = run_one(solver, puzzle, time_limit_s, hard_timeout_s, memory_mb, cpu_seconds)
            stat["total_time"] += result.time_seconds
            total_time += result.time_seconds

            if result.error:
                stat["timeout_or_error"] += 1
                continue
            if not result.solved:
                stat["timeout_or_error"] += 1
                continue

            valid, err = validator.validate_solution(puzzle, result.solution)
            if valid:
                stat["solved"] += 1
                total_solved += 1
            else:
                stat["invalid_solution"] += 1  # solver "çözdüm" dedi ama çözüm yanlış

    summary = {
        "solver": getattr(solver, "name", solver.__class__.__name__),
        "bank": bank_path,
        "total_puzzles": total,
        "total_solved": total_solved,
        "solve_rate": round(total_solved / total, 4) if total else 0.0,
        "avg_time_s": round(total_time / total, 3) if total else 0.0,
        "per_game": {
            g: {**s, "solve_rate": round(s["solved"] / s["total"], 4) if s["total"] else 0.0}
            for g, s in per_game.items()
        },
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True, help="modul.yolu:SinifAdi")
    parser.add_argument("--bank", required=True)
    parser.add_argument("--time-limit", type=float, default=10.0,
                         help="solver'a bildirilen yumuşak limit (saniye)")
    parser.add_argument("--hard-timeout", type=float, default=None,
                         help="process'i zorla kesme süresi (varsayılan: time-limit + 5s)")
    parser.add_argument("--memory-mb", type=int, default=1024,
                         help="solver process'ine bellek limiti (MB, varsayılan 1024)")
    parser.add_argument("--cpu-seconds", type=int, default=60,
                         help="solver process'ine CPU süresi limiti (saniye, varsayılan 60)")
    parser.add_argument("--max-puzzles", type=int, default=None, help="test için havuzun bir kısmı")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    hard_timeout = args.hard_timeout if args.hard_timeout is not None else args.time_limit + 5.0

    SolverClass = load_solver_class(args.solver)
    solver = SolverClass()

    summary = run_match(solver, args.bank, args.time_limit, hard_timeout,
                         args.memory_mb, args.cpu_seconds, args.max_puzzles)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
