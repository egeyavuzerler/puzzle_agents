# Puzzle Agents Hackathon — Yarışma Kuralları

Bu hackathon'da kendi puzzle **generator**'ınızı (üretici) ve **solver**'ınızı
(çözücü) yazacaksınız. Generator'ınız yeni puzzle'lar üretecek, solver'ınız
başka takımların ürettiği puzzle'ları çözmeye çalışacak. Puanlama tamamen
**ampiriktir** — kendi generator'ınızın "zorluk" beyanına güvenilmez, sadece
gerçek çözülme oranına bakılır.

---

## 1. Genel Kurallar

- 10 farklı oyun türü var (aşağıda tek tek anlatılıyor). Generator'ınız
  **hepsi için** puzzle üretebilmeli, solver'ınız **hepsi için** çözüm
  bulabilmeli.
- Her generator çağrısı bir `(puzzle, solution)` ikilisi döndürmek
  **zorundadır** (bkz. Bölüm 3). `solution`, üretilen puzzle'ın gerçekten
  çözülebilir olduğunun kanıtıdır (witness). Bu kanıt doğrulanamazsa puzzle
  havuza (bank) **hiç girmez** — yani çözülemez bir puzzle üretmek size hiçbir
  avantaj sağlamaz, tam tersine o puzzle diskalifiye edilir.
- Solver'lar **izole ve limitli process'lerde** çalıştırılır: bellek limiti,
  CPU süresi limiti ve sert bir duvar-saati timeout'u uygulanır. Sonsuz
  döngüye giren ya da belleği dolduran bir solver, sizi diskalifiye etmez —
  sadece o puzzle "çözülemedi" sayılır.
- Skor: solver'ınızın, diğer takımların havuzlarındaki puzzle'ların kaçını
  gerçekten çözebildiği (oyun türü bazlı ve genel oran).

---

## 2. Oyunlar

### Zip
10x10 ızgarada, numaralı checkpoint'leri **sırayla** bağlayan ve ızgaranın
**her hücresinden tam 1 kez geçen** tek bir yol (Hamiltonian path) bulun. Yol
ilk checkpoint'te başlar, son checkpoint'te biter.

**Hareket ettirilemez bloklar (opsiyonel kural):** Generator'ınız isterseniz
10x10 ızgarada **en fazla 4 tane** "blocked_cell" (hareket ettirilemez blok —
yoldan geçilemeyen hücre) yerleştirebilir. Bu **zorunlu değildir** — hiç blok
kullanmadan da geçerli Zip puzzle'ları üretebilirsiniz. Blok kullanırsanız,
yolunuzun (witness solution) o hücrelerden geçmediğinden emin olun; blok
yerleşiminiz ızgarayı iki parçaya bölerse (bağlı olmayan bir alan
yaratırsanız) puzzle zaten çözülemez hale gelir ve reddedilir.

### Queens
Her satırda, her sütunda ve her renkli bölgede **tam 1 kraliçe** olacak
şekilde yerleştirin. İki kraliçe, çapraz dahil, birbirine **komşu olamaz**.

### Tango
Her (bloklu olmayan) hücreyi güneş/ay ile doldurun. Her satır/sütunda
(bloklu hariç, serbest hücreler arasında) **eşit sayıda** güneş/ay olmalı, 3
hücre art arda **aynı sembol olamaz**. Bazı hücre çiftlerinde "eşit" / "zıt"
kısıtı olabilir. Bazı hücreler dokunulmaz (bloklu) olabilir, bazı hücreler
baştan verilmiş ipucu (prefilled) olabilir.

### Patches (Shikaku)
Izgarayı dikdörtgenlere bölün. Her dikdörtgen **tam 1 clue** (alan + şekil
kısıtı: kare / yatay / dikey / serbest) içermeli, clue'nun belirttiği alanı
kaplamalı. Boşluk yok, çakışma yok, tüm ızgara kaplanmalı.

