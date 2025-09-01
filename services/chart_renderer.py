# services/chart_renderer.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from core.logger import get_logger

logger = get_logger("chart_renderer")

def render_chart_with_overlays(
    df: pd.DataFrame,
    overlays: Dict[str, Any],
    out_path: str,
    title: Optional[str] = None
) -> str:
    # ---- OHLC бэлтгэх
    needed = ["time","open","high","low","close"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    d = df[needed].copy()
    
    # Debug: анхны өгөгдлийг шалгах
    logger.info(f"Original time column type: {df['time'].dtype}")
    logger.info(f"Original time values: {df['time'].head().tolist()}")
    
    # MT5-аас timestamp төрлөөр ирсэн байх ёстой
    d = d.copy()
    # DATETIME хөрвүүлэлтийг уян хатан болгох
    d["time"] = pd.to_datetime(d["time"], errors="coerce")
    d = d.rename(columns={"time":"Date","open":"Open","high":"High","low":"Low","close":"Close"})
    d = d.set_index("Date")

    # --- DATETIME INDEX БАТАЛГААЖУУЛАЛТ ---
    d.index = pd.to_datetime(d.index, errors="coerce")
    d = d[~d.index.isna()]
    d = d[~d.index.duplicated()]
    d = d.sort_index()
    # Хэрэв 1970 хэвээр байвал UNIX timestamp гэж үзээд хөрвүүлнэ
    if d.index.min().year < 2000:
        d.index = pd.to_datetime(d.index.astype(int) // 10**9, unit='s', errors='coerce')
        d = d[~d.index.isna()]
        d = d[~d.index.duplicated()]
        d = d.sort_index()
    assert isinstance(d.index, pd.DatetimeIndex), f"Index is not DatetimeIndex: {type(d.index)}"
    assert d.index.min().year > 2000, f"Min year is {d.index.min().year}, check time data!"
    
    # Index шалгах ба баталгаажуулах
    if not isinstance(d.index, pd.DatetimeIndex):
        logger.warning("Index is not DatetimeIndex - converting...")
        d.index = pd.to_datetime(d.index, utc=True)
        
    # Timezone fix
    d.index = d.index.tz_localize(None)
    
    # Хугацааны интервал шалгах
    time_range = d.index.max() - d.index.min()
    logger.info(f"Time range: {time_range} ({d.index.min()} to {d.index.max()})")
    
    if d.index.year.min() < 2020 or d.index.year.max() > 2030:
        raise ValueError(f"Suspicious date range: {d.index.min()} to {d.index.max()}")
    
    # ---- Volume (байвал л асаана)
    vol_flag = False
    for c in ("real_volume","tick_volume","volume"):
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce")
            v = pd.Series(v.values, index=d.index)
            if v.notna().any() and (v.max() > v.min()):
                d["Volume"] = v.fillna(0)
                vol_flag = True
                break

    # ---- Хадгалах зам (absolute) ба хавтас
    out_path_abs = str((Path(__file__).resolve().parent.parent / out_path).resolve())
    Path(out_path_abs).parent.mkdir(parents=True, exist_ok=True)

    # ---- Зурах
    # mplfinance-д зориулж plot_df бэлдэх
    plot_df = pd.DataFrame(index=d.index)
    plot_df["Open"] = d["Open"]
    plot_df["High"] = d["High"]
    plot_df["Low"] = d["Low"]
    plot_df["Close"] = d["Close"]
    if "Volume" in d.columns:
        plot_df["Volume"] = d["Volume"]
    
    # Debug logging
    logger.info(f"Plot DataFrame index: {type(plot_df.index)}")
    logger.info(f"Plot date range: {plot_df.index.min()} to {plot_df.index.max()}")
    # Extra diagnostics to catch 1970-style axis issues
    logger.info(f"d.index dtype: {d.index.dtype}; sample: {d.index[:5].tolist()}")
    logger.info(f"plot_df.index dtype: {plot_df.index.dtype}; sample: {plot_df.index[:5].tolist()}")
    
    # --- Replace mplfinance with explicit matplotlib candlestick rendering
    # If candlestick_ohlc is not available, fall back to mplfinance.plot
    if 'candlestick_ohlc' not in globals() or candlestick_ohlc is None:
        logger.info('candlestick_ohlc not available, falling back to mplfinance.plot')
        fig, axlist = mpf.plot(
            plot_df,
            type='candle',
            volume=vol_flag,
            style='nightclouds',
            returnfig=True,
            figratio=(16,9),
            figscale=1.0,
            datetime_format='%Y-%m-%d %H:%M',
            xrotation=25
        )
        ax = axlist[0]
        ax_vol = axlist[2] if len(axlist) > 2 else (axlist[1] if len(axlist) > 1 else None)
    else:
        # Convert cleaned index to timezone-aware then naive times, then to matplotlib floats
        times = pd.to_datetime(d.index, utc=True).tz_convert('Asia/Ulaanbaatar').tz_localize(None)
        x = mdates.date2num(times.to_pydatetime())

        # Create OHLC array for candlestick_ohlc
        ohlc = np.column_stack([
            x,
            d['Open'].to_numpy(),
            d['High'].to_numpy(),
            d['Low'].to_numpy(),
            d['Close'].to_numpy()
        ])

        # Figure and axes (sharex=True so price and volume align)
        fig, (ax_price, ax_vol) = plt.subplots(
            nrows=2, ncols=1, sharex=True,
            gridspec_kw={'height_ratios': (6, 1)}, figsize=(12, 8)
        )
        # overlays-тэй нийцүүлэхийн тулд нэг гол axes-ийг 'ax' болгон онооно
        ax = ax_price

        ax_price.set_facecolor('black')
        ax_vol.set_facecolor('black')
        ax_price.grid(True, linestyle='--', color='#404040')

        # 1) Compute median step (dx) from x to size bars correctly
        if len(x) > 1:
            dx = np.median(np.diff(x))
        else:
            dx = 1/48  # fallback: 30min ≈ 1/48 day

        candle_w = dx * 0.6
        bar_w = dx * 0.8

        # Draw candlesticks
        candlestick_ohlc(ax_price, ohlc, width=candle_w, colorup='white', colordown='#00A7E1', alpha=1.0)

        # Draw volume bars
        if 'Volume' in d.columns:
            vol = d['Volume'].to_numpy()
            colors = ['white' if c >= o else '#00A7E1' for o, c in zip(d['Open'].to_numpy(), d['Close'].to_numpy())]
            ax_vol.bar(x, vol, width=bar_w, color=colors, align='center')

        # 2) Remove any manual xlim remnants by re-scaling axes to data
        ax_price.relim(); ax_price.autoscale_view()
        ax_vol.relim(); ax_vol.autoscale_view()

        # 3) Concise date formatter and locator
        loc = mdates.AutoDateLocator()
        fmt = mdates.ConciseDateFormatter(loc)
        for ax in (ax_price, ax_vol):
            ax.xaxis.set_major_locator(loc)
            ax.xaxis.set_major_formatter(fmt)
            ax.grid(True, linestyle='--', alpha=0.25)
        ax_price.tick_params(axis='x', rotation=0)

    # --- Overlays (минимал)
    for tl in overlays.get("trendlines", []):
        t1 = pd.to_datetime(tl["anchor_a"]["time"]); p1 = tl["anchor_a"]["price"]
        t2 = pd.to_datetime(tl["anchor_b"]["time"]); p2 = tl["anchor_b"]["price"]
        ax.plot([t1, t2], [p1, p2], linewidth=1.5)
    for z in overlays.get("zones", []):
        ax.axhspan(z["price_min"], z["price_max"], alpha=0.15)
    for fb in overlays.get("fibonacci", []):
        hi = fb["swing_high"]["price"]; lo = fb["swing_low"]["price"]
        for lvl in fb["levels"]:
            ax.axhline(lo + (hi-lo)*float(lvl), linestyle="--", linewidth=0.8)
    # --- Annotate Entry / SL / TP if provided in overlays
    # overlays may include: overlays['annotate_levels'] = {'entry': float, 'sl': float, 'tp': float}
    def _annotate_levels(ax, entry=None, sl=None, tp=None):
        try:
            xlim = ax.get_xlim()
            x_pos = xlim[1]
        except Exception:
            x_pos = None
        items = (
            (entry, 'Entry', 'yellow'),
            (sl, 'SL', 'red'),
            (tp, 'TP', 'lime')
        )
        for price, label, color in items:
            if price is None:
                continue
            ax.axhline(price, color=color, linestyle='-', linewidth=1.0, alpha=0.9)
            try:
                if x_pos is not None:
                    ax.text(x_pos, price, f"{label} {price:.2f}", color=color,
                            fontsize=8, ha='right', va='center', backgroundcolor='black')
                else:
                    ax.text(0.98, price, f"{label} {price:.2f}", color=color,
                            fontsize=8, ha='right', va='center', transform=ax.get_yaxis_transform(), backgroundcolor='black')
            except Exception:
                # Best-effort annotate; don't fail the whole render for text placement issues
                logger.debug("Failed to draw level label for %s", label)

    ann = overlays.get('annotate_levels') or overlays.get('levels')
    if isinstance(ann, dict):
        _annotate_levels(ax, entry=ann.get('entry'), sl=ann.get('sl'), tp=ann.get('tp'))
    # X тэнхлэгийн тохиргоо
    fig.autofmt_xdate()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    
    # Хадгалах
    plt.savefig(out_path_abs, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path_abs
