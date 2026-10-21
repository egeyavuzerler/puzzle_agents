"""
arena/check_submission.py

GONDERMEDEN ONCE kendi generator ve solver'inizi, organizatorun kullanacagi
AYNI izole hatla deneyin. Sorunlari yarisma gunu degil simdi gorun.

Kontrol ettikleri:
  1. Yukleme: modul import ediliyor mu, sinif var mi, olusturulabiliyor mu
  2. GENERATOR: her oyundan birkac puzzle uretir; sekil + witness solution
     kontrolunden gecen kac tanesi havuza girerdi (organizatorle ayni kural,
     ayni sure/bellek siniri, generate() ayri process'te calisir)
  3. SOLVER: iki havuza karsi calisir -- (a) referans generator'un (garanti
     gecerli) puzzle'lari, (b) kendi generator'unuzun puzzle'lari. Solver ayri
     process'te, cevabi JSON olarak dondurulerek calistirilir (yarisma gunuyle
     ayni protokol): cevabiniz JSON'a cevrilemiyorsa (ornegin numpy dizisi,
     set) burada hata olarak gorursunuz.

Kullanim:
    python3 arena/check_submission.py \
        --generator takim_x.agent:MyGenerator --solver takim_x.agent:MySolver

    # sadece bazi oyunlar, daha cok puzzle:
    python3 arena/check_submission.py --generator takim_x.agent:MyGenerator \
        --games zip,queens --per-type 5

    # kodunuz proje kokunun disindaki bir klasordeyse:
    python3 arena/check_submission.py --solver agent:MySolver --path /yol/klasor

Cikis kodu: [HATA] varsa 1, yoksa 0. [UYARI]'lar gonderimi engellemez ama bakmaya deger.
"""

import argparse
import importlib
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents_examples.baseline import BaselineGenerator
from arena.run_match import run_match
from arena.sandboxed_solver import SandboxedSolver
from bank.build_bank import build_bank
from core.base import BaseGeneratorAgent, BaseSolverAgent
from core.registry import _auto_register_defaults, list_games

OK, WARN, ERR = "[OK]    ", "[UYARI] ", "[HATA]  "


def _load_class(spec: str):
    module_path, class_name = spec.split(":")
    return getattr(importlib.import_module(module_path), class_name)


def _short_tb() -> str:
    return traceback.format_exc(limit=3).strip().splitlines()[-1]