### Slitherlink
Nokta ızgarası üzerinde **tek bir kapalı döngü** (loop) çizin. Her noktanın
derecesi 0 ya da 2 olmalı, döngü tek parça (bağlı) olmalı, her ipuçlu
hücrenin etrafındaki döngü-kenarı sayısı ipucuyla eşleşmeli.

### Numberlink (Flow varyantı)
Aynı renkli iki uç noktayı, **kendine değmeyen** basit bir yolla birleştirin.
Farklı renklerin hücreleri birbirine komşu olabilir. Izgaranın her hücresinin
dolu olması **şart değil** (Flow varyantı, klasik Numberlink'ten farklı
olarak bazı hücreler boş kalabilir).

**Portal (opsiyonel kural):** Generator'ınız isterseniz birbirine
"ışınlanma" ile bağlı **hücre çiftleri** (portal) yerleştirebilir. Bir
rengin yolu, bu iki hücreyi **fiziksel komşuluk olmadan** ardışık olarak
kullanabilir — yani yol bu noktada "atlar". Bu **zorunlu değildir** — hiç
portal kullanmadan da geçerli Numberlink puzzle'ları üretebilirsiniz.
Portal kullanırsanız, witness çözümünüzde bu iki hücrenin gerçekten
ardışık olarak (yolun bir parçası olarak) kullanıldığından emin olun;
sadece "aynı renk" olmaları yeterli değildir, aralarında **fiziksel komşuluk
olmaması ve path içinde ardışık olmaları** gerekir.

### Hashiwokakero (Bridges)
Numaralı adaları yatay/dikey köprülerle (1 ya da 2 telli) bağlayın:
köprüler yalnızca aynı satır/sütundaki, arada başka ada olmayan iki ada
arasında olabilir; bir bağlantıda en fazla 2 köprü olabilir; köprüler
birbirini kesemez; her adanın üzerindeki köprü sayısı toplamı adanın
değerine eşit olmalı; **tüm adalar** köprüler aracılığıyla tek bir bağlı ağ
oluşturmalı.

### LITS
Her bölgede **tam 4 hücreyi** gölgeleyin; gölgelenen 4 hücre L, I, T ya da S
tetromino şekillerinden birini oluşturmalı (dönüşler ve yansımalar serbest).
Tüm gölgeli hücreler tek bir bağlı bütün oluşturmalı, hiçbir 2x2 alan
tamamen gölgeli olamaz, birbirine komşu iki tetromino aynı tipte olamaz.

**Zorunlu hücre (opsiyonel kural):** Generator'ınız isterseniz belirli
hücreleri "kesinlikle gölgeli olmak zorunda" (`forced_shaded`) diye
işaretleyebilir. Hangi tetrominoya ait olduğu ya da tetrominonun tipi
**söylenmez** — sadece o hücrenin çözümde mutlaka gölgeli olması gerektiği
belirtilir. Bu **zorunlu değildir** — hiç zorunlu hücre kullanmadan da
geçerli LITS puzzle'ları üretebilirsiniz. Kullanırsanız, witness
çözümünüzün bu hücreleri gerçekten gölgelediğinden emin olun.

### Yin-Yang
Tüm hücreleri siyah/beyaz boyayın: tüm siyah hücreler kendi aralarında bağlı
olmalı, tüm beyaz hücreler kendi aralarında bağlı olmalı (**ikisi aynı
anda**), hiçbir 2x2 alan tek renk olamaz.

*(Not: Yin-Yang şu an sabit 5x5 ızgarada üretiliyor — 6x6 ve üzeri, üretim
algoritmasının kombinatorik olarak tıkanması sebebiyle henüz desteklenmiyor.)*

### Tapa
Bazı hücrelerde bir ya da birden fazla sayı var (bu hücreler asla
boyanmaz); sayılar, çevresindeki (en fazla 8) komşuda **saat yönünde
ardışık** boyalı blokların uzunluklarını gösteriyor. Tüm boyalı hücreler tek
bağlı bütün oluşturmalı, hiçbir 2x2 alan tamamen boyalı olamaz.

---

## 3. Generator / Solver Sözleşmesi

