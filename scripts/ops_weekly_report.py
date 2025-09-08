# scripts/ops_weekly_report.py
# ------------------------------------------------------------
# Зорилго: Өнгөрсөн 7 хоногийн /metrics snapshot + аудит логуудаас
# KPI гаргаж, docs/WEEKLY_OPS_REPORT.md тайланг монголоор үүсгэнэ.
# KPI: p95 loop, rejected%, timeout%, orders count,
#      partial→filled ratio, SLA breaches, DR drill статус
# Хэрэглээ: python scripts/ops_weekly_report.py
# Орших газар:
#   - artifacts/metrics-YYYYMMDD-HHMM.json  (snapshot_metrics.py гаргасан)
#   - logs/audit-YYYYMMDD.jsonl             (AuditLogger-ийн бичлэг)
# ------------------------------------------------------------
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import pathlib
import re
from statistics import median

ART = pathlib.Path("artifacts")
LOG = pathlib.Path("logs")
DOCS = pathlib.Path("docs")
DOCS.mkdir(parents=True, exist_ok=True)


# --- Туслах функцууд (монгол коммент) ---


def _load_recent_metric_snapshots(days: int = 7) -> list[dict]:
    """Сүүлийн N хоногийн metrics snapshot-уудыг уншина."""
    if not ART.exists():
        return []
    files = sorted(ART.glob("metrics-*.json"))
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    out = []
    for f in files:
        # Файлын нэрээс UTC ts (YYYYMMDD-HHMM) авахыг оролдъё
        # Жишээ: metrics-20250908-1100.json
        try:
            ts_str = f.stem.split("-")[1]
            snap_dt = dt.datetime.strptime(ts_str, "%Y%m%d")
        except Exception:
            # Мөрийн огноо parse болохгүй бол файлыг уншаад ts_utc-г ашиглана
            try:
                snap = json.loads(f.read_text(encoding="utf-8"))
                ts_utc = snap.get("ts_utc")
                if ts_utc:
                    # ts_utc = "YYYYMMDD-HHMM"
                    snap_dt = dt.datetime.strptime(ts_utc.split("-")[0], "%Y%m%d")
                else:
                    snap_dt = dt.datetime.min
            except:
                snap_dt = dt.datetime.min
        if snap_dt >= cutoff:
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return out


def _parse_prom(text: str, name: str) -> float | None:
    """
    Prometheus-подоб текстээс ганц metric-ийн утгыг авах.
    Жишээ мөр: trade_loop_latency_ms_p95{...} 183.42
               rejected_rate 0.031
    """
    # ^metric({labels})? <value>
    pat = re.compile(
        rf"^{re.escape(name)}(?:{{[^}}]*}})?\s+([-+eE0-9\.]+)\s*$", re.MULTILINE
    )
    m = pat.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _agg(values: list[float]) -> tuple[float | None, float | None]:
    """Дундаж ба медиан (хоёуланг нь буцаана)."""
    if not values:
        return None, None
    avg = sum(values) / len(values)
    med = median(values)
    return avg, med


def _load_audit_events(days: int = 7) -> list[dict]:
    """Сүүлийн N хоногийн аудит логуудаас бүх мөрийг цуглуулна (jsonl)."""
    out = []
    if not LOG.exists():
        return out
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).date()
    for f in sorted(LOG.glob("audit-*.jsonl")):
        # Файлын нэр: audit-YYYYMMDD.jsonl
        try:
            dstr = f.stem.split("-")[1]
            fdate = dt.datetime.strptime(dstr, "%Y%m%d").date()
        except Exception:
            fdate = dt.date.min
        if fdate < cutoff:
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _fmt(val: float | None, suffix: str = "", places: int = 2, na: str = "—") -> str:
    """Тоог форматлана (None бол '—')."""
    if val is None:
        return na
    return f"{val:.{places}f}{suffix}"


def _decide_actions(stats: dict) -> list[str]:
    """Үзүүлэлтүүдийг үндэслэн цаашдын арга хэмжээг санал болгоно."""
    actions = []

    # P95 latency > 250ms
    if stats["loop_latency_ms_p95"] and stats["loop_latency_ms_p95"] > 250:
        actions.append("- **Loop хурд сайжруулах**: P95 latency-г 200ms доошлуулах")

    # Rejected rate > 5%
    if stats["rejected_rate"] and stats["rejected_rate"] > 0.05:
        actions.append("- **Rejection шийдэх**: Тайлбарыг шалгаж засах")

    # Too many SLA breaches
    if stats["sla_breach_count"] and stats["sla_breach_count"] > 10:
        actions.append("- **SLA зөрчил багасгах**: Системийн ачаалал тохируулах")

    # DR drill overdue
    if not stats["dr_drill_this_week"]:
        actions.append("- **DR дадлага хийх**: Сэргээн босголтын тест")

    if not actions:
        actions.append("- Бүх үзүүлэлт хэвийн түвшинд байна ✅")

    return actions


