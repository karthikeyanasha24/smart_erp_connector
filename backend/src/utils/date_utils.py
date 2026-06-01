"""
Time Intelligence Engine
Resolves natural language time expressions into SQL date ranges.
Covers: today, yesterday, MTD, YTD, QTD, last_7d, last_30d, last_90d,
        last_month, last_quarter, last_year, rolling periods, specific months/quarters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# ─── IST timezone ────────────────────────────────────────────────────────────
# The ERP (SQL Server) records transactions in Indian Standard Time (UTC+5:30).
# All "today / yesterday / MTD" date boundaries must be resolved in IST so that
# midnight rolls over at the correct business time — not UTC midnight.
_IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    """Current calendar date in IST (UTC+5:30). Use instead of date.today()."""
    return datetime.now(_IST).date()


@dataclass
class DateRange:
    start: str    # YYYY-MM-DD
    end: str      # YYYY-MM-DD
    label: str
    period: str   # canonical period key


def _fmt(d: date) -> str:
    return d.isoformat()


def _start_of_month(d: date) -> date:
    return d.replace(day=1)


def _end_of_month(d: date) -> date:
    # Move to first of next month, subtract one day
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


def _start_of_year(d: date) -> date:
    return d.replace(month=1, day=1)


def _get_quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _start_of_quarter(d: date) -> date:
    q = _get_quarter(d)
    return d.replace(month=(q - 1) * 3 + 1, day=1)


def _end_of_quarter(d: date) -> date:
    q = _get_quarter(d)
    end_month = q * 3
    end = d.replace(month=end_month, day=1)
    return _end_of_month(end)


# ─── Resolver ─────────────────────────────────────────────────────────────────

def resolve_date_range(period: str, ref_date: Optional[date] = None) -> DateRange:
    today = ref_date or today_ist()
    today_str = _fmt(today)

    lower = re.sub(r"[\s_\-]+", "_", period.lower().strip())

    if lower == "today":
        return DateRange(today_str, today_str, "Today", "today")

    if lower == "yesterday":
        y = today - timedelta(days=1)
        return DateRange(_fmt(y), _fmt(y), "Yesterday", "yesterday")

    if lower in ("mtd", "month_to_date", "this_month"):
        return DateRange(_fmt(_start_of_month(today)), today_str, "Month-to-Date", "mtd")

    if lower in ("ytd", "year_to_date", "this_year"):
        return DateRange(_fmt(_start_of_year(today)), today_str, "Year-to-Date", "ytd")

    if lower in ("qtd", "quarter_to_date", "this_quarter"):
        return DateRange(_fmt(_start_of_quarter(today)), today_str, "Quarter-to-Date", "qtd")

    if lower in ("last_7d", "last_7_days", "past_week"):
        return DateRange(_fmt(today - timedelta(days=6)), today_str, "Last 7 Days", "last_7d")

    if lower in ("last_30d", "last_30_days", "past_month"):
        return DateRange(_fmt(today - timedelta(days=29)), today_str, "Last 30 Days", "last_30d")

    if lower in ("last_90d", "last_90_days", "last_quarter_rolling"):
        return DateRange(_fmt(today - timedelta(days=89)), today_str, "Last 90 Days", "last_90d")

    if lower in ("last_month", "previous_month"):
        lm = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        return DateRange(_fmt(lm), _fmt(_end_of_month(lm)), "Last Month", "last_month")

    if lower in ("last_quarter", "previous_quarter"):
        # Go back 3 months from start of current quarter
        sqtr = _start_of_quarter(today)
        lq_end = sqtr - timedelta(days=1)
        lq_start = _start_of_quarter(lq_end)
        return DateRange(_fmt(lq_start), _fmt(lq_end), "Last Quarter", "last_quarter")

    if lower in ("last_year", "previous_year"):
        ly = today.replace(year=today.year - 1, month=1, day=1)
        ly_end = today.replace(year=today.year - 1, month=12, day=31)
        return DateRange(_fmt(ly), _fmt(ly_end), "Last Year", "last_year")

    # Rolling "last N days/weeks/months/years"
    rolling = re.match(r"last[_\s](\d+)[_\s]?(day|week|month|year)s?", lower)
    if rolling:
        n = int(rolling.group(1))
        unit = rolling.group(2)
        if unit == "day":
            days_back = n
        elif unit == "week":
            days_back = n * 7
        elif unit == "month":
            days_back = n * 30
        else:
            days_back = n * 365
        s = _fmt(today - timedelta(days=days_back - 1))
        label = f"Last {n} {unit}{'s' if n > 1 else ''}"
        return DateRange(s, today_str, label, f"last_{n}_{unit}s")

    # Specific month name: "january 2024", "jan 24"
    month_names = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    for i, m in enumerate(month_names):
        pat = rf"\b{m}\w*[_\s]?(\d{{2,4}})?\b"
        match = re.search(pat, lower)
        if match:
            yr_str = match.group(1)
            year = today.year
            if yr_str:
                year = int(f"20{yr_str}" if len(yr_str) == 2 else yr_str)
            d = date(year, i + 1, 1)
            end = _end_of_month(d)
            label = d.strftime("%B %Y")
            return DateRange(_fmt(d), _fmt(end), label, f"month_{year}_{i + 1}")

    if lower in ("last_6m", "last_6_months", "last_180d"):
        return DateRange(_fmt(today - timedelta(days=179)), today_str, "Last 6 Months", "last_180d")

    # Default to MTD
    return DateRange(_fmt(_start_of_month(today)), today_str, "Month-to-Date", "mtd")


def resolve_custom_range(start: str, end: str) -> DateRange:
    """Parse YYYY-MM-DD start/end from custom date picker."""
    s = date.fromisoformat(start.strip()[:10])
    e = date.fromisoformat(end.strip()[:10])
    if e < s:
        s, e = e, s
    return DateRange(_fmt(s), _fmt(e), f"{_fmt(s)} to {_fmt(e)}", "custom")


def trend_granularity(period: str) -> str:
    """day for MTD/today; month for QTD, YTD, last_6m."""
    p = period.lower()
    if p in ("today", "yesterday", "mtd", "last_7d", "last_14d", "last_30d", "custom"):
        return "day"
    return "month"


def get_prior_year_range(period: str, ref_date: Optional[date] = None) -> DateRange:
    """Same calendar window one year earlier (for YoY bar comparison)."""
    dr = resolve_date_range(period, ref_date)
    s = date.fromisoformat(dr.start).replace(year=date.fromisoformat(dr.start).year - 1)
    e = date.fromisoformat(dr.end).replace(year=date.fromisoformat(dr.end).year - 1)
    return DateRange(_fmt(s), _fmt(e), f"LY {dr.label}", f"ly_{dr.period}")


# ─── Period Detector ──────────────────────────────────────────────────────────

def detect_period(query: str) -> str:
    q = query.lower()

    if re.search(r"\btoday\b", q):
        return "today"
    if re.search(r"\byesterday\b", q):
        return "yesterday"
    if re.search(r"\bmtd\b|month.?to.?date|this month", q):
        return "mtd"
    if re.search(r"\bytd\b|year.?to.?date|this year", q):
        return "ytd"
    if re.search(r"\bqtd\b|quarter.?to.?date|this quarter", q):
        return "qtd"
    if re.search(r"last\s+7\s+days?|past\s+week", q):
        return "last_7d"
    if re.search(r"last\s+30\s+days?", q):
        return "last_30d"
    if re.search(r"last\s+90\s+days?", q):
        return "last_90d"
    if re.search(r"last\s+month|previous\s+month", q):
        return "last_month"
    if re.search(r"last\s+quarter|previous\s+quarter", q):
        return "last_quarter"
    if re.search(r"last\s+year|previous\s+year", q):
        return "last_year"

    rolling = re.search(r"last\s+(\d+)\s+(day|week|month|year)s?", q)
    if rolling:
        return f"last_{rolling.group(1)}_{rolling.group(2)}s"

    return "mtd"


# ─── Comparison Period ────────────────────────────────────────────────────────

def get_comparison_range(period: str, ref_date: Optional[date] = None) -> DateRange:
    ref = ref_date or today_ist()
    canonical = period.lower()

    if canonical == "mtd":
        prev = (ref.replace(day=1) - timedelta(days=1)).replace(day=1)
        r = resolve_date_range("mtd", prev)
        return DateRange(r.start, r.end, "Prior MTD", "prior_mtd")

    if canonical == "ytd":
        prev = ref.replace(year=ref.year - 1, month=1, day=1)
        r = resolve_date_range("ytd", prev)
        return DateRange(r.start, r.end, "Prior YTD", "prior_ytd")

    if canonical == "qtd":
        prev = ref.replace(year=ref.year - 1)
        r = resolve_date_range("qtd", prev)
        return DateRange(r.start, r.end, "Prior QTD", "prior_qtd")

    if canonical in ("last_180d", "last_6m"):
        dr = resolve_date_range("last_180d", ref)
        s = date.fromisoformat(dr.start) - timedelta(days=365)
        e = date.fromisoformat(dr.end) - timedelta(days=365)
        return DateRange(_fmt(s), _fmt(e), "Prior Year (6M)", "prior_6m")

    # Default: one year back
    prev = ref.replace(year=ref.year - 1)
    r = resolve_date_range(period, prev)
    return DateRange(r.start, r.end, f"Prior {r.label}", f"prior_{r.period}")


# ─── Cache key helpers ────────────────────────────────────────────────────────

# Periods whose cache must roll over at midnight (end date = today).
_ROLLING_CACHE_PERIODS = frozenset({
    "today", "yesterday", "mtd", "qtd", "ytd",
    "last_7d", "last_30d", "last_90d", "last_180d", "last_6m", "last_365d",
})


def cache_as_of_date(period: str, ref_date: Optional[date] = None) -> str:
    """ISO end-date for a period — used as cache key suffix (resolved in IST)."""
    return resolve_date_range(period, ref_date).end


def period_cache_key(prefix: str, period: str, ref_date: Optional[date] = None) -> str:
    """
    Build a cache key that invalidates when the calendar day rolls over.
    Fixed historical periods (last_month, last_quarter) omit the date suffix.
    """
    if period in _ROLLING_CACHE_PERIODS:
        return f"{prefix}:{period}:{cache_as_of_date(period, ref_date)}"
    return f"{prefix}:{period}"


def cache_key_date_suffix(key: str) -> Optional[str]:
    """Extract trailing YYYY-MM-DD from a cache key, if present."""
    m = re.search(r":(\d{4}-\d{2}-\d{2})$", key)
    return m.group(1) if m else None


def cache_key_is_stale(key: str, ref_date: Optional[date] = None) -> bool:
    """True when a date-suffixed key belongs to a prior calendar day (compared in IST)."""
    suffix = cache_key_date_suffix(key)
    if not suffix:
        return False
    today = ref_date or today_ist()
    return suffix != _fmt(today)
ix.
    """
    if period in _ROLLING_CACHE_PERIODS:
        return f"{prefix}:{period}:{cache_as_of_date(period, ref_date)}"
    return f"{prefix}:{period}"


def cache_key_date_suffix(key: str) -> Optional[str]:
    """Extract trailing YYYY-MM-DD from a cache key, if present."""
    m = re.search(r":(\d{4}-\d{2}-\d{2})$", key)
    return m.group(1) if m else None


def cache_key_is_stale(key: str, ref_date: Optional[date] = None) -> bool:
    """True when a date-suffixed key belongs to a prior calendar day (compared in IST)."""
    suffix = cache_key_date_suffix(key)
    if not suffix:
        return False
    today = ref_date or today_ist()
    return suffix != _fmt(today)
