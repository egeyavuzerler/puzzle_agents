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
import contextlib
import importlib
import io
import json
import os
import sys
import time
import traceback
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.registry import _auto_register_defaults, list_games, get_validator
from core.sandbox import IsolatedWorker


def load_generator_class(spec: str):
    """spec formatı: 'modul.yolu:SinifAdi'"""
    module_path, class_name = spec.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# Yeniden deneme seed'leri baska puzzle'larin seed'leriyle CAKISMASIN diye her deneme
# bu kadar atlar (puzzle index'i bundan kucuk oldugu surece seed'ler birbirinden ayridir).
_ATTEMPT_SEED_STRIDE = 10_007


def _write_file(path: str, text: str, mode: int) -> None:
    """Dosyayi verilen izinle (rwx bitleri) yazar ve diske zorlar."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    if hasattr(os, "fchmod"):
        os.fchmod(fd, mode)  # dosya onceden varsa eski (gevsek) izinler kalmasin
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def build_bank(generator, per_type: int, out_path: str, max_retries_per_puzzle: int = 20,
                solutions_out_path: str | None = None, gen_timeout_s: float = 20.0,
                gen_memory_mb: int = 1024, gen_cpu_seconds: int = 60,
                isolate: bool = True, max_consecutive_failures: int = 10,
                game_time_budget_s: float | None = 600.0, games: list[str] | None = None) -> dict:
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

    İZOLASYON: generator.generate() katılımcı kodudur, hakemin process'inde
    ÇALIŞTIRILMAZ. core.sandbox.IsolatedWorker ile ayrı bir process'te,
    çağrı başına `gen_timeout_s` saniye duvar-saati sınırı ve bellek/CPU
    limitiyle çalışır. Sonsuz döngü, aşırı bellek, process'i öldürme ya da
    anlamsız dönüş değeri sadece o denemeyi "başarısız" yapar (failed_error),
    bank üretimi devam eder. `isolate=False` yalnızca hata ayıklama içindir.

    ZAMAN KORUMASI: bozuk/kötü niyetli bir generator (her çağrıda takılan, hep aynı puzzle'ı
    basan...) hakemin saatlerini yiyemez:
      - bir oyunda `max_consecutive_failures` puzzle ARDIŞIK başarısız olursa o oyundan vazgeçilir
      - bir oyun için harcanabilecek süre `game_time_budget_s` ile sınırlıdır (None = sınırsız)
    Vazgeçilen oyunun kalan puzzle'ları üretilmez (bankta EKSİK kalır; turnuva skorunda
    generator bu eksikten puan alamaz) ve `per_game[oyun]["gave_up"]` nedeni yazar.
    """
    _auto_register_defaults()
    all_games = list_games()
    if games is None:
        games = all_games
    else:
        unknown = [g for g in games if g not in all_games]
        if unknown:
            raise ValueError(f"bilinmeyen oyun(lar): {unknown} (bilinenler: {all_games})")

    written = 0
    failed_shape = 0
    failed_solution = 0
    failed_error = 0
    failed_duplicate = 0
    seen_puzzles: set[str] = set()   # bank'te ZATEN olan puzzle'lar (tekrar kabul edilmez)
    stats_per_game = {g: {"ok": 0, "failed_shape": 0, "failed_solution": 0, "failed_error": 0,
                          "failed_duplicate": 0, "gave_up": None, "skipped": 0,
                          "example_error": None, "seconds": 0.0} for g in games}

    worker = IsolatedWorker(generator, gen_memory_mb, gen_cpu_seconds) if isolate else None

    def _call_generate(game_name, diff, seed_value):
        if worker is None:
            try:
                return True, generator.generate(game=game_name, difficulty=diff, seed=seed_value)
            except Exception as e:
                return False, f"{type(e).__name__}: {e}"
        return worker.call("generate", gen_timeout_s,
                           game=game_name, difficulty=diff, seed=seed_value)

    # Dosyalar bellekte biriktirilir, generator worker'i KAPANDIKTAN SONRA yazilir:
    # worker (katilimci kodu) bank dosyasina sahte/dogrulanmamis satir sizdiramaz.
    solutions_f = io.StringIO() if solutions_out_path else None
    try:
        with contextlib.nullcontext(io.StringIO()) as f:
            puzzle_id = 0
            for game in games:
                validator = get_validator(game)
                difficulty_cycle = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # zorluk dağılımı basitçe döngüsel

                game_start = time.time()
                consecutive_failures = 0
                attempted = 0
                gave_up = None

                for i in range(per_type):
                    if consecutive_failures >= max_consecutive_failures:
                        gave_up = "ardisik_basarisizlik"
                        break
                    if game_time_budget_s is not None and time.time() - game_start > game_time_budget_s:
                        gave_up = "sure_butcesi"
                        break
                    attempted += 1
                    difficulty = difficulty_cycle[i % len(difficulty_cycle)]
                    # Oyun+index'e bağlı, GERÇEKTEN tekrar üretilebilir seed. (Eskiden hash(game)
                    # kullanılıyordu; Python'da str hash'i her çalıştırmada rastgele değişir.)
                    seed = (1_000_000 * (zlib.crc32(game.encode("utf-8")) % 999983) + i) % (2**31)

                    ok_puzzle = None
                    ok_solution = None
                    last_err = None
                    last_err_kind = None  # "shape" | "solution" | "exception"
                    for attempt in range(max_retries_per_puzzle):
                        ok, res = _call_generate(game, difficulty, (seed + attempt * _ATTEMPT_SEED_STRIDE) % (2**31))
                        if not ok:
                            last_err, last_err_kind = f"generate() hatasi: {res}", "exception"
                            continue
                        if not (isinstance(res, (tuple, list)) and len(res) == 2):
                            last_err, last_err_kind = "generate() (puzzle, solution) ikilisi döndürmedi", "shape"
                            continue
                        candidate, candidate_solution = res
                        if not isinstance(candidate, dict):
                            last_err, last_err_kind = "generate() puzzle olarak dict döndürmedi", "shape"
                            continue
                        try:  # bank.jsonl'e yazilabilmeli
                            json.dumps(candidate)
                            json.dumps(candidate_solution)
                        except (TypeError, ValueError) as e:
                            last_err, last_err_kind = f"puzzle/solution JSON'a çevrilemedi: {e}", "shape"
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

                        # Tekrar kontrolü: aynı puzzle'ı defalarca bank'e koyup havuzu şişirmek
                        # (ya da tek bir zor puzzle'la skor kasmak) engellenir.
                        puzzle_key = json.dumps(candidate, sort_keys=True)
                        if puzzle_key in seen_puzzles:
                            last_err, last_err_kind = "bank'te zaten var (tekrar eden puzzle)", "duplicate"
                            continue

                        ok_puzzle, ok_solution = candidate, candidate_solution
                        seen_puzzles.add(puzzle_key)
                        break

                    if ok_puzzle is None:
                        consecutive_failures += 1
                        if stats_per_game[game]["example_error"] is None:   # katilimciya gosterilecek ilk hata
                            stats_per_game[game]["example_error"] = f"{last_err_kind}: {str(last_err)[:300]}"
                        if last_err_kind == "solution":
                            failed_solution += 1
                            stats_per_game[game]["failed_solution"] += 1
                        elif last_err_kind == "exception":
                            failed_error += 1
                            stats_per_game[game]["failed_error"] += 1
                        elif last_err_kind == "duplicate":
                            failed_duplicate += 1
                            stats_per_game[game]["failed_duplicate"] += 1
                        else:
                            failed_shape += 1
                            stats_per_game[game]["failed_shape"] += 1
                        continue

                    consecutive_failures = 0
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

                stats_per_game[game]["gave_up"] = gave_up
                stats_per_game[game]["seconds"] = round(time.time() - game_start, 2)
                stats_per_game[game]["skipped"] = per_type - attempted
    finally:
        if worker is not None:
            worker.close()

    _write_file(out_path, f.getvalue(), 0o644)
    if solutions_f is not None:
        _write_file(solutions_out_path, solutions_f.getvalue(), 0o600)  # sadece sahibi okur

    return {
        "written": written,
        "failed_shape": failed_shape,
        "failed_solution": failed_solution,
        "failed_error": failed_error,
        "failed_duplicate": failed_duplicate,
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
    parser.add_argument("--gen-timeout", type=float, default=20.0,
                         help="generate() başına duvar-saati sınırı (saniye, varsayılan 20)")
    parser.add_argument("--gen-memory-mb", type=int, default=1024,
                         help="generator process'ine bellek limiti (MB, varsayılan 1024)")
    parser.add_argument("--max-consecutive-failures", type=int, default=10,
                         help="bir oyunda bu kadar puzzle ARDIŞIK başarısız olursa o oyundan vazgeç (varsayılan 10)")
    parser.add_argument("--game-time-budget", type=float, default=600.0,
                         help="oyun başına en fazla harcanacak süre, saniye (varsayılan 600; 0 = sınırsız)")
    parser.add_argument("--no-isolation", action="store_true",
                         help="(yalnızca hata ayıklama) generator'ı ana process'te çalıştır")
    args = parser.parse_args()

    GenClass = load_generator_class(args.generator)
    generator = GenClass()

    t0 = time.time()
    try:
        result = build_bank(generator, args.per_type, args.out, solutions_out_path=args.solutions_out,
                             gen_timeout_s=args.gen_timeout, gen_memory_mb=args.gen_memory_mb,
                             isolate=not args.no_isolation,
                             max_consecutive_failures=args.max_consecutive_failures,
                             game_time_budget_s=args.game_time_budget or None)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    elapsed = time.time() - t0

    print(f"Bank yazıldı: {result['out_path']}")
    print(f"Toplam yazılan: {result['written']}")
    print(f"Reddedilen (şekil geçersiz): {result['failed_shape']}")
    print(f"Reddedilen (çözülemez -- solution kanıtlanamadı): {result['failed_solution']}")
    print(f"Reddedilen (generator hata/timeout/çökme): {result['failed_error']}")
    print(f"Reddedilen (tekrar eden puzzle): {result['failed_duplicate']}")
    for g, st in result["per_game"].items():
        if st["gave_up"]:
            print(f"UYARI: '{g}' oyunundan vazgeçildi ({st['gave_up']}), {st['skipped']} puzzle üretilmedi")
    print(f"Oyun bazlı: {json.dumps(result['per_game'], ensure_ascii=False, indent=2)}")
    print(f"Süre: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
