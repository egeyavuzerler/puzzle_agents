"""
Skorlama dayanikliligi: oyun agirliklari, eksik banka ceza, tekrar eden puzzle,
sureyle beraberlik bozma ve tekrar uretilebilir seed.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import arena.run_tournament as rt
import bank.build_bank as bb
from agents_examples.baseline import BaselineGenerator
from agents_examples.evil_generators import DuplicateSpamGenerator


def _summary(**games):
    """_summary(zip=(total, solved), ...) -> run_match ozeti taklidi"""
    per_game = {g: {"total": t, "solved": s, "solve_rate": (s / t if t else 0.0)}
                for g, (t, s) in games.items()}
    return {"per_game": per_game, "total_puzzles": sum(t for t, _ in games.values())}


class AgirlikTest(unittest.TestCase):
    def test_esit_agirlik_makro_ortalama(self):
        s = _summary(zip=(10, 10), hashi=(10, 0))
        self.assertAlmostEqual(rt.weighted_actual_rate(s), 0.5)

    def test_oyun_agirligi_etkiler(self):
        s = _summary(zip=(10, 10), hashi=(10, 0))
        self.assertAlmostEqual(rt.weighted_actual_rate(s, {"zip": 3}), 0.75)

    def test_bankta_olmayan_oyun_solver_skorunu_dusurmez(self):
        s = _summary(zip=(10, 10))
        self.assertAlmostEqual(rt.weighted_actual_rate(s), 1.0)

    def test_agirlik_dogrulamasi(self):
        self.assertIsNone(rt.parse_game_weights(None))
        self.assertEqual(rt.parse_game_weights('{"zip": 2, "hashi": 1.5}'), {"zip": 2.0, "hashi": 1.5})
        for bad in ("{bozuk", "[1]", '{"yok_boyle_oyun": 2}', '{"zip": -1}', '{"zip": 0}',
                    '{"zip": true}', '{"zip": "2"}'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    rt.parse_game_weights(bad)


class EksikBankaCezasiTest(unittest.TestCase):
    GAMES = ["zip", "hashi"]

    def test_hic_puzzle_olmayan_oyun_generator_icin_cozuldu_sayilir(self):
        s = _summary(zip=(10, 2))                       # hashi icin hic puzzle yok
        rate = rt.generator_effective_rate(s, 10, self.GAMES)
        self.assertAlmostEqual(rate, (0.2 + 1.0) / 2)

    def test_kismi_eksik(self):
        s = _summary(zip=(6, 0), hashi=(10, 0))         # zip'te 4 puzzle eksik
        rate = rt.generator_effective_rate(s, 10, self.GAMES)
        self.assertAlmostEqual(rate, (0.4 + 0.0) / 2)

    def test_tam_banka_ceza_yok(self):
        s = _summary(zip=(10, 3), hashi=(10, 5))
        self.assertAlmostEqual(rt.generator_effective_rate(s, 10, self.GAMES), (0.3 + 0.5) / 2)

    def test_max_puzzles_modunda_ceza_uygulanmaz(self):
        s = _summary(zip=(3, 0))
        self.assertAlmostEqual(rt.generator_effective_rate(s, 10, self.GAMES, penalize_shortfall=False), 0.0)


class BeraberlikTest(unittest.TestCase):
    def test_solver_esit_skorda_hizli_olan_ustte(self):
        order = rt.rank_order({"yavas": 0.8, "hizli": 0.8, "iyi": 0.9},
                              {"yavas": 5.0, "hizli": 1.0, "iyi": 9.0}, time_higher_is_better=False)
        self.assertEqual([n for n, _ in order], ["iyi", "hizli", "yavas"])

    def test_generator_esit_skorda_rakibi_daha_uzun_ugrastiran_ustte(self):
        order = rt.rank_order({"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 4.0}, time_higher_is_better=True)
        self.assertEqual([n for n, _ in order], ["b", "a"])

    def test_suresi_olmayanlar(self):
        # solver hic puzzle cozmediyse (sure None) esit skorda sona gider
        order = rt.rank_order({"x": 0.0, "y": 0.0}, {"x": None, "y": 2.0}, time_higher_is_better=False)
        self.assertEqual([n for n, _ in order], ["y", "x"])
        # generator'in puzzle'larini kimse cozmediyse (sure None) esit skorda basa gecer
        order = rt.rank_order({"x": 1.0, "y": 1.0}, {"x": None, "y": 2.0}, time_higher_is_better=True)
        self.assertEqual([n for n, _ in order], ["x", "y"])

    def test_skor_farki_sureden_once_gelir(self):
        order = rt.rank_order({"a": 0.9, "b": 0.5}, {"a": 99.0, "b": 0.1}, time_higher_is_better=False)
        self.assertEqual([n for n, _ in order], ["a", "b"])


class TekrarVeSeedTest(unittest.TestCase):
    GAMES = ["zip", "queens"]

    def test_tekrar_eden_puzzle_elenir(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("bank.build_bank.list_games", return_value=self.GAMES):
            out = os.path.join(tmp, "b.jsonl")
            r = bb.build_bank(DuplicateSpamGenerator(), 4, out, max_retries_per_puzzle=3)
        self.assertEqual(r["written"], len(self.GAMES))            # oyun basina sadece 1 tane
        self.assertEqual(r["failed_duplicate"], 3 * len(self.GAMES))

    def test_tekrar_spam_generator_turnuvada_puan_alamaz(self):
        spec = "agents_examples.{}:{}:BaselineSolver"
        teams = [rt.parse_team_spec("iyi:" + spec.format("baseline", "BaselineGenerator")),
                 rt.parse_team_spec("spam:" + spec.format("evil_generators", "DuplicateSpamGenerator"))]
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("bank.build_bank.list_games", return_value=self.GAMES), \
                mock.patch("arena.run_tournament.list_games", return_value=self.GAMES), \
                contextlib.redirect_stdout(io.StringIO()):
            res = rt.run_tournament(teams, 4, tmp, 3, 6, 1024, 60)
        # spam bankasinda oyun basina 1/4 puzzle var -> rakip etkin orani >= 0.75 -> skor <= 0.25
        self.assertLessEqual(res["generator_scores"]["spam"], 0.25 + 1e-9)
        self.assertGreaterEqual(res["generator_scores"]["iyi"], res["generator_scores"]["spam"])
        # spam'in etkin orani, bankin eksik kismi yuzunden en az 3/4:
        for solver in ("iyi", "spam"):
            self.assertGreaterEqual(res["generator_matrix"]["spam"][solver], 0.75 - 1e-9)

    def test_seed_PYTHONHASHSEED_den_bagimsiz(self):
        digests = []
        for hashseed in ("1", "2"):
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "b.jsonl")
                code = ("import sys; sys.path.insert(0, %r); "
                        "from unittest import mock; import bank.build_bank as bb; "
                        "from agents_examples.baseline import BaselineGenerator; "
                        "mock.patch('bank.build_bank.list_games', return_value=['zip','queens','tapa']).start(); "
                        "bb.build_bank(BaselineGenerator(), 3, %r)" % (str(ROOT), out))
                subprocess.run([sys.executable, "-c", code], check=True, cwd=str(ROOT),
                               env={**os.environ, "PYTHONHASHSEED": hashseed},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                digests.append(hashlib.md5(Path(out).read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1], "ayni komut farkli bank uretti (seed kararsiz)")


if __name__ == "__main__":
    unittest.main()
