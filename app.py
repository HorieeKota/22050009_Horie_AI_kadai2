import os
from matplotlib import font_manager, rcParams

font_path = os.path.join(os.path.dirname(__file__), "fonts", "IPAexGothic.ttf")  # .ttf名を合わせてください
font_manager.fontManager.addfont(font_path)
rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from logic import (
    load_source, import_uploaded_csv, years, leagues, teams,
    filter_table, team_trend, snapshot_to_db, load_db
)

# ===== 見た目設定 =====
matplotlib.rcParams["font.family"] = ["MS Gothic", "Yu Gothic", "Meiryo", "sans-serif"]
st.set_page_config(page_title="NPB 成績分析アプリ", layout="wide")

st.title("NPB 成績分析アプリ")
st.caption("年度・リーグ・チームでフィルタして、勝率を表とグラフで可視化。必要な結果はCSVに保存できます。")
st.caption("※ データはNPB公式記録を参考に作成したサンプル（架空値を含む）。CSV差し替えで実成績にも即対応。")

# ===== データ読み込み or アップロード =====
src_df = load_source()
with st.expander("🔽 外部CSVの一時読み込み（列: Year,League,Team,Games,Wins,Losses,Draws,WinRate）", expanded=False):
    up = st.file_uploader("npb_stats互換CSVを選択", type=["csv"])
    if up is not None:
        try:
            src_df = import_uploaded_csv(up.read())
            st.success("CSVを一時的に読み込みました（保存はしません / 列名が一致する必要あり）")
        except Exception as e:
            st.error(f"読み込み失敗: {e}")

# ===== サイドバー（入力UI） =====
with st.sidebar:
    st.header("フィルタ")
    y = st.selectbox("年度", years(src_df))
    lg_opts = ["全体"] + leagues(src_df)
    lg = st.selectbox("リーグ", lg_opts, index=0)
    team_opts = ["（全チーム）"] + teams(src_df, y, None if lg == "全体" else lg)
    tm = st.selectbox("チーム", team_opts, index=0)
    show_labels = st.checkbox("棒グラフに数値ラベル", value=True)
    use_percent = st.checkbox("勝率を%表記にする", value=True)
    st.divider()
    if st.button("この一覧をCSVに保存（加点）", use_container_width=True):
        view_for_save = filter_table(src_df, y, lg, tm)
        meta = {"year": y, "league": lg, "team": tm}
        snapshot_to_db(view_for_save, meta)
        st.success("data/records.csv に保存しました。")

# ===== タブ構成 =====
tab1, tab2, tab3 = st.tabs(["📊 概要", "📈 チーム推移", "🗂 履歴/データ"])

# ===== 共通のフィルタ済データ =====
view = filter_table(src_df, y, lg, tm)

# ===== 便利関数 =====
def fmt_rate(val: float, to_percent: bool) -> str:
    return f"{val*100:.1f}%" if to_percent else f"{val:.3f}"

def bar_colors_by_league(series_league: pd.Series):
    # セ＝青系 / パ＝緑系 / 全体混在時も対応
    cmap_se = plt.cm.Blues
    cmap_pa = plt.cm.Greens
    colors = []
    for i, lg in enumerate(series_league):
        if lg == "セ・リーグ":
            colors.append(cmap_se(0.6))
        elif lg == "パ・リーグ":
            colors.append(cmap_pa(0.6))
        else:
            colors.append(plt.cm.Greys(0.6))
    return colors

# ===== タブ1：概要 =====
with tab1:
    # KPIカード
    c1, c2, c3, c4 = st.columns(4)
    avg_rate = (view["WinRate"].mean()) if not view.empty else 0
    max_rate = (view["WinRate"].max()) if not view.empty else 0
    min_rate = (view["WinRate"].min()) if not view.empty else 0
    c1.metric("平均勝率", fmt_rate(avg_rate, use_percent))
    c2.metric("最高勝率", fmt_rate(max_rate, use_percent))
    c3.metric("最低勝率", fmt_rate(min_rate, use_percent))
    c4.metric("表示チーム数", len(view))

    st.markdown("### 成績表（フィルタ適用後・勝率で降順）")
    if use_percent:
        view_show = view.copy()
        view_show["WinRate(%)"] = (view_show["WinRate"] * 100).round(1)
        st.dataframe(
            view_show[["Year","League","Team","Games","Wins","Losses","Draws","WinRate(%)"]],
            use_container_width=True
        )
    else:
        st.dataframe(view, use_container_width=True)

    st.markdown("### 勝率ランキング（バー）")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    colors = bar_colors_by_league(view["League"]) if lg == "全体" else plt.cm.viridis(view["WinRate"])
    bars = ax.bar(view["Team"], view["WinRate"], color=colors, edgecolor="white")

    # ラベル
    if show_labels:
        for b, r in zip(bars, view["WinRate"]):
            ax.text(b.get_x() + b.get_width()/2, r,
                    fmt_rate(r, use_percent),
                    ha="center", va="bottom", fontsize=8)

    ax.set_ylabel("勝率(%)" if use_percent else "勝率")
    ymax = (max(0.8, view["WinRate"].max() + 0.05)) if not view.empty else 1.0
    ax.set_ylim(0, ymax)
    ax.tick_params(axis="x", labelrotation=30, labelsize=8)
    ax.grid(axis="y", alpha=0.2)
    st.pyplot(fig, clear_figure=True)

    # ちょい分析コメント（一言で言える材料）
    if not view.empty:
        top_row = view.iloc[0]
        st.info(
            f"✅ {y}年の{(' ' + lg) if lg != '全体' else ''}で最も高い勝率は "
            f"**{top_row['Team']}**（{fmt_rate(top_row['WinRate'], use_percent)}）。"
        )
    else:
        st.warning("該当データがありません。フィルタ条件を見直してください。")

# ===== タブ2：チーム別 年度推移 =====
with tab2:
    st.subheader("チーム別 勝率の年度推移")
    sel_team = st.selectbox("チームを選択", teams(src_df), index=0, key="trend_team")
    trend = team_trend(src_df, sel_team)

    if trend.empty:
        st.warning("データが見つかりません。")
    else:
        fig2, ax2 = plt.subplots(figsize=(10, 3.8))
        ax2.plot(trend["Year"], trend["WinRate"], marker="o")
        for x, yv in zip(trend["Year"], trend["WinRate"]):
            ax2.text(x, yv, fmt_rate(yv, use_percent), ha="center", va="bottom", fontsize=8)
        ax2.set_xlabel("年度")
        ax2.set_ylabel("勝率(%)" if use_percent else "勝率")
        ax2.set_ylim(0, max(0.8, trend["WinRate"].max() + 0.05))
        ax2.grid(True, alpha=0.3)
        st.pyplot(fig2, clear_figure=True)

        # ひとこと要約
        st.caption(f"→ **{sel_team}** は {trend['Year'].min()}–{trend['Year'].max()} で "
                   f"平均 {fmt_rate(trend['WinRate'].mean(), use_percent)}。")

# ===== タブ3：履歴/データ =====
with tab3:
    st.subheader("保存履歴（records.csv）")
    db = load_db()
    if db is None or db.empty:
        st.info("まだ保存履歴はありません。サイドバーの『この一覧をCSVに保存』を押すと追記されます。")
    else:
        st.dataframe(db, use_container_width=True)
        st.download_button(
            "履歴CSVをダウンロード",
            data=db.to_csv(index=False).encode("utf-8-sig"),
            file_name="records.csv",
            mime="text/csv"
        )

    st.divider()
    st.subheader("現在の元データ（npb_stats.csv）を確認")
    st.dataframe(src_df, use_container_width=True)

