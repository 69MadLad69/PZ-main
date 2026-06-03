from __future__ import annotations

import logging
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

C = dict(
    day     = "#2E75B6",
    night   = "#8FAADC",
    weekday = "#2E75B6",
    weekend = "#1F8B8B",
    peak    = "#E74C3C",
    avg     = "#27AE60",
    solar   = "#F39C12",
    battery = "#8E44AD",
    grid    = "#95A5A6",
    norm    = "#E67E22",
    anom_pos= "#E74C3C",
    anom_neg= "#3498DB",
    text    = "#2C3E50",
    grid_ln = "#DDDDDD",
)

MONTHS_UA = ["Січ","Лют","Бер","Кві","Тра","Чер",
             "Лип","Сер","Вер","Жов","Лис","Гру"]

plt.rcParams.update({
    "font.family"      : "DejaVu Sans",
    "axes.grid"        : True,
    "grid.alpha"       : 0.3,
    "grid.linestyle"   : "--",
    "axes.spines.top"  : False,
    "axes.spines.right": False,
    "figure.dpi"       : 150,
})

def _save(fig: plt.Figure, path: str) -> None:
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Chart → %s", path)


def _subtitle(ax: plt.Axes, text: str) -> None:
    ax.set_title(text, fontsize=11, fontweight="bold", color=C["text"], pad=10)


def _fmt_kwh(ax: plt.Axes, axis: str = "y") -> None:
    fmt = mticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)

def save_all(
    reports_dir: str,
    dfs: dict,
    area_m2: float = 850.0,
    object_name: str = "Поліклініка Київ",
) -> None:
    os.makedirs(reports_dir, exist_ok=True)
    fns = [
        (_chart_daily, "fig_01_daily.png", dfs.get("daily"), dict(area_m2=area_m2, obj=object_name)),
        (_chart_monthly, "fig_02_monthly.png", dfs.get("monthly"), dict(obj=object_name)),
        (_chart_tariff, "fig_03_tariff.png", dfs.get("tariff"), {}),
        (_chart_specific, "fig_04_specific.png", dfs.get("specific"), dict(area_m2=area_m2)),
        (_chart_hourly, "fig_05_hourly_profile.png", dfs.get("hourly"), dict(obj=object_name)),
        (_chart_load_factor,  "fig_06_load_factor.png", dfs.get("load_factor"), {}),
        (_chart_anomalies, "fig_07_anomalies.png", dfs.get("anomalies"),   {}),
        (_chart_solar, "fig_08_solar_balance.png", dfs.get("solar"),       {}),
    ]
    for fn, fname, df, kwargs in fns:
        if df is None or df.empty:
            logger.warning("Skipping %s — no data", fname)
            continue
        try:
            fn(df, os.path.join(reports_dir, fname), **kwargs)
        except Exception as exc:
            logger.error("Failed %s: %s", fname, exc)

