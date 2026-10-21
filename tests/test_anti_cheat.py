"""
Unsolvable-puzzle korumasi: generator'in cozumu KANITLANMAYAN puzzle'i bank'e giremez,
solution bank'e yazilmaz, solutions dosyasi gizli izinle yazilir.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bank.build_bank as bb
from agents_examples.baseline import BaselineGenerator
from agents_examples.evil_generators import UnsolvableGenerator, WrongSolutionGenerator

GAMES = ["zip", "queens", "tapa"]


class AntiCheatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch("bank.build_bank.list_games", return_value=GAMES)
        p.start()
        self.addCleanup(p.stop)

    def _build(self, generator, **kw):
        out = os.path.join(self.tmp.name, "bank.jsonl")
        result = bb.build_bank(generator, 3, out, max_retries_per_puzzle=2, **kw)
        return result, out

    def test_cozumsuz_puzzle_bank_e_giremez(self):
        result, out = self._build(UnsolvableGenerator())
        self.assertEqual(result["written"], 0)
        self.assertEqual(result["failed_solution"], 3 * len(GAMES))
        self.assertEqual(Path(out).read_text(), "")

    def test_yanlis_solution_bank_e_giremez(self):
        result, _ = self._build(WrongSolutionGenerator())
        self.assertEqual(result["written"], 0)
        self.assertEqual(result["failed_solution"], 3 * len(GAMES))

    def test_dogru_generator_hepsi_girer(self):
        result, _ = self._build(BaselineGenerator())
        self.assertEqual(result["written"], 3 * len(GAMES))
        self.assertEqual(result["failed_shape"] + result["failed_solution"] + result["failed_error"], 0)

    def test_bank_solution_icermez(self):
        _, out = self._build(BaselineGenerator())
        lines = Path(out).read_text().strip().splitlines()
        self.assertTrue(lines)
        for line in lines:
            record = json.loads(line)
            self.assertNotIn("solution", record)
            self.assertNotIn("solution", record["puzzle"])

    @unittest.skipUnless(os.name == "posix", "dosya izinleri sadece POSIX'te")
    def test_solutions_dosyasi_gizli_izinli(self):
        sol_path = os.path.join(self.tmp.name, "solutions.jsonl")
        # eski, gevsek izinli bir dosya varsa bile 0600'e cekilmeli
        Path(sol_path).write_text("eski")
        os.chmod(sol_path, 0o644)
        self._build(BaselineGenerator(), solutions_out_path=sol_path)
        mode = stat.S_IMODE(os.stat(sol_path).st_mode)
        self.assertEqual(mode, 0o600)
        self.assertTrue(Path(sol_path).read_text().strip())


class ZamanKorumasiTest(unittest.TestCase):
    """Bozuk/kotu niyetli generator hakemin zamanini sinirsiz tuketemez."""
    GAMES = ["zip", "queens"]

    def _build(self, generator, per_type=30, games=None, timeout=0.3, retries=1, **kw):
        import time
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("bank.build_bank.list_games", return_value=games or self.GAMES):
            t0 = time.time()
            result = bb.build_bank(generator, per_type, os.path.join(tmp, "b.jsonl"),
                                    max_retries_per_puzzle=retries, gen_timeout_s=timeout, **kw)
            return result, time.time() - t0

    def test_ardisik_basarisizlikta_vazgecer(self):
        from agents_examples.evil_generators import HangingGenerator
        result, elapsed = self._build(HangingGenerator(), max_consecutive_failures=3)
        for game in self.GAMES:
            st = result["per_game"][game]
            self.assertEqual(st["gave_up"], "ardisik_basarisizlik")
            self.assertEqual(st["failed_error"], 3)
            self.assertEqual(st["skipped"], 27)
        self.assertEqual(result["written"], 0)
        self.assertLess(elapsed, 15)   # 30 puzzle x 2 oyun x 0.3s = 18s olurdu

    def test_sure_butcesi(self):
        from agents_examples.evil_generators import DuplicateSpamGenerator
        result, _ = self._build(DuplicateSpamGenerator(), game_time_budget_s=0.0)
        for game in self.GAMES:
            self.assertEqual(result["per_game"][game]["gave_up"], "sure_butcesi")
        self.assertEqual(result["written"], 0)

    def test_saglikli_generator_etkilenmez(self):
        result, _ = self._build(BaselineGenerator(), per_type=12, timeout=20.0, retries=20)
        self.assertEqual(result["written"], 12 * len(self.GAMES))
        for game in self.GAMES:
            self.assertIsNone(result["per_game"][game]["gave_up"])
            self.assertEqual(result["per_game"][game]["skipped"], 0)

    def test_tekil_basarisizlik_sayaci_sifirlar(self):
        """Arada basarili puzzle varsa 'ardisik' sayaci sifirlanir (FlakyGenerator: yari yariya takilir)."""
        from agents_examples.evil_generators import FlakyGenerator
        result, _ = self._build(FlakyGenerator(), per_type=6, games=["queens"], timeout=1.0,
                                max_consecutive_failures=3)
        self.assertIsNone(result["per_game"]["queens"]["gave_up"])
        self.assertGreater(result["written"], 0)


if __name__ == "__main__":
    unittest.main()
