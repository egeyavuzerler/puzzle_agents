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

Skorlama ayrintilari:
  - Oyun agirliklari: her oyunun orani --game-weights ile agirliklandirilir
    (varsayilan hepsi 1 = oyunlar arasi makro ortalama).
  - Generator'in bankta EKSIK kalan kismi (uretemedigi, reddedilen, tekrar eden
    puzzle'lar; hic puzzle'i olmayan oyunlar dahil) rakip tarafindan "cozuldu"
    sayilir -> generator o kisimdan puan alamaz.
  - ESIT skorlarda siralamayi HAKEMIN OLCTUGU cozum suresi belirler (solver:
    hizli olan, generator: rakiplerin daha uzun surede cozdugu).

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
from core.registry import _auto_register_defaults, list_games
from arena.sandboxed_solver import SandboxedSolver


def _load_class(module_path: str, class_name: str):
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def parse_team_spec(spec: str, sandbox: str = "none", docker_image: str = "puzzle-arena",
                     submission_dir: str | None = None, memory_mb: int = 1024, cpu_seconds: int = 60):
    """
    spec format: 'takim_adi:modul.yolu:GeneratorSinifi:SolverSinifi'

    sandbox != "none" ise SOLVER hakem process'inde import EDILMEZ; ayri
    process/container'da calisir (arena/sandboxed_solver.py).
    NOT: generator sinifi hala hakem process'inde import edilir (generate()
    cagrilari izoledir ama modulun import-anindaki kodu degil). Yarisma
    gunu her takimin generator'ini da container icinde calistirin.
    """
    parts = spec.split(":")
    if len(parts) != 4:
        raise ValueError(f"gecersiz --team format: {spec!r} (beklenen: ad:modul:Generator:Solver)")
    name, module_path, gen_class_name, solver_class_name = parts
    GenClass = _load_class(module_path, gen_class_name)
    if sandbox == "none":
        solver = _load_class(module_path, solver_class_name)()
    else:
        solver = SandboxedSolver(f"{module_path}:{solver_class_name}", mode=sandbox,
                                  docker_image=docker_image, submission_dir=submission_dir,
                                  memory_mb=memory_mb, cpu_seconds=cpu_seconds)
    return {"name": name, "generator": GenClass(), "solver": solver}


def parse_game_weights(text: str | None):
    """--game-weights '{"zip": 2, "hashi": 1.5}' -> {'zip': 2.0, 'hashi': 1.5} (belirtilmeyen oyun = 1)."""
    if not text:
        return None
    try:
        weights = json.loads(text)
    except ValueError as e:
        raise ValueError(f"--game-weights gecerli JSON degil: {e}")
    if not isinstance(weights, dict):
        raise ValueError("--game-weights bir JSON nesnesi olmali, ornegin '{\"zip\": 2}'")
    _auto_register_defaults()
    known = set(list_games())
    for game, w in weights.items():
        if game not in known:
            raise ValueError(f"--game-weights: bilinmeyen oyun {game!r} (bilinenler: {sorted(known)})")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w <= 0:
            raise ValueError(f"--game-weights: {game!r} agirligi pozitif sayi olmali, gelen: {w!r}")
    return {g: float(w) for g, w in weights.items()}


def weighted_actual_rate(summary: dict, weights: dict | None = None) -> float:
    """Bir mac ozetinin oyun-agirlikli (makro) ortalama cozulme orani. Bankta olmayan oyun sayilmaz."""
    num = den = 0.0
    for game, st in summary["per_game"].items():
        if st["total"] <= 0:
            continue
        w = (weights or {}).get(game, 1.0)
        num += w * st["solved"] / st["total"]
        den += w
    return num / den if den else 0.0


