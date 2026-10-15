from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

for i in range(1, 4):
    subprocess.run([sys.executable, str(ROOT / "run.py")], check=True)
    (OUT / f"run_{i}.csv").write_bytes((OUT / "results.csv").read_bytes())

hashes = {}
for i in range(1, 4):
    p = OUT / f"run_{i}.csv"
    hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()

print("Run SHA256 hashes:")
for name, digest in hashes.items():
    print(f"{name}: {digest}")
print("IDENTICAL" if len(set(hashes.values())) == 1 else "MISMATCH")
if len(set(hashes.values())) != 1:
    raise SystemExit(1)
(OUT / "reproducibility_report.txt").write_text(
    "Three runs produced byte-identical CSV outputs.\n" +
    "\n".join(f"{name}: {digest}" for name, digest in hashes.items()) + "\n",
    encoding="utf-8",
)