Kendi generator ve solver'ınızı `BaseGeneratorAgent` / `BaseSolverAgent`'tan
miras alarak yazacaksınız:

```python
from core.base import BaseGeneratorAgent, BaseSolverAgent, SolveResult

class MyGenerator(BaseGeneratorAgent):
    name = "takim_x_generator"

    def generate(self, game: str, difficulty: int, seed: int | None = None):
        ...  # game: "zip", "queens", "tango", "patches", "slitherlink",
             #       "numberlink", "hashi", "lits", "yinyang", "tapa"
        return puzzle, solution   # ZORUNLU: ikili donus (bkz. asagida)

class MySolver(BaseSolverAgent):
    name = "takim_x_solver"

    def solve(self, puzzle: dict, time_limit_s: float = 30.0) -> SolveResult:
        ...
```

**`generate()` neden `(puzzle, solution)` döndürmek zorunda?** `solution`,
ürettiğiniz puzzle'ın en az bir geçerli çözümü olduğunun kanıtıdır (witness).
Puzzle'ınız havuza girmeden önce iki kontrolden geçer:

1. **Şekil kontrolü** — puzzle kurallara uygun mu (bkz. Bölüm 2'deki oyun
   şemaları, `games/<oyun>/validator.py`'de tam olarak yazıyor)
2. **Çözüm kontrolü** — verdiğiniz `solution`, gerçekten bu puzzle'ı çözüyor
   mu

İkisinden biri bile başarısız olursa puzzle'ınız **reddedilir**, havuza
girmez. Bu, kasıtlı ya da kazara çözülemez bir puzzle üretip solver'ları
haksız yere elemenizi (ve "zorluk" adı altında tam puan almanızı) engeller.

---

## 4. Kendi Ortamınızda Test Etme

**Kurulum:**
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install matplotlib
```

**Generator'ınızı test edin — kendi puzzle havuzunuzu üretin:**
```bash
python3 bank/build_bank.py \
    --generator agents_examples.baseline:BaselineGenerator \
    --out bank/takim_x_bank.jsonl \
    --per-type 500
```
(`agents_examples.baseline:BaselineGenerator` yerine kendi
`modul_yolu:SinifAdi`'nızı yazın. Test için `--per-type 5` gibi küçük bir
sayı kullanabilirsiniz, hızlı sonuç alırsınız.)

Çıktıda her oyun için `ok` / `failed_shape` / `failed_solution` sayılarını
göreceksiniz — `failed_solution` sayısı yüksekse generator'ınız çözülemez
puzzle'lar üretiyor demektir, bunu düzeltmeniz gerekir.

**Solver'ınızı test edin — kendi havuzunuza karşı koşturun:**
```bash
python3 arena/run_match.py \
    --solver agents_examples.baseline:BaselineSolver \
    --bank bank/takim_x_bank.jsonl \
    --time-limit 10 \
    --hard-timeout 15 \
    --memory-mb 1024 \
    --cpu-seconds 60 \
    --out results/takim_x_solver_test.json
```
Çıktı: kaç puzzle çözüldü, oyun türü bazlı çözüm oranı, ortalama süre.

**Solver'ınızı canlı izleyin (adım adım nasıl çözdüğünü görün):**
```bash
python3 arena/run_live.py --game zip --size 6
python3 arena/run_live.py --game queens --size 8
python3 arena/run_live.py --game tango --difficulty 5
# diğer oyunlar icin: patches, slitherlink, numberlink, hashi, lits, yinyang, tapa

# kendi havuzunuzdan belirli bir puzzle'ı izlemek icin:
python3 arena/run_live.py --game zip --from-bank bank/takim_x_bank.jsonl --puzzle-id 0
```
Bir matplotlib penceresi açılır, solver adım attıkça (checkpoint'e basma,
çıkmaz sokağa girip geri sarma dahil) canlı günceller.

**Statik görsel kontrol (opsiyonel):**
```python
from core.visualize import render_zip, render_queens
render_zip(puzzle_dict, solution_list_or_None, "cikti.png")
render_queens(puzzle_dict, solution_list_or_None, "cikti.png")
```