def generator_effective_rate(summary: dict, per_type: int, all_games, weights: dict | None = None,
                              penalize_shortfall: bool = True) -> float:
    """
    GENERATOR skoru icin rakibin "etkin" cozulme orani. Generator'in uretemedigi /
    reddedilen / tekrar eden puzzle'lar (bankin eksik kalan kismi, hic puzzle'i
    olmayan oyunlar dahil) rakip tarafindan "cozuldu" sayilir: bu sayede dogrulanabilir
    ve FARKLI puzzle uretemeyen bir generator, zor oyunlari "atlayarak" skor kasamaz.
    (--max-puzzles ile havuzun sadece bir kismi oynaniyorsa ceza uygulanmaz.)
    """
    num = den = 0.0
    for game in all_games:
        w = (weights or {}).get(game, 1.0)
        st = summary["per_game"].get(game)
        total = st["total"] if st else 0
        solved = st["solved"] if st else 0
        if penalize_shortfall and per_type > 0:
            missing = max(0, per_type - total)
            rate = (solved + missing) / max(per_type, total)
        else:
            if total == 0:
                continue
            rate = solved / total
        num += w * rate
        den += w
    return num / den if den else 1.0


def _mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def rank_order(scores: dict, times: dict | None, time_higher_is_better: bool):
    """
    Skora gore (yuksekten dusuge) siralar; ESIT skorlarda (4 basamaga yuvarlanmis)
    hakemin olctugu cozum suresi belirler:
      - solver:    daha HIZLI cozen ustte   (time_higher_is_better=False)
      - generator: rakiplerin cozmesi daha UZUN suren ustte (time_higher_is_better=True)
    Suresi olmayan (hic puzzle cozulmemis) solver sona, generator basa gecer.
    """
    def key(item):
        name, score = item
        t = (times or {}).get(name)
        if t is None:
            tkey = float("-inf") if time_higher_is_better else float("inf")
        else:
            tkey = -t if time_higher_is_better else t
        return (-round(score, 4), tkey, name)
    return sorted(scores.items(), key=key)


def run_tournament(teams, per_type, bank_dir, time_limit_s, hard_timeout_s,
                    memory_mb, cpu_seconds, max_puzzles=None, weights=None):
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
              f"{result['failed_error']} hata/timeout, "
              f"{result['failed_duplicate']} tekrar, "
              f"{time.time()-t0:.1f}s", flush=True)
        bank_paths[team["name"]] = out_path

    _auto_register_defaults()
    all_games = list_games()
    penalize = max_puzzles is None
    matrix = {}            # oyun-agirlikli GERCEK cozulme orani (solver skoru icin)
    gen_matrix = {}        # eksik banka cezali "etkin" oran (generator skoru icin)
    time_matrix = {}       # hakemin olctugu ortalama cozum suresi (sadece cozulenler)
    full_results = {}
    total_pairs = len(teams) * len(teams)
    pair_i = 0
    for gen_team in teams:
        matrix[gen_team["name"]] = {}
        gen_matrix[gen_team["name"]] = {}
        time_matrix[gen_team["name"]] = {}
        full_results[gen_team["name"]] = {}
        for solver_team in teams:
            pair_i += 1
            print(f"[arena {pair_i}/{total_pairs}] {solver_team['name']} solver'i "
                  f"{gen_team['name']} havuzuna karsi...", flush=True)
            summary = run_match(
                solver_team["solver"], bank_paths[gen_team["name"]],
                time_limit_s, hard_timeout_s, memory_mb, cpu_seconds, max_puzzles,
            )
            g_name, s_name = gen_team["name"], solver_team["name"]
            matrix[g_name][s_name] = weighted_actual_rate(summary, weights)
            gen_matrix[g_name][s_name] = generator_effective_rate(
                summary, per_type, all_games, weights, penalize_shortfall=penalize)
            time_matrix[g_name][s_name] = summary.get("avg_solved_time_s")
            full_results[g_name][s_name] = summary
            print(f"       solve_rate={matrix[g_name][s_name]:.3f}", flush=True)

    team_names = [t["name"] for t in teams]

    solver_scores = {}
    solver_times = {}
    for solver_name in team_names:
        # Hic puzzle'i olmayan bir havuz (generator hic uretememis) solver'i cezalandirmasin
        gens = [g for g in team_names if full_results[g][solver_name]["total_puzzles"] > 0]
        rates = [matrix[g][solver_name] for g in gens]
        solver_scores[solver_name] = sum(rates) / len(rates) if rates else 0.0
        solver_times[solver_name] = _mean([time_matrix[g][solver_name] for g in gens])

    generator_scores = {}
    generator_times = {}
    for gen_name in team_names:
        opponents = [s for s in team_names if s != gen_name] or [gen_name]  # tek takimsa kendisi
        avg_opponent_solve_rate = sum(gen_matrix[gen_name][s] for s in opponents) / len(opponents)
        generator_scores[gen_name] = 1.0 - avg_opponent_solve_rate
        generator_times[gen_name] = _mean([time_matrix[gen_name][s] for s in opponents])

    return {
        "teams": team_names,
        "matrix": matrix,
        "generator_matrix": gen_matrix,
        "solver_scores": solver_scores,
        "generator_scores": generator_scores,
        "solver_times": solver_times,
        "generator_times": generator_times,
        "weights": weights,
        "shortfall_penalty": penalize,
        "full_results": full_results,
    }


