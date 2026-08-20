import re
from datetime import date, datetime, timedelta


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _resolve_named_date(day: int, month: int, year: int | None, base_date: date) -> str:
    resolved_year = year or base_date.year
    candidate = date(resolved_year, month, day)
    if year is None and candidate < base_date:
        candidate = date(resolved_year + 1, month, day)
    return candidate.isoformat()


def parse_prompt_date(query: str, current_date_str: str | None = None) -> str:
    base_date = date.today()
    if current_date_str:
        try:
            base_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    query_lower = query.lower()
    date_match = re.search(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b", query)
    if date_match:
        return date(
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
        ).isoformat()

    reverse_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", query)
    if reverse_match:
        return date(
            int(reverse_match.group(3)),
            int(reverse_match.group(2)),
            int(reverse_match.group(1)),
        ).isoformat()

    month_pattern = "|".join(sorted(MONTHS, key=len, reverse=True))
    day_first = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:\s*,?\s*(\d{{4}}))?\b",
        query_lower,
    )
    if day_first:
        year = int(day_first.group(3)) if day_first.group(3) else None
        return _resolve_named_date(
            int(day_first.group(1)),
            MONTHS[day_first.group(2)],
            year,
            base_date,
        )

    month_first = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?\b",
        query_lower,
    )
    if month_first:
        year = int(month_first.group(3)) if month_first.group(3) else None
        return _resolve_named_date(
            int(month_first.group(2)),
            MONTHS[month_first.group(1)],
            year,
            base_date,
        )

    if "day after tomorrow" in query_lower:
        return (base_date + timedelta(days=2)).isoformat()
    if "today" in query_lower:
        return base_date.isoformat()
    if "tomorrow" in query_lower:
        return (base_date + timedelta(days=1)).isoformat()
    if "next week" in query_lower:
        return (base_date + timedelta(days=7)).isoformat()

    days_match = re.search(r"\bin\s+(\d+)\s+days\b", query_lower)
    if days_match:
        return (base_date + timedelta(days=int(days_match.group(1)))).isoformat()

    return (base_date + timedelta(days=14)).isoformat()
