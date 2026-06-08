"""Génère data/seed_monthly_closes.csv depuis Coin Metrics community data.

Clôture mensuelle = dernier point journalier d'un mois CIVIL CLOS (Synchro §4.4).
Source : github.com/coinmetrics/data (tier Community, licence Creative Commons).
Usage : python scripts/generate_seed.py
"""
import csv, io, sys, urllib.request
from datetime import date

SRC = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"
OUT = "data/seed_monthly_closes.csv"

def main(out_path=OUT):
    print(f"Téléchargement {SRC} …", file=sys.stderr)
    raw = urllib.request.urlopen(SRC, timeout=60).read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))

    monthly = {}  # 'YYYY-MM' -> price (dernier jour du mois ; CSV trié chrono)
    for row in reader:
        t, p = row.get("time", "").strip(), row.get("PriceUSD", "").strip()
        if not t or not p:
            continue
        try:
            monthly[t[:7]] = float(p)
        except ValueError:
            continue

    today = date.today()
    current = f"{today.year:04d}-{today.month:02d}"
    closed = {m: v for m, v in monthly.items() if m < current}  # exclut mois courant
    months = sorted(closed)

    # contrôle d'intégrité : trous
    gaps = []
    for i in range(1, len(months)):
        y0, m0 = map(int, months[i-1].split("-"))
        y1, m1 = map(int, months[i].split("-"))
        if (y1*12 + m1) != (y0*12 + m0) + 1:
            gaps.append((months[i-1], months[i]))
    if gaps:
        print(f"⚠ {len(gaps)} trou(s) : {gaps[:5]}", file=sys.stderr)

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "price"])
        for m in months:
            w.writerow([m, f"{closed[m]:.10g}"])

    print(f"✓ {len(months)} mois — {months[0]} → {months[-1]} → {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUT)
