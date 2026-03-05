"""
MOVE Index Dashboard - Data Collector
Collects: MOVE, VIX, TLT, DXY via yfinance
Merges with: SPY, BTC, USO, GLD from CSV
Output: data/move_dashboard.json
"""

import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────────────────────────────
YFINANCE_TICKERS = {
    "MOVE": "^MOVE",
    "VIX":  "^VIX",
    "TLT":  "TLT",
    "DXY":  "DX-Y.NYB",
}

CSV_FILES = {
    "SPY": "data/SPY.csv",
    "BTC": "data/BTC_USD.csv",
    "USO": "data/USO.csv",
    "GLD": "data/GLD.csv",
}

START_DATE = "2000-01-01"
OUTPUT_PATH = "data/move_dashboard.json"

# ── yfinance 수집 ──────────────────────────────────────────────────────────────
def fetch_yfinance():
    result = {}
    for name, ticker in YFINANCE_TICKERS.items():
        try:
            df = yf.download(ticker, start=START_DATE, auto_adjust=True, progress=False)
            df = df[["Close"]].dropna()
            df.index = pd.to_datetime(df.index)
            df.index = df.index.tz_localize(None)
            df.columns = [name]
            result[name] = df
            print(f"  ✅ {name} ({ticker}): {len(df)} rows")
        except Exception as e:
            print(f"  ❌ {name} ({ticker}): {e}")
    return result

# ── CSV 로드 ───────────────────────────────────────────────────────────────────
def load_csvs():
    result = {}
    for name, path in CSV_FILES.items():
        try:
            df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
            df = df[["Close"]].dropna()
            df.index = pd.to_datetime(df.index)
            df.index = df.index.tz_localize(None)
            df.columns = [name]
            result[name] = df
            print(f"  ✅ {name} (CSV): {len(df)} rows")
        except Exception as e:
            print(f"  ❌ {name} (CSV): {e}")
    return result

# ── 직렬화 헬퍼 ───────────────────────────────────────────────────────────────
def to_series(df, col):
    """DataFrame 컬럼 → [[timestamp_ms, value], ...] 리스트"""
    series = df[col].dropna()
    return [
        [int(ts.timestamp() * 1000), round(float(v), 4)]
        for ts, v in series.items()
    ]

# ── Z-Score 계산 (rolling 252일) ──────────────────────────────────────────────
def compute_zscore(series_df, col, window=252):
    s = series_df[col]
    mean = s.rolling(window).mean()
    std  = s.rolling(window).std()
    z    = (s - mean) / std
    return pd.DataFrame({col: z}, index=series_df.index)

# ── MOVE 위기 구간 ─────────────────────────────────────────────────────────────
CRISIS_ZONES = [
    {"label": "금융위기",      "start": "2008-09-01", "end": "2009-03-31", "color": "rgba(255,80,80,0.12)"},
    {"label": "코로나 충격",   "start": "2020-02-15", "end": "2020-05-31", "color": "rgba(255,140,0,0.12)"},
    {"label": "Fed 긴축",      "start": "2022-01-01", "end": "2023-06-30", "color": "rgba(255,200,0,0.12)"},
]

# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs("data", exist_ok=True)
    print("📡 yfinance 수집 중...")
    yf_data = fetch_yfinance()

    print("📂 CSV 로드 중...")
    csv_data = load_csvs()

    all_data = {**yf_data, **csv_data}

    # MOVE Z-Score
    move_z = None
    if "MOVE" in all_data:
        move_z = compute_zscore(all_data["MOVE"], "MOVE")

    output = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "crisis_zones": CRISIS_ZONES,
        "series": {},
    }

    for name, df in all_data.items():
        output["series"][name] = to_series(df, name)
        print(f"  📊 {name}: {len(output['series'][name])} points")

    if move_z is not None:
        output["series"]["MOVE_Z"] = to_series(move_z, "MOVE")
        print(f"  📊 MOVE_Z: {len(output['series']['MOVE_Z'])} points")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n✅ 저장 완료: {OUTPUT_PATH} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    main()
