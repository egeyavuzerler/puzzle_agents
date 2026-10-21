"""
arena/run_tournament.py

Round-robin turnuva: N takimin generator'i x N takimin solver'i.
Her takimin generator'i kendi puzzle havuzunu uretir, sonra HERKESIN
solver'i HERKESIN havuzuna karsi kosturulur. Iki ayri skor cikar:

  - SOLVER skoru: bir takimin solver'i, TUM generator'larin havuzlarinda
    ortalama ne kadar cozebildi (yuksek = iyi solver)
  - GENERATOR skoru: bir takimin generator'inin urettigi puzzle'lari,
    DIGER takimlarin solver'lari ortalama ne kadar AZ cozebildi
    (yuksek = zor/iyi puzzle ureten generator). Kendi solver'i haric
    tutulur (yoksa bir takim kendi solver'ini generator'una gore
    ayarlayip skoru sisirebilir).

Bu ampirik skorlama, generator'larin kendi "difficulty" etiketine
GUVENMEZ -- sadece gercek cozulme oranina bakar.

Kullanim:
    python3 arena/run_tournament.py \
        --team baseline:agents_examples.baseline:BaselineGenerator:BaselineSolver \
        --team takim2:takim2_agent:Takim2Generator:Takim2Solver \
        --per-type 20 --time-limit 8 --hard-timeout 12 --out results/tournament.json
"""

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bank.build_bank import build_bank
from arena.run_match import run_match


def _load_class(module_path: str, class_name: str):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def parse_team_spec(spec: str):
    """spec format: 'takim_adi:modul.yolu:GeneratorSinifi:SolverSinifi'"""
    parts = spec.split(":")
    if len(parts) != 4:
        raise ValueError(f"gecersiz --team format: {spec!r} (beklenen: ad:modul:Generator:Solver)")
    name, module_path, gen_class_name, solver_class_name = parts
    GenClass = _load_class(module_path, gen_class_name)
    SolverClass = _load_class(module_path, solver_class_name)
    return {"name": name, "generator": GenClass(), "solver": SolverClass()}


def run_tournament(teams, per_type, bank_dir, time_limit_s, hard_timeout_s,
                    memory_mb, cpu_seconds, max_puzzles=None):
    Path(bank_dir).mkdir(parents=True, exist_ok=True)

    bank_paths = {}
    for team in teams:
        out_path = str(Path(bank_dir) / f"{team['name']}_bank.jsonl")
        print(f"[bank] {team['name']} icin havuz uretiliyor ({per_type}/tur)...", flush=True)
        t0 = time.time()
        result = build_bank(team["generator"], per_type, out_path)
        print(f"       {result['written']} puzzle yazildi, "
              f"{result['failed_shape']} sekil-gecersiz, "
              f"{result['failed_solution']} cozulemez (solution kanitlanamadi), "
              f"{time.time()-t0:.1f}s", flush=True)
        bank_paths[team["name"]] = out_path

    matrix = {}
    full_results = {}
    total_pairs = len(teams) * len(teams)
    pair_i = 0
    for gen_team in teams:
        matrix[gen_team["name"]] = {}
        full_results[gen_team["name"]] = {}
        for solver_team in teams:
            pair_i += 1
            print(f"[arena {pair_i}/{total_pairs}] {solver_team['name']} solver'i "
                  f"{gen_team['name']} havuzuna karsi...", flush=True)
            summary = run_match(
                solver_team["solver"], bank_paths[gen_team["name"]],
                time_limit_s, hard_timeout_s, memory_mb, cpu_seconds, max_puzzles,
            )
            matrix[gen_team["name"]][solver_team["name"]] = summary["solve_rate"]
            full_results[gen_team["name"]][solver_team["name"]] = summary
            print(f"       solve_rate={summary['solve_rate']:.3f}", flush=True)

    team_names = [t["name"] for t in teams]

    solver_scores = {}
    for solver_name in team_names:
        rates = [matrix[gen_name][solver_name] for gen_name in team_names]
        solver_scores[solver_name] = sum(rates) / len(rates)

    generator_scores = {}
    for gen_name in team_names:
        opponent_rates = [matrix[gen_name][s_name] for s_name in team_names if s_name != gen_name]
        if opponent_rates:
            avg_opponent_solve_rate = sum(opponent_rates) / len(opponent_rates)
        else:
            avg_opponent_solve_rate = matrix[gen_name][gen_name]
        generator_scores[gen_name] = 1.0 - avg_opponent_solve_rate

    return {
        "teams": team_names,
        "matrix": matrix,
        "solver_scores": solver_scores,
        "generator_scores": generator_scores,
        "full_results": full_results,
    }


def print_leaderboard(result):
    print("\n" + "=" * 60)
    print("SOLVER SIRALAMASI (yuksek = daha cok puzzle cozdu)")
    print("=" * 60)
    for name, score in sorted(result["solver_scores"].items(), key=lambda x: -x[1]):
        print(f"  {name:20s}  {score:.3f}")

    print("\n" + "=" * 60)
    print("GENERATOR SIRALAMASI (yuksek = puzzle'lari rakiplere daha zor geldi)")
    print("=" * 60)
    for name, score in sorted(result["generator_scores"].items(), key=lambda x: -x[1]):
        print(f"  {name:20s}  {score:.3f}")

    print("\n" + "=" * 60)
    print("TAM MATRIS (satir=generator, sutun=solver, deger=solve_rate)")
    print("=" * 60)
    teams = result["teams"]
    header = " " * 22 + "".join(f"{t[:10]:>12s}" for t in teams)
    print(header)
    for gen_name in teams:
        row = f"  {gen_name:20s}" + "".join(f"{result['matrix'][gen_name][s]:>12.3f}" for s in teams)
        print(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", action="append", required=True,
                         help="format: ad:modul.yolu:GeneratorSinifi:SolverSinifi (birden fazla kez verilebilir)")
    parser.add_argument("--per-type", type=int, default=10)
    parser.add_argument("--bank-dir", default="bank/tournament")
    parser.add_argument("--time-limit", type=float, default=8.0)
    parser.add_argument("--hard-timeout", type=float, default=12.0)
    parser.add_argument("--memory-mb", type=int, default=1024)
    parser.add_argument("--cpu-seconds", type=int, default=60)
    parser.add_argument("--max-puzzles", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    teams = [parse_team_spec(spec) for spec in args.team]
    if len(teams) < 1:
        print("en az 1 takim gerekli")
        sys.exit(1)

    result = run_tournament(
        teams, args.per_type, args.bank_dir,
        args.time_limit, args.hard_timeout, args.memory_mb, args.cpu_seconds, args.max_puzzles,
    )

    print_leaderboard(result)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nTam sonuclar kaydedildi: {args.out}")


if __name__ == "__main__":
    main()