def _chart_daily(df: pd.DataFrame, path: str, area_m2: float, obj: str) -> None:
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day")

    fig, ax = plt.subplots(figsize=(14, 4.5))

    ax.fill_between(df["day"], df["total_kwh"], alpha=0.10, color=C["day"])
    ax.plot(df["day"], df["total_kwh"],
            color=C["day"], lw=0.9, alpha=0.55, label="Добове споживання")

    rolling = df.set_index("day")["total_kwh"].rolling("7D").mean()
    ax.plot(rolling.index, rolling.values,
            color=C["peak"], lw=2.0, label="Ковзне середнє (7 днів)", zorder=3)

    for m in range(1, 13):
        x = pd.Timestamp(f"2025-{m:02d}-01")
        ax.axvline(x, color=C["grid_ln"], lw=0.7, zorder=1)
        mid = pd.Timestamp(f"2025-{m:02d}-15")
        ax.text(mid, ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 0,
                MONTHS_UA[m-1], ha="center", fontsize=7.5,
                color="#888", va="bottom")

    i_max = df["total_kwh"].idxmax()
    i_min = df["total_kwh"].idxmin()
    for idx, label, color in [(i_max, "Макс", C["peak"]),
                               (i_min, "Мін",  C["avg"])]:
        ax.annotate(
            f"{label}: {df.loc[idx,'total_kwh']:.0f} кВт·год",
            xy=(df.loc[idx, "day"], df.loc[idx, "total_kwh"]),
            xytext=(0, 16 if label == "Макс" else -28),
            textcoords="offset points",
            ha="center", fontsize=7.8, color=color,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        )

    ax.set_ylabel("кВт·год / добу")
    ax.legend(fontsize=9, loc="upper right")
    _fmt_kwh(ax)
    _subtitle(ax, f"Добове споживання електроенергії — 2025 рік\n{obj}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    _save(fig, path)


def _chart_monthly(df: pd.DataFrame, path: str, obj: str) -> None:
    df = df.copy().sort_values("month")
    x  = np.arange(len(df))
    w  = 0.62

    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                             gridspec_kw={"width_ratios": [3, 1]})
    ax, ax2 = axes

    b1 = ax.bar(x, df["night_kwh"], w, label="Нічна зона (5,60 грн)",
                color=C["night"], edgecolor="white", linewidth=0.5)
    b2 = ax.bar(x, df["day_kwh"],   w, bottom=df["night_kwh"],
                label="Денна зона (6,90 грн)",
                color=C["day"],   edgecolor="white", linewidth=0.5)

    totals = df["day_kwh"] + df["night_kwh"]
    for i, v in enumerate(totals):
        ax.text(i, v + totals.max() * 0.015, f"{v:,.0f}",
                ha="center", fontsize=7.2, color=C["text"], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([MONTHS_UA[int(m)-1] for m in df["month"]])
    ax.set_ylabel("кВт·год")
    ax.legend(fontsize=9)
    _fmt_kwh(ax)
    _subtitle(ax, f"Місячне споживання — {obj}")

    ax2.bar(x, df["total_cost_uah"] / 1000, 0.62,
            color=C["avg"], alpha=0.8, edgecolor="white")
    ax2.set_xticks(x)
    ax2.set_xticklabels([MONTHS_UA[int(m)-1] for m in df["month"]], fontsize=8)
    ax2.set_ylabel("Вартість, тис. грн")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}к"))
    _subtitle(ax2, "Вартість")

    plt.tight_layout()
    _save(fig, path)


def _chart_tariff(df: pd.DataFrame, path: str) -> None:
    day_row = df[df["tariff_zone"] == "day"].iloc[0]
    night_row = df[df["tariff_zone"] == "night"].iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    pairs = [
        (axes[0], [day_row["total_kwh"], night_row["total_kwh"]],
         "Споживання, кВт·год",
         f"{day_row['total_kwh']:,.0f} + {night_row['total_kwh']:,.0f}"),
        (axes[1], [day_row["total_uah"], night_row["total_uah"]],
         "Вартість, грн",
         f"{day_row['total_uah']:,.0f} + {night_row['total_uah']:,.0f}"),
    ]
    labels = ["Денна зона\n(07:00–23:00)", "Нічна зона\n(23:00–07:00)"]
    colors = [C["day"], C["night"]]

    for ax, vals, title, total_str in pairs:
        wedges, _, autotexts = ax.pie(
            vals, labels=labels, colors=colors,
            autopct="%1.1f%%", startangle=90,
            pctdistance=0.75,
            wedgeprops=dict(width=0.52, edgecolor="white", linewidth=2),
        )
        for at in autotexts:
            at.set_fontsize(11)
            at.set_fontweight("bold")
            at.set_color("white")
        ax.set_title(f"{title}\n{total_str}", fontsize=9.5, fontweight="bold",
                     color=C["text"])

    fig.suptitle("Розподіл споживання та витрат за тарифними зонами — 2025 рік",
                 fontsize=11, fontweight="bold", color=C["text"], y=1.02)
    plt.tight_layout()
    _save(fig, path)