def print_leaderboard(result):
    print("\n" + "=" * 60)
    print("SOLVER SIRALAMASI (yuksek = daha cok puzzle cozdu)")
    print("=" * 60)
    solver_times = result.get("solver_times", {})
    for name, score in rank_order(result["solver_scores"], solver_times, time_higher_is_better=False):
        t = solver_times.get(name)
        print(f"  {name:20s}  {score:.3f}" + (f"   (ort. cozum suresi {t:.2f}s)" if t is not None else ""))

    print("\n" + "=" * 60)
    print("GENERATOR SIRALAMASI (yuksek = puzzle'lari rakiplere daha zor geldi)")
    print("=" * 60)
    generator_times = result.get("generator_times", {})
    for name, score in rank_order(result["generator_scores"], generator_times, time_higher_is_better=True):
        t = generator_times.get(name)
        print(f"  {name:20s}  {score:.3f}" + (f"   (rakiplerin ort. cozum suresi {t:.2f}s)" if t is not None else ""))

    print("\n" + "=" * 60)
    print("TAM MATRIS (satir=generator, sutun=solver, deger=solve_rate, oyun agirlikli)")
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
    parser.add_argument("--sandbox", choices=["none", "local", "docker"], default="none",
                         help="solver'ları nerede çalıştır (bkz. arena/run_match.py --help)")
    parser.add_argument("--docker-image", default="puzzle-arena")
    parser.add_argument("--game-weights", default=None,
                         help='oyun agirliklari (JSON), ornegin \'{"zip": 2, "hashi": 1.5}\'; belirtilmeyen oyun = 1')
    parser.add_argument("--submission-dir", default=None,
                         help="--sandbox docker: katılımcı kodunun klasörü (salt-okunur bağlanır)")
    args = parser.parse_args()

    try:
        weights = parse_game_weights(args.game_weights)
    except ValueError as e:
        parser.error(str(e))

    teams = [parse_team_spec(spec, args.sandbox, args.docker_image, args.submission_dir,
                              args.memory_mb, args.cpu_seconds) for spec in args.team]
    if len(teams) < 1:
        print("en az 1 takim gerekli")
        sys.exit(1)

    try:
        result = run_tournament(
            teams, args.per_type, args.bank_dir,
            args.time_limit, args.hard_timeout, args.memory_mb, args.cpu_seconds, args.max_puzzles,
            weights=weights,
        )
    finally:
        for t in teams:
            if hasattr(t["solver"], "close"):
                t["solver"].close()

    print_leaderboard(result)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nTam sonuclar kaydedildi: {args.out}")


if __name__ == "__main__":
    main()
