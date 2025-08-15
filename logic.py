from __future__ import annotations
import os
import io
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SRC_PATH = os.path.join(DATA_DIR, "npb_stats.csv")
DB_PATH  = os.path.join(DATA_DIR, "records.csv")

NEEDED_COLS = ["Year", "League", "Team", "Games", "Wins", "Losses", "Draws", "WinRate"]

def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def _read_csv_strict(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in NEEDED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSVの列が不足しています: {missing} / 期待: {NEEDED_COLS}")
    return df

def load_source() -> pd.DataFrame:
    """元データを読み込み、型と値域を軽く整える"""
    ensure_dirs()
    df = _read_csv_strict(SRC_PATH).copy()
    df["Year"]   = df["Year"].astype(int)
    for c in ["Games","Wins","Losses","Draws"]:
        df[c] = df[c].astype(int)
    df["WinRate"] = df["WinRate"].astype(float).clip(0, 1)
    return df

def import_uploaded_csv(bytes_obj: bytes) -> pd.DataFrame:
    """アップロードCSVをバリデーションして返す（保存はしない）"""
    with io.BytesIO(bytes_obj) as f:
        df = pd.read_csv(f)
    missing = [c for c in NEEDED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"アップロードCSVの列が不足: {missing}")
    return df

def years(df: pd.DataFrame) -> list[int]:
    return sorted(df["Year"].unique().tolist(), reverse=True)

def leagues(df: pd.DataFrame) -> list[str]:
    return sorted(df["League"].unique().tolist())

def teams(df: pd.DataFrame, year: int | None = None, league: str | None = None) -> list[str]:
    q = df
    if year is not None:   q = q[q["Year"] == year]
    if league:             q = q[q["League"] == league]
    return sorted(q["Team"].unique().tolist())

def filter_table(df: pd.DataFrame, year: int, league: str | None, team: str | None) -> pd.DataFrame:
    q = df[df["Year"] == year].copy()
    if league and league != "全体":
        q = q[q["League"] == league]
    if team and team != "（全チーム）":
        q = q[q["Team"] == team]
    return q.sort_values("WinRate", ascending=False).reset_index(drop=True)

def team_trend(df: pd.DataFrame, team: str) -> pd.DataFrame:
    t = df[df["Team"] == team].copy()
    return t.sort_values("Year").reset_index(drop=True)

def snapshot_to_db(df_view: pd.DataFrame, meta: dict) -> None:
    """画面に出している表をそのままDB(CSV)に追記（加点用）"""
    ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = df_view.copy()
    out.insert(0, "_saved_at", stamp)
    out.insert(1, "_meta", str(meta))
    if os.path.exists(DB_PATH):
        out.to_csv(DB_PATH, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        out.to_csv(DB_PATH, index=False, encoding="utf-8-sig")

def load_db() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    return pd.read_csv(DB_PATH)