def _chart_specific(df: pd.DataFrame, path: str, area_m2: float) -> None:
    df  = df.copy().sort_values("month")
    x   = np.arange(len(df))
    vals = df["kwh_per_m2"].values
    annual = vals.sum()

    colors = [C["peak"] if v > 150/12 else C["day"] if v > 130/12 else C["avg"]
              for v in vals]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x, vals, 0.6, color=colors, edgecolor="white", linewidth=0.5)

    for i, v in enumerate(vals):
        ax.text(i, v + 0.08, f"{v:.2f}", ha="center", fontsize=7.5, color=C["text"])

    ax.axhline(annual / 12, color=C["day"], linestyle="--", lw=1.5,
               label=f"Середнє ({annual/12:.1f} кВт·год/м²/міс)")
    ax.axhline(150/12, color=C["norm"], linestyle=":",  lw=1.5,
               label="Норматив 150 кВт·год/м²·рік (÷12)")
    ax.axhline(200/12, color=C["peak"], linestyle=":",  lw=1.0, alpha=0.5,
               label="Норматив 200 кВт·год/м²·рік (÷12)")

    ax.set_xticks(x)
    ax.set_xticklabels([MONTHS_UA[int(m)-1] for m in df["month"]])
    ax.set_ylabel("кВт·год / м²")
    ax.legend(fontsize=8.5, loc="upper right")
    _subtitle(ax,
        f"Питоме споживання електроенергії — 2025 рік\n"
        f"Річний підсумок: {annual:.1f} кВт·год/м²  (норматив: 150–200)")
    _save(fig, path)


def _chart_hourly(df: pd.DataFrame, path: str, obj: str) -> None:
    wd = df[df["day_type"] == "weekday"].sort_values("hour")
    we = df[df["day_type"] == "weekend"].sort_values("hour")
    h  = list(range(24))

    fig, ax = plt.subplots(figsize=(13, 5))

    ax.fill_between(wd["hour"], wd["min_kw"], wd["max_kw"],
                    alpha=0.10, color=C["weekday"])
    ax.fill_between(we["hour"], we["min_kw"], we["max_kw"],
                    alpha=0.10, color=C["weekend"])

    ax.plot(wd["hour"], wd["avg_kw"], "o-", color=C["weekday"],
            lw=2.2, markersize=5, label="Будній день (середнє)")
    ax.plot(we["hour"], we["avg_kw"], "s--", color=C["weekend"],
            lw=2.2, markersize=5, label="Вихідний день (середнє)")

    ax.axvspan(8, 20, alpha=0.05, color=C["avg"], zorder=0)
    ax.axvline(8,  color=C["avg"], linestyle=":", lw=1.2, alpha=0.6)
    ax.axvline(20, color=C["avg"], linestyle=":", lw=1.2, alpha=0.6)
    ax.text(14, ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 0.5,
            "Робочі години  8:00 – 20:00", ha="center",
            fontsize=8, color=C["avg"], alpha=0.85)

    i_pk = wd["avg_kw"].idxmax()
    ax.annotate(
        f"Пік будній: {wd.loc[i_pk,'avg_kw']:.1f} кВт",
        xy=(wd.loc[i_pk, "hour"], wd.loc[i_pk, "avg_kw"]),
        xytext=(0, 14), textcoords="offset points",
        ha="center", fontsize=8, color=C["peak"],
        arrowprops=dict(arrowstyle="->", color=C["peak"], lw=0.9),
    )

    ax.set_xticks(h)
    ax.set_xticklabels([f"{hh:02d}:00" for hh in h], rotation=45, fontsize=7.5)
    ax.set_xlabel("Година доби")
    ax.set_ylabel("Середнє навантаження, кВт")
    ax.legend(fontsize=9.5, loc="upper left")
    _subtitle(ax, f"Середній погодинний профіль навантаження — 2025 рік\n{obj}")
    _save(fig, path)


def _chart_load_factor(df: pd.DataFrame, path: str) -> None:
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day").dropna(subset=["load_factor"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

    ax1.fill_between(df["day"], df["load_factor"], alpha=0.15, color=C["avg"])
    ax1.plot(df["day"], df["load_factor"], color=C["avg"], lw=0.9)
    mean_lf = df["load_factor"].mean()
    ax1.axhline(mean_lf, color=C["peak"], linestyle="--", lw=1.5,
                label=f"Середнє = {mean_lf:.3f}")
    ax1.set_ylabel("Коефіцієнт навантаження")
    ax1.set_ylim(0, 1.05)
    ax1.legend(fontsize=9)
    _subtitle(ax1, "Коефіцієнт навантаження та відношення пік/середнє — 2025 рік")

    ax2.fill_between(df["day"], df["peak_to_avg"], alpha=0.15, color=C["day"])
    ax2.plot(df["day"], df["peak_to_avg"], color=C["day"], lw=0.9)
    ax2.axhline(df["peak_to_avg"].mean(), color=C["norm"], linestyle="--", lw=1.5,
                label=f"Середнє = {df['peak_to_avg'].mean():.2f}")
    ax2.set_ylabel("Пік / Середнє")
    ax2.legend(fontsize=9)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.tight_layout()
    _save(fig, path)


