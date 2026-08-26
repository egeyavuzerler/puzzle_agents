# Puzzle Agents Hackathon — Kurulum ve Kullanım

## Klasör yapısı
```
core/base.py            -> BaseGeneratorAgent / BaseSolverAgent (HERKESİN miras alacağı sözleşme)
core/validator.py       -> hakem arayüzü (sabit, katılımcı dokunmaz)
core/registry.py        -> oyun türü -> hakem eşlemesi
core/visualize.py       -> puzzle/çözümü PNG olarak çizer
games/zip/validator.py      -> Zip oyunu kuralları (blocked_cells destekli)
games/queens/validator.py   -> Queens oyunu kuralları
agents_examples/baseline.py -> örnek/referans generator + solver (siz böyle bir dosya yazacaksınız)
agents_examples/evil_solvers.py -> güvenlik testi için kötü niyetli örnek solver'lar
bank/build_bank.py      -> bir generator'dan N tür x 500 = 10.000'lik puzzle havuzu üretir
arena/run_match.py      -> bir solver'ı bir havuza karşı, izole+limitli process'lerde koşturur
demo_visualize.py       -> örnek görselleştirme scripti
```

## Kurulum
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install matplotlib
```
Ekstra bağımlılık yok, sadece görselleştirme için matplotlib gerekiyor.

## Katılımcı olarak ne yazacaksınız?
`agents_examples/baseline.py` dosyasına bakıp aynı desende kendi dosyanızı yazın:

```python
from core.base import BaseGeneratorAgent, BaseSolverAgent, SolveResult

class MyGenerator(BaseGeneratorAgent):
    name = "takim_x_generator"
    def generate(self, game: str, difficulty: int, seed: int | None = None) -> dict:
        ...  # game == "zip" veya "queens" (ileride daha fazla tür)

class MySolver(BaseSolverAgent):
    name = "takim_x_solver"
    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        ...
```

## 1. Adım: kendi 10.000'lik havuzunuzu üretin
```bash
python3 bank/build_bank.py \
    --generator agents_examples.baseline:BaselineGenerator \
    --out bank/takim_x_bank.jsonl \
    --per-type 500
```
(Test için `--per-type 5` gibi küçük bir sayı kullanabilirsiniz, hızlı sonuç alırsınız.)

## 2. Adım: bir solver'ı bir havuza karşı koşturun
```bash
python3 arena/run_match.py \
    --solver agents_examples.baseline:BaselineSolver \
    --bank bank/takim_x_bank.jsonl \
    --time-limit 10 \
    --hard-timeout 15 \
    --memory-mb 1024 \
    --cpu-seconds 60 \
    --out results/takimY_solver_vs_takimX_bank.json
```
Çıktı: kaç puzzle çözüldü, oyun türü bazlı çözüm oranı, ortalama süre.

**Güvenlik notu:** her puzzle çözümü ayrı process'te, sert bellek (`--memory-mb`)
ve CPU süresi (`--cpu-seconds`) limitleriyle çalışır. Sonsuz döngüye giren ya
da RAM'i dolduran bir solver turnuvayı kilitlemez, sadece o puzzle
"çözülemedi" sayılır. Bunu `agents_examples/evil_solvers.py` ile test edebilirsiniz:
```bash
python3 arena/run_match.py --solver agents_examples.evil_solvers:InfiniteLoopSolver \
    --bank bank/takim_x_bank.jsonl --cpu-seconds 3 --hard-timeout 6 --max-puzzles 2
```

## 3. Adım: solver'ı CANLI izle (asıl istediğin bu)
```bash
# küçük bir Zip puzzle üret, baseline solver'ı ekranda canlı izle
python3 arena/run_live.py --game zip --size 6

# 10x10 -- daha zor, daha seyrek yenile (yoksa pencere çok yavaşlar)
python3 arena/run_live.py --game zip --size 10 --n-checkpoints 5 --redraw-every 500

# Queens'i canlı izle (her adımda 1 kraliçe yerleştiği için redraw-every=1 zaten hızlı)
python3 arena/run_live.py --game queens --size 8

# bank'tan belirli bir puzzle'ı izle
python3 arena/run_live.py --game zip --from-bank bank/test_bank.jsonl --puzzle-id 0
```
Bu komut GIF/video DOSYASI ÜRETMEZ -- çalıştığın anda bir matplotlib penceresi
açar ve solver adım attıkça (checkpoint'e basma, çıkmaz sokağa girip geri
sarma dahil) canlı günceller. Pencere solver bitince açık kalır, kapatana
kadar sonucu gösterir.

**`--redraw-every` ayarı önemli:** solver on binlerce "adım" atabiliyor
(özellikle 10x10'da), her birini çizmek pencereyi kilitler. Küçük grid'lerde
(6x6) `25` gibi bir değer akıcı görünür; 10x10'da `300-1000` arası dene,
istersen yükselt/düşür. `--pause` ise her karede ne kadar bekleneceğini
kontrol eder (0.001 = çok hızlı, 0.05 = daha izlenebilir).

## 4. Adım: statik görsel kontrol (opsiyonel)
```bash
python3 demo_visualize.py
```
`demo_out/` klasörüne PNG'ler yazar (çözümsüz ve çözümlü hallerini gösterir).
Kendi puzzle/çözümünüzü çizmek için:
```python
from core.visualize import render_zip, render_queens
render_zip(puzzle_dict, solution_list_or_None, "cikti.png")
render_queens(puzzle_dict, solution_list_or_None, "cikti.png")
```

## Turnuva organizatörü olarak (sen) sırada ne var
- Round-robin: her takımın havuzunu her takımın solver'ına karşı koşturup
  bir leaderboard matrisi oluşturmak (N generator x N solver) — bunu bir
  sonraki adımda yazabiliriz.
- Görsel leaderboard / turnuva sonu demo ekranı — `core/visualize.py`
  bunun temeli, üzerine bir HTML/dashboard eklenebilir.
- 20 oyun türüne çıkarken: her yeni oyun için `games/<isim>/validator.py`
  yazıp `core/registry.py`'a 2 satır eklemek yeterli.
