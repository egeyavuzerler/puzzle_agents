"""
bank/build_bank.py

Bir katılımcının GENERATOR agent'ını alır, registry'deki HER oyun türünden
`per_type` kadar (varsayılan 500) geçerli puzzle üretir, hepsini tek bir
bank.jsonl dosyasına yazar.

Şu an registry'de 2 oyun var (zip, queens) -> 1000 puzzle.
20 oyun olduğunda otomatik olarak 20 x 500 = 10.000 üretecek;
bu dosyada değişiklik gerekmez, registry'ye oyun eklemek yeterli.

Kullanım:
    python bank/build_bank.py --generator my_agents.team_a:TeamAGenerator \
                               --out bank/team_a_bank.jsonl \
                               --per-type 500
"""

import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.registry import _auto_register_defaults, list_games, get_validator


def load_generator_class(spec: str):
    """spec formatı: 'modul.yolu:SinifAdi'"""
    module_path, class_name = spec.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_bank(generator, per_type: int, out_path: str, max_retries_per_puzzle: int = 20,
                solutions_out_path: str | None = None) -> dict:
    """
    ÖNEMLİ (unsolvable puzzle koruması): generator.generate() artık
    (puzzle, solution) ikilisi döndürür. Bir puzzle bank'e girebilmesi için
    İKİ ayrı kontrolü de geçmesi gerekir:

      1. validate_puzzle_shape(puzzle)         -> format/kural olarak tutarlı mı
      2. validate_solution(puzzle, solution)   -> generator'ın verdiği solution
                                                   gerçekten bu puzzle'ı çözüyor mu

      (2) olmadan bir generator, kuralca "şekli" geçerli ama aslında hiçbir
      çözümü olmayan bir puzzle üretip bank'e sokabilir -- katılımcı bunu
      (kasıtlı ya da kazara) yaparsa, o puzzle'ı çözemeyen HERKES aynı oranda
      cezalanır, "zorluk" değil "imkansızlık" olur. validate_solution bunu
      matematiksel olarak imkansız kılar: generator kendi solution'ını
      kanıtlamadan bank'e giremez.

      `solution` bank.jsonl'e YAZILMAZ -- solver'lar sadece puzzle'ı görür.
      İstenirse ayrı bir solutions_out_path'e (aynı id ile) yazılabilir,
      yalnızca organizatörün/denetimin erişeceği bir dosyada.
    """
    _auto_register_defaults()
    games = list_games()

    written = 0
    failed_shape = 0
    failed_solution = 0
    stats_per_game = {g: {"ok": 0, "failed_shape": 0, "failed_solution": 0} for g in games}

    solutions_f = open(solutions_out_path, "w") if solutions_out_path else None
    try:
        with open(out_path, "w") as f:
            puzzle_id = 0
            for game in games:
                validator = get_validator(game)
                difficulty_cycle = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # zorluk dağılımı basitçe döngüsel

                for i in range(per_type):
                    difficulty = difficulty_cycle[i % len(difficulty_cycle)]
                    seed = 1_000_000 * hash(game) % 999983 + i  # oyun+index'e bağlı, tekrar üretilebilir seed
                    seed = abs(seed) % (2**31)

                    ok_puzzle = None
                    ok_solution = None
                    last_err = None
                    last_err_kind = None  # "shape" | "solution" | "exception"
                    for attempt in range(max_retries_per_puzzle):
                        try:
                            candidate, candidate_solution = generator.generate(
                                game=game, difficulty=difficulty, seed=seed + attempt)
                        except Exception as e:
                            last_err, last_err_kind = f"generate() exception: {e}", "exception"
                            continue
                        if candidate.get("game") != game:
                            last_err = f"generate() '{game}' istenirken '{candidate.get('game')}' döndürdü"
                            last_err_kind = "shape"
                            continue

                        shape_ok, shape_err = validator.validate_puzzle_shape(candidate)
                        if not shape_ok:
                            last_err, last_err_kind = shape_err, "shape"
                            continue

                        solution_ok, solution_err = validator.validate_solution(candidate, candidate_solution)
                        if not solution_ok:
                            # Puzzle şekli geçerli ama generator kendi ürettiği "çözümünü"
                            # kanıtlayamadı -- YANİ ÇÖZÜLEBİLİRLİĞİ İSPATLANAMADI. Reddet.
                            last_err, last_err_kind = solution_err, "solution"
                            continue

                        ok_puzzle, ok_solution = candidate, candidate_solution
                        break

                    if ok_puzzle is None:
                        if last_err_kind == "solution":
                            failed_solution += 1
                            stats_per_game[game]["failed_solution"] += 1
                        else:
                            failed_shape += 1
                            stats_per_game[game]["failed_shape"] += 1
                        continue

                    record = {
                        "id": puzzle_id,
                        "game": game,
                        "difficulty": difficulty,
                        "puzzle": ok_puzzle,   # solution KASITLI OLARAK burada yok
                    }
                    f.write(json.dumps(record) + "\n")
                    if solutions_f:
                        solutions_f.write(json.dumps({"id": puzzle_id, "game": game,
                                                       "solution": ok_solution}) + "\n")
                    puzzle_id += 1
                    written += 1
                    stats_per_game[game]["ok"] += 1
    finally:
        if solutions_f:
            solutions_f.close()

    return {
        "written": written,
        "failed_shape": failed_shape,
        "failed_solution": failed_solution,
        "per_game": stats_per_game,
        "out_path": out_path,
        "solutions_out_path": solutions_out_path,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generator", required=True, help="modul.yolu:SinifAdi")
    parser.add_argument("--out", required=True)
    parser.add_argument("--per-type", type=int, default=500)
    parser.add_argument("--solutions-out", default=None,
                         help="(opsiyonel) witness solution'ların ayrıca yazılacağı denetim dosyası -- "
                              "solver'lara ASLA verilmemeli")
    args = parser.parse_args()

    GenClass = load_generator_class(args.generator)
    generator = GenClass()

    t0 = time.time()
    try:
        result = build_bank(generator, args.per_type, args.out, solutions_out_path=args.solutions_out)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    elapsed = time.time() - t0

    print(f"Bank yazıldı: {result['out_path']}")
    print(f"Toplam yazılan: {result['written']}")
    print(f"Reddedilen (şekil geçersiz): {result['failed_shape']}")
    print(f"Reddedilen (çözülemez -- solution kanıtlanamadı): {result['failed_solution']}")
    print(f"Oyun bazlı: {json.dumps(result['per_game'], ensure_ascii=False, indent=2)}")
    print(f"Süre: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
