# Yarisma hakemi icin SANDBOX image'i.
#
# Solver'lar (ve istenirse generator'lar) bu image icinde, AG KAPALI,
# SALT-OKUNUR dosya sistemi, tum capability'ler dusurulmus ve root olmayan
# kullaniciyla calistirilir. Komutlar arena/sandboxed_solver.py'de.
#
#   1) Build:
#        docker build -t puzzle-arena .
#
#   2) Izolasyon kendin dene (ag/dosya ENGELLI olmali):
#        python3 arena/run_match.py --sandbox docker --max-puzzles 1 \
#            --solver agents_examples.evil_solvers:SnoopSolver --bank bank/test.jsonl
#      stderr'de "AG: ENGELLI", "DOSYA ...: ENGELLI", "YAZMA /app: ENGELLI" gormelisin.
#
#   3) Katilimci solver'i calistir (katilimci klasoru salt-okunur baglanir;
#      PROJE KOKUNU verme, bank/ ve results/ gorunur olur):
#        python3 arena/run_match.py --sandbox docker --submission-dir submissions/takimB \
#            --solver takimb_agent:TakimBSolver --bank bank/tournament/takim_a_bank.jsonl
#
#   4) Katilimci GENERATOR'unu container'da calistir (bank'i container uretir;
#      root basladigi icin generate() worker'i 'nobody'ye duser ve bank dosyasina
#      yazamaz; SETUID/SETGID capability'si bunun icin, KILL capability'si ise
#      takilan worker'i oldurebilmek icin gerekli):
#        mkdir -p out && chmod 777 out
#        docker run --rm --user 0:0 --network none --read-only --tmpfs /tmp:rw,size=256m \
#            --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add DAC_OVERRIDE --cap-add KILL \
#            --security-opt no-new-privileges --pids-limit 256 --memory 4g \
#            -e PYTHONPATH=/submission:/app \
#            --mount type=bind,src="$PWD/submissions/takimA",dst=/submission,readonly \
#            --mount type=bind,src="$PWD/out",dst=/out \
#            puzzle-arena python /app/bank/build_bank.py \
#            --generator takima_agent:TakimAGenerator --out /out/takim_a_bank.jsonl --per-type 500
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY core/ /app/core/
COPY games/ /app/games/
COPY agents_examples/ /app/agents_examples/
COPY bank/build_bank.py /app/bank/build_bank.py
COPY arena/solver_runner.py /app/arena/solver_runner.py
# Katilimcilarin ek paketleri gerekiyorsa buraya ekleyin, ornegin:
# RUN pip install --no-cache-dir numpy
RUN chmod -R a-w /app && chmod -R a+rX /app
USER 65534:65534
