"""
arena/solver_runner.py

SANDBOX (container ya da ayri process) ICINDE calisir. Hakemden satir
satir JSON istek alir, katilimcinin solver'ini cagirir, satir satir JSON
cevap yollar. Boylece katilimci kodu bank dosyalarini, baska takimlarin
verisini, validator'lari ya da hakemin sonuclarini GOREMEZ; sadece kendisine
verilen puzzle'i gorur.

Protokol (stdin/stdout, UTF-8, her satir bir JSON):
  runner -> hakem : {"ready": true}   (ya da {"ready": false, "error": "..."})
  hakem  -> runner: {"id": 7, "puzzle": {...}, "time_limit_s": 8.0}
  runner -> hakem : {"id": 7, "solved": bool, "solution": ..., "steps_taken": int,
                     "error": str|null, "time_seconds": float}

Solver'in print()'leri protokolu bozmasin diye stdout, baslangicta stderr'e
yonlendirilir; protokol icin ayri bir dosya tanimlayicisi kullanilir.

Kullanim (genellikle dogrudan degil, arena/sandboxed_solver.py uzerinden):
    python arena/solver_runner.py --solver modul.yolu:SinifAdi
"""

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.sandbox import drop_privileges, set_cpu_budget, set_memory_limit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True, help="modul.yolu:SinifAdi")
    parser.add_argument("--memory-mb", type=int, default=1024)
    parser.add_argument("--cpu-seconds", type=int, default=60,
                        help="HER puzzle icin CPU saniyesi butcesi")
    args = parser.parse_args()

    # Protokol kanalini ayir; solver'in stdout'a yazdiklari stderr'e gitsin.
    proto = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(obj) -> None:
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    drop_privileges()
    set_memory_limit(args.memory_mb)

    try:
        module_path, class_name = args.solver.split(":")
        solver = getattr(importlib.import_module(module_path), class_name)()
    except BaseException:
        send({"ready": False, "error": traceback.format_exc(limit=3)[-500:]})
        return
    send({"ready": True})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            rid, puzzle, limit = req["id"], req["puzzle"], float(req["time_limit_s"])
        except Exception:
            continue  # bozuk istek: cevapsiz birak, hakem timeout ile halleder

        set_cpu_budget(args.cpu_seconds)
        t0 = time.time()
        resp = {"id": rid, "solved": False, "solution": None, "steps_taken": 0,
                "error": None, "time_seconds": 0.0}
        try:
            result = solver.solve(puzzle, time_limit_s=limit)
            resp["solved"] = bool(result.solved)
            resp["solution"] = result.solution
            resp["steps_taken"] = int(getattr(result, "steps_taken", 0) or 0)
            resp["error"] = None if result.error is None else str(result.error)
            json.dumps(resp)  # JSON'a cevrilebilir mi?
        except MemoryError:
            resp.update(solved=False, solution=None, error=f"BELLEK LIMITI ASILDI ({args.memory_mb}MB)")
        except BaseException as e:  # solve() her turlu hata verebilir
            resp.update(solved=False, solution=None, error=f"{type(e).__name__}: {e}"[:300])
        resp["time_seconds"] = time.time() - t0
        send(resp)


if __name__ == "__main__":
    main()