def run_checks(generator_spec: str | None, solver_spec: str | None, games: list[str] | None = None,
               per_type: int = 3, time_limit_s: float = 10.0, gen_timeout_s: float = 20.0,
               extra_paths: list[str] | None = None, out=print) -> dict:
    """Kontrolleri calistirir, raporu `out` ile yazdirir, {"errors": n, "warnings": n, ...} dondurur."""
    _auto_register_defaults()
    all_games = list_games()
    games = games or all_games
    for p in extra_paths or []:
        sys.path.insert(0, str(Path(p).resolve()))

    report = {"errors": 0, "warnings": 0, "generator": None, "solver": None}

    def say(tag, msg):
        if tag == ERR:
            report["errors"] += 1
        elif tag == WARN:
            report["warnings"] += 1
        out(f"  {tag}{msg}")

    out("=" * 64)
    out("GONDERIM KONTROLU")
    out("=" * 64)

    # ------------------------------------------------------------ 1) yukleme
    out("\n[1/3] Yukleme")
    generator = solver = None
    if generator_spec:
        try:
            cls = _load_class(generator_spec)
            generator = cls()
            say(OK, f"generator yuklendi: {generator_spec}")
            if not isinstance(generator, BaseGeneratorAgent):
                say(WARN, "generator BaseGeneratorAgent'tan miras almiyor (zorunlu degil ama onerilir)")
            if not callable(getattr(generator, "generate", None)):
                say(ERR, "generator sinifinda generate() metodu yok")
                generator = None
        except Exception:
            say(ERR, f"generator yuklenemedi ({generator_spec}): {_short_tb()}")
    if solver_spec:
        try:
            cls = _load_class(solver_spec)
            inst = cls()
            say(OK, f"solver yuklendi: {solver_spec}")
            if not isinstance(inst, BaseSolverAgent):
                say(WARN, "solver BaseSolverAgent'tan miras almiyor (zorunlu degil ama onerilir)")
            if not callable(getattr(inst, "solve", None)):
                say(ERR, "solver sinifinda solve() metodu yok")
            else:
                solver = True
        except Exception:
            say(ERR, f"solver yuklenemedi ({solver_spec}): {_short_tb()}")

    tmp = tempfile.mkdtemp(prefix="check_submission_")
    own_bank = None

    # ------------------------------------------------------------ 2) generator
    out(f"\n[2/3] Generator (her oyundan {per_type} puzzle; generate() basina {gen_timeout_s:g}s sinir)")
    if generator is None:
        out("  (atlandi)")
    else:
        out("  (kotu giden bir generator'da bu adim birkac dakika surebilir)")
        path = os.path.join(tmp, "own_bank.jsonl")
        res = build_bank(generator, per_type, path, max_retries_per_puzzle=2, gen_timeout_s=gen_timeout_s,
                         games=games, max_consecutive_failures=2,
                         game_time_budget_s=max(60.0, per_type * gen_timeout_s * 2))
        report["generator"] = res
        for g in games:
            st = res["per_game"][g]
            line = f"{g:12s} {st['ok']}/{per_type} havuza girdi  ({st['seconds']:.1f}s)"
            if st["ok"] == per_type:
                tag = OK
            elif st["ok"] > 0:
                tag = WARN
            else:
                tag = ERR
            if st["ok"] < per_type and st["example_error"]:
                line += f"\n{'':11s}ilk hata -> {st['example_error']}"
            if st["gave_up"]:
                line += f"\n{'':11s}(bu oyundan vazgecildi: {st['gave_up']})"
            say(tag, line)
            if st["ok"] and st["seconds"] / max(1, st["ok"]) > gen_timeout_s * 0.5:
                say(WARN, f"{g}: yavas, puzzle basina ort. {st['seconds']/st['ok']:.1f}s (sinir {gen_timeout_s:g}s)")
        if res["written"] > 0:
            own_bank = path

    # ------------------------------------------------------------ 3) solver
    out(f"\n[3/3] Solver (cozum suresi siniri {time_limit_s:g}s/puzzle)")
    if not solver:
        out("  (atlandi)")
    else:
        ref_path = os.path.join(tmp, "ref_bank.jsonl")
        build_bank(BaselineGenerator(), per_type, ref_path, games=games, isolate=False)
        banks = [("referans havuz (garanti gecerli puzzle'lar)", ref_path)]
        if own_bank:
            banks.append(("kendi generator'unuzun havuzu", own_bank))
        elif generator_spec:
            out("  (kendi havuzunuz bos oldugu icin solver sadece referans havuza karsi denenecek)")
        report["solver"] = {}
        for label, bank_path in banks:
            out(f"\n  -- {label}")
            with SandboxedSolver(solver_spec, mode="local", extra_pythonpath=extra_paths) as sv:
                summary = run_match(sv, bank_path, time_limit_s, time_limit_s + 5.0)
            report["solver"][label] = summary
            for g in games:
                st = summary["per_game"].get(g)
                if not st:
                    continue
                line = f"{g:12s} {st['solved']}/{st['total']} cozdu"
                if st["avg_solved_time_s"] is not None:
                    line += f"  (ort. {st['avg_solved_time_s']:.2f}s)"
                if st["invalid_solution"] > 0:
                    tag = ERR
                    line += f"\n{'':11s}{st['invalid_solution']} cevap GECERSIZ sayildi: {st['first_error']}"
                elif st["errors"] == st["total"]:
                    tag = ERR
                    line += f"\n{'':11s}her puzzle'da hata -> {st['first_error']}"
                elif st["errors"] > 0 or st["timeouts"] > 0:
                    tag = WARN
                    line += f"\n{'':11s}{st['errors']} hata, {st['timeouts']} zaman asimi"
                    if st["first_error"]:
                        line += f" -> {st['first_error']}"
                else:
                    tag = OK
                say(tag, line)
            out(f"  Genel: {summary['total_solved']}/{summary['total_puzzles']} puzzle cozuldu "
                f"(bilgi amacli; asil skor rakiplerin puzzle'lariyla olculur)")

    # ------------------------------------------------------------ sonuc
    out("\n" + "=" * 64)
    if report["errors"]:
        out(f"SONUC: {report['errors']} HATA, {report['warnings']} uyari -- gondermeden once duzeltin.")
    elif report["warnings"]:
        out(f"SONUC: hata yok, {report['warnings']} uyari -- gonderebilirsiniz, uyarilara bakmaniz onerilir.")
    else:
        out("SONUC: her sey yolunda -- gonderime hazir.")
    out("=" * 64)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Gonderim oncesi generator/solver kontrolu")
    parser.add_argument("--generator", help="modul.yolu:SinifAdi")
    parser.add_argument("--solver", help="modul.yolu:SinifAdi")
    parser.add_argument("--games", help="virgullu oyun listesi (varsayilan: hepsi)")
    parser.add_argument("--per-type", type=int, default=3, help="oyun basina puzzle sayisi (varsayilan 3)")
    parser.add_argument("--time-limit", type=float, default=10.0, help="solver sure siniri (sn, varsayilan 10)")
    parser.add_argument("--gen-timeout", type=float, default=20.0, help="generate() cagrisi sinirI (sn, varsayilan 20)")
    parser.add_argument("--path", action="append", default=[], help="kodunuzun bulundugu klasor (birden fazla verilebilir)")
    args = parser.parse_args()

    if not args.generator and not args.solver:
        parser.error("en az bir tane --generator ya da --solver verin")
    games = [g.strip() for g in args.games.split(",")] if args.games else None
    if games:
        _auto_register_defaults()
        unknown = [g for g in games if g not in list_games()]
        if unknown:
            parser.error(f"bilinmeyen oyun(lar): {unknown} (bilinenler: {list_games()})")

    report = run_checks(args.generator, args.solver, games, args.per_type, args.time_limit,
                        args.gen_timeout, args.path)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