def _chart_anomalies(df: pd.DataFrame, path: str) -> None:
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df["datetime"] = df["day"] + pd.to_timedelta(df["hour"].astype(int), unit="h")
    df = df.sort_values("datetime")

    fig, ax = plt.subplots(figsize=(14, 4.5))

    pos = df[df["deviation_pct"] > 0]
    neg = df[df["deviation_pct"] < 0]

    ax.scatter(pos["datetime"], pos["deviation_pct"],
               color=C["anom_pos"], s=30, alpha=0.75, label="Перевищення (+)", zorder=3)
    ax.scatter(neg["datetime"], neg["deviation_pct"],
               color=C["anom_neg"], s=30, alpha=0.75, label="Недоспоживання (−)", zorder=3)

    ax.axhline(20, color=C["anom_pos"], linestyle=":", lw=1.2, alpha=0.6)
    ax.axhline(-20, color=C["anom_neg"], linestyle=":", lw=1.2, alpha=0.6)
    ax.axhline(0, color="#AAAAAA", linestyle="-", lw=0.8)
    ax.fill_between(df["datetime"], -20, 20, alpha=0.04, color="#AAAAAA")
    ax.text(df["datetime"].iloc[-1], 20.5, "Поріг +20%",
            ha="right", fontsize=7.5, color=C["anom_pos"])
    ax.text(df["datetime"].iloc[-1], -21.5, "Поріг −20%",
            ha="right", fontsize=7.5, color=C["anom_neg"])

    ax.set_ylabel("Відхилення від базової лінії, %")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    _subtitle(ax,
        f"Аномальні години — відхилення >20% від базової лінії (всього: {len(df)})\n"
        "2025 рік, Поліклініка Київ")
    _save(fig, path)


def _chart_solar(df: pd.DataFrame, path: str) -> None:
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    # aggregate to monthly
    df["month"] = df["day"].dt.month
    monthly = df.groupby("month").agg(
        consumption_kwh=("consumption_kwh", "sum"),
        solar_kwh =("solar_kwh", "sum"),
        battery_kwh =("battery_kwh", "sum"),
        grid_import_kwh=("grid_import_kwh", "sum"),
    ).reset_index()

    x = np.arange(len(monthly))
    w = 0.5

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5),
                                   gridspec_kw={"width_ratios": [2, 1]})

    ax1.bar(x, monthly["solar_kwh"],       w, label="СЕС генерація",  color=C["solar"])
    ax1.bar(x, monthly["battery_kwh"],     w, bottom=monthly["solar_kwh"],
            label="BESS розрядка", color=C["battery"])
    ax1.bar(x, monthly["grid_import_kwh"], w,
            bottom=monthly["solar_kwh"] + monthly["battery_kwh"],
            label="Мережа (імпорт)", color=C["grid"])
    ax1.plot(x, monthly["consumption_kwh"], "o--",
             color=C["peak"], lw=1.8, markersize=5, label="Загальне споживання", zorder=3)

    ax1.set_xticks(x)
    ax1.set_xticklabels([MONTHS_UA[int(m)-1] for m in monthly["month"]])
    ax1.set_ylabel("кВт·год")
    ax1.legend(fontsize=8.5, loc="upper right")
    _fmt_kwh(ax1)
    _subtitle(ax1, "Місячний енергобаланс: СЕС / BESS / мережа — 2025 рік")

    ann_sol  = monthly["solar_kwh"].sum()
    ann_bat  = monthly["battery_kwh"].sum()
    ann_grid = monthly["grid_import_kwh"].sum()
    total    = ann_sol + ann_bat + ann_grid

    vals   = [ann_sol, ann_bat, ann_grid]
    lbls   = ["СЕС", "BESS", "Мережа"]
    clrs   = [C["solar"], C["battery"], C["grid"]]
    wedges, _, auts = ax2.pie(
        vals, labels=lbls, colors=clrs,
        autopct="%1.1f%%", startangle=90,
        pctdistance=0.75,
        wedgeprops=dict(width=0.52, edgecolor="white", linewidth=2),
    )
    for at in auts:
        at.set_fontsize(10); at.set_fontweight("bold"); at.set_color("white")
    _subtitle(ax2, "Джерела покриття\n(річний підсумок)")

    plt.tight_layout()
    _save(fig, path)