def main():
    """Үндсэн ажиллагаа: 7 хоногийн тайлан үүсгэх."""
    print("🔍 Өнгөрсөн 7 хоногийн тайлан эхлэж байна...")

    # 1) Metrics цуглуулах
    snapshots = _load_recent_metric_snapshots()
    print(f"📊 {len(snapshots)} metrics snapshot олдлоо")

    # 2) KPI тооцоолох
    p95_vals, rej_vals, timeout_vals = [], [], []
    orders_total = 0

    for snap in snapshots:
        text = snap.get("text", "")

        # Loop latency p95
        p95 = _parse_prom(text, "trade_loop_latency_ms_p95")
        if p95 is not None:
            p95_vals.append(p95)

        # Reject rate
        rej = _parse_prom(text, "rejected_rate")
        if rej is not None:
            rej_vals.append(rej)

        # Timeout rate
        timeout = _parse_prom(text, "timeout_rate")
        if timeout is not None:
            timeout_vals.append(timeout)

        # Orders count
        orders = _parse_prom(text, "orders_count")
        if orders is not None:
            orders_total += orders

    # 3) Дундаж/медиан
    p95_avg, p95_med = _agg(p95_vals)
    rej_avg, rej_med = _agg(rej_vals)
    timeout_avg, timeout_med = _agg(timeout_vals)

    # 4) Аудит events
    audit_events = _load_audit_events()
    print(f"📋 {len(audit_events)} audit event олдлоо")

    sla_breaches = [e for e in audit_events if e.get("level") == "SLA_BREACH"]
    partial_filled = [e for e in audit_events if e.get("status") == "PARTIAL"]
    full_filled = [e for e in audit_events if e.get("status") == "FILLED"]

    partial_fill_ratio = None
    if len(full_filled) > 0:
        partial_fill_ratio = len(partial_filled) / (
            len(partial_filled) + len(full_filled)
        )

    # DR drill шалгах (энэ 7 хоногт DR event байсан уу)
    dr_events = [e for e in audit_events if "DR" in e.get("message", "").upper()]
    dr_drill_this_week = len(dr_events) > 0

    # 5) Статистик бэлтгэх
    stats = {
        "loop_latency_ms_p95": p95_med,  # медиан ашиглая
        "rejected_rate": rej_med,
        "timeout_rate": timeout_med,
        "orders_total": orders_total,
        "partial_fill_ratio": partial_fill_ratio,
        "sla_breach_count": len(sla_breaches),
        "dr_drill_this_week": dr_drill_this_week,
        "audit_events_count": len(audit_events),
    }

    # 6) Арга хэмжээ санал болгох
    actions = _decide_actions(stats)

    # 7) Markdown тайлан бичих
    now = dt.datetime.utcnow()
    week_start = now - dt.timedelta(days=7)

    report = f"""# 7 Хоногийн Үйл Ажиллагааны Тайлан

**Хугацаа**: {week_start.strftime('%Y-%m-%d')} — {now.strftime('%Y-%m-%d')}
**Үүсгэсэн**: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC

## 🎯 Гол Үзүүлэлтүүд (KPI)

| Үзүүлэлт | Утга | Зорилт |
|-----------|------|---------|
| **Loop Latency (P95)** | {_fmt(stats['loop_latency_ms_p95'], 'ms')} | < 200ms |
| **Reject Rate** | {_fmt(stats['rejected_rate'], '%', places=1)} | < 3% |
| **Timeout Rate** | {_fmt(stats['timeout_rate'], '%', places=1)} | < 1% |
| **Нийт Order** | {int(stats['orders_total']) if stats['orders_total'] else 0} | — |
| **Partial→Fill Ratio** | {_fmt(stats['partial_fill_ratio'], '%', places=1)} | < 10% |

## 🚨 Асуудлууд

| Түвшин | Тоо | Тайлбар |
|--------|-----|---------|
| **SLA Зөрчил** | {stats['sla_breach_count']} | Service level agreement зөрчсөн үйлдэл |
| **DR Drill** | {"✅" if stats['dr_drill_this_week'] else "❌"} | Disaster recovery дадлага хийгдсэн эсэх |
| **Аудит Events** | {stats['audit_events_count']} | Нийт аудит бичлэгийн тоо |

## 📋 Санал болгох арга хэмжээ

{chr(10).join(actions)}

## 📊 Дэлгэрэнгүй мэдээлэл

- **Metrics Snapshots**: {len(snapshots)}
- **Audit Events**: {len(audit_events)}
- **Хяналтын хугацаа**: 7 хоног
- **Дараагийн тайлан**: {(now + dt.timedelta(days=7)).strftime('%Y-%m-%d')}

---
*Автоматаар үүсгэсэн тайлан | Bot Trading System*
"""

    # 8) Файл бичих
    DOCS.mkdir(exist_ok=True)
    report_path = DOCS / "WEEKLY_OPS_REPORT.md"

    # UTF-8 кодчилолтой бичих
    with report_path.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Тайлан бэлэн: {report_path}")
    print("📋 Хураангуй:")
    print(f"   • Loop P95: {_fmt(stats['loop_latency_ms_p95'], 'ms')}")
    print(f"   • Reject: {_fmt(stats['rejected_rate'], '%', places=1)}")
    print(f"   • SLA зөрчил: {stats['sla_breach_count']}")
    print(f"   • DR drill: {'✅' if stats['dr_drill_this_week'] else '❌'}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
