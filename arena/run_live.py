"""
arena/run_live.py

Bir puzzle uretir (ya da bank'tan okur), solver'i CALISTIRIRKEN ekranda
CANLI bir matplotlib penceresi acar.

Kullanim:
    python3 arena/run_live.py --game zip --size 6
    python3 arena/run_live.py --game queens --size 8
    python3 arena/run_live.py --game tango --difficulty 5
    python3 arena/run_live.py --game patches --difficulty 5
    python3 arena/run_live.py --game slitherlink --difficulty 4
    python3 arena/run_live.py --game numberlink --difficulty 5
    python3 arena/run_live.py --game hashi --difficulty 6
    python3 arena/run_live.py --game lits --difficulty 5
    python3 arena/run_live.py --game yinyang --difficulty 5
    python3 arena/run_live.py --game tapa --difficulty 6
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from games.zip.reference_agent import solve_zip_warnsdorff
from games.queens.reference_agent import solve_queens_backtrack, solve_n_queens_any
from games.tango.reference_agent import solve_tango_backtrack, generate_tango
from games.patches.reference_agent import solve_patches_backtrack, generate_patches
from games.slitherlink.reference_agent import solve_slitherlink_backtrack, generate_slitherlink
from games.numberlink.reference_agent import solve_numberlink, generate_numberlink
from games.hashi.reference_agent import solve_hashi_backtrack, generate_hashi
from games.lits.reference_agent import solve_lits_backtrack, generate_lits
from games.yinyang.reference_agent import solve_yinyang_backtrack, generate_yinyang
from games.tapa.reference_agent import solve_tapa_backtrack, generate_tapa
from core.live_view import (LiveZipView, LiveQueensView, LiveTangoView, LivePatchesView,
                             LiveSlitherlinkView, LiveNumberlinkView, LiveHashiView,
                             LiveLitsView, LiveYinYangView, LiveTapaView)

_SIMPLE_GAMES = {
    "tango": generate_tango,
    "patches": generate_patches,
    "slitherlink": generate_slitherlink,
    "numberlink": generate_numberlink,
    "hashi": generate_hashi,
    "lits": generate_lits,
    "yinyang": generate_yinyang,
    "tapa": generate_tapa,
}


def build_puzzle(args) -> dict:
    if args.from_bank:
        with open(args.from_bank) as f:
            for line in f:
                record = json.loads(line)
                if record["game"] == args.game and (args.puzzle_id is None or record["id"] == args.puzzle_id):
                    return record["puzzle"]
        raise ValueError("bank icinde uygun puzzle bulunamadi")

    rng = random.Random(args.seed)

    if args.game == "zip":
        rows = cols = args.size
        path = []
        for r in range(rows):
            col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            for c in col_range:
                path.append((r, c))
        n_cp = min(args.n_checkpoints, len(path))
        middle = rng.sample(range(1, len(path) - 1), max(0, n_cp - 2)) if n_cp > 2 else []
        idxs = sorted({0, len(path) - 1} | set(middle))
        checkpoints = [{"order": i + 1, "pos": list(path[idx])} for i, idx in enumerate(idxs)]
        return {"game": "zip", "size": [rows, cols], "checkpoints": checkpoints, "blocked_cells": []}

    elif args.game in _SIMPLE_GAMES:
        puzzle, _solution = _SIMPLE_GAMES[args.game](rng, args.difficulty)  # solution burada gerekmiyor
        return puzzle

    else:  # queens
        solution = solve_n_queens_any(args.size, rng)
        n = args.size
        regions = [[-1] * n for _ in range(n)]
        for r in range(n):
            for c in range(n):
                best_q, best_dist = None, None
                for qi, (qr, qc) in enumerate(solution):
                    d = max(abs(r - qr), abs(c - qc))
                    if best_dist is None or d < best_dist:
                        best_dist, best_q = d, qi
                regions[r][c] = best_q
        return {"game": "queens", "size": [n, n], "regions": regions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", choices=["zip", "queens", "tango", "patches", "slitherlink",
                                            "numberlink", "hashi", "lits", "yinyang", "tapa"], required=True)
    parser.add_argument("--size", type=int, default=6, help="grid boyutu (NxN) -- zip/queens icin")
    parser.add_argument("--n-checkpoints", type=int, default=5, help="(zip) checkpoint sayisi")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--from-bank", default=None, help="bir bank.jsonl dosyasindan puzzle oku")
    parser.add_argument("--puzzle-id", type=int, default=None)
    parser.add_argument("--redraw-every", type=int, default=None,
                         help="kac adimda bir ekrani yenile")
    parser.add_argument("--pause", type=float, default=None,
                         help="her yenilemede bekleme suresi, saniye")
    parser.add_argument("--max-expansions", type=int, default=50000,
                         help="(zip) solver bu kadar dugumden sonra pes etsin")
    parser.add_argument("--difficulty", type=int, default=5,
                         help="(tango/patches/slitherlink/numberlink/hashi/lits/yinyang/tapa) 1-10 arasi")
    args = parser.parse_args()

    puzzle = build_puzzle(args)

    if args.game == "zip":
        redraw_every = args.redraw_every if args.redraw_every is not None else 25
        pause = args.pause if args.pause is not None else 0.001
        view = LiveZipView(puzzle, redraw_every=redraw_every, pause=pause)
        result, _ = solve_zip_warnsdorff(puzzle, on_step=view.on_step, max_expansions=args.max_expansions)
        view.finish(result)

    elif args.game == "tango":
        redraw_every = args.redraw_every if args.redraw_every is not None else 5
        pause = args.pause if args.pause is not None else 0.02
        view = LiveTangoView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_tango_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "patches":
        redraw_every = args.redraw_every if args.redraw_every is not None else 3
        pause = args.pause if args.pause is not None else 0.03
        view = LivePatchesView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_patches_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "slitherlink":
        redraw_every = args.redraw_every if args.redraw_every is not None else 150
        pause = args.pause if args.pause is not None else 0.01
        view = LiveSlitherlinkView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_slitherlink_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "numberlink":
        redraw_every = args.redraw_every if args.redraw_every is not None else 10
        pause = args.pause if args.pause is not None else 0.02
        view = LiveNumberlinkView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_numberlink(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "hashi":
        redraw_every = args.redraw_every if args.redraw_every is not None else 5
        pause = args.pause if args.pause is not None else 0.02
        view = LiveHashiView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_hashi_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "lits":
        redraw_every = args.redraw_every if args.redraw_every is not None else 20
        pause = args.pause if args.pause is not None else 0.02
        view = LiveLitsView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_lits_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "yinyang":
        redraw_every = args.redraw_every if args.redraw_every is not None else 3
        pause = args.pause if args.pause is not None else 0.05
        view = LiveYinYangView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_yinyang_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    elif args.game == "tapa":
        redraw_every = args.redraw_every if args.redraw_every is not None else 10
        pause = args.pause if args.pause is not None else 0.02
        view = LiveTapaView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_tapa_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    else:  # queens
        redraw_every = args.redraw_every if args.redraw_every is not None else 1
        pause = args.pause if args.pause is not None else 0.05
        view = LiveQueensView(puzzle, redraw_every=redraw_every, pause=pause)
        result = solve_queens_backtrack(puzzle, on_step=view.on_step)
        view.finish(result)

    print(f"\nSonuc: solved={result.solved}" + (f", error={result.error}" if result.error else ""))


if __name__ == "__main__":
    main()
