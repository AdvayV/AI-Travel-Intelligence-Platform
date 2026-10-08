import json
import re


def _text(value):
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= 1200 else text[:1200].rsplit(" ", 1)[0] + "… (excerpt shortened)"


def _label(key):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key).replace("_", " ").strip().lower()


def _value(value, depth=0):
    if value is None:
        return "not recorded"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    if isinstance(value, str):
        return _text(value)
    if depth >= 3:
        return "additional nested properties (see technical details)"
    if isinstance(value, dict):
        return "; ".join(f"{_label(key)}: {_value(item, depth + 1)}" for key, item in value.items()
                         if not key.startswith("_") and item is not None) or "no readable properties"
    if isinstance(value, (list, tuple)):
        items = [_value(item, depth + 1) for item in value[:12]]
        return ", ".join(items) + ("; additional items omitted" if len(value) > 12 else "") if items else "none recorded"
    return _text(value)


def _sentences(properties):
    parts = []
    name = properties.get("name")
    identifier = properties.get("id") or properties.get("code")
    if name:
        parts.append(f"This record describes {_text(name)}" + (f" ({_text(identifier)})" if identifier else ""))
    elif identifier:
        parts.append(f"The record identifier is {_text(identifier)}")
    for key, value in properties.items():
        if key.startswith("_") or key in {"name", "id", "code"} or value is None or value == "":
            continue
        if key == "allowed_cabins":
            parts.append(f"Permitted cabins are {_value(value).replace('_', ' ').title()}")
        elif key == "allowed_fare_classes":
            parts.append(f"Permitted fare codes are {_value(value)}")
        elif key == "preferred_airlines":
            parts.append(f"Preferred airline codes are {_value(value)}")
        elif key in {"max_fare_inr", "max_fare"}:
            parts.append(f"The maximum fare is INR {_value(value)}")
        elif key in {"price_inr", "total_fare_inr"}:
            parts.append(f"The recorded fare is INR {_value(value)}")
        elif key == "requires_approval_above_inr":
            parts.append(f"Approval is required for fares above INR {_value(value)}")
        elif key == "min_advance_days":
            parts.append(f"The minimum advance-booking window is {_value(value)} days")
        elif key == "snippet":
            parts.append(_text(value))
        else:
            parts.append(f"The recorded {_label(key)} is {_value(value)}")
    return ". ".join(part.rstrip(".") for part in parts) + "." if parts else ""


def _record_paragraph(record):
    if not isinstance(record, dict):
        return f"The query returned {_value(record)}."
    if "PolicySnippet" in record or "SectionTitle" in record:
        title = record.get("SectionTitle")
        snippet = record.get("PolicySnippet")
        paragraph = f"{_text(title)}: " if title else ""
        paragraph += _text(snippet) if snippet else "No policy excerpt was recorded for this section."
        page = record.get("PageNumber")
        if page and page != "0":
            paragraph += f" (page {_value(page)})"
        return paragraph.rstrip(".") + "."
    paragraphs = []
    scalars = {}
    for key, value in record.items():
        if key.startswith("_") or value is None:
            continue
        if isinstance(value, dict):
            paragraph = _sentences(value)
            if paragraph:
                paragraphs.append(paragraph)
        else:
            scalars[key] = value
    if scalars:
        paragraphs.append(_sentences(scalars))
    return " ".join(paragraphs)


def format_graph_answer(question, results, max_records=15):
    if not results:
        return "No matching records were found in the graph for this question."
    paragraphs = []
    for record in results[:max_records]:
        paragraph = _record_paragraph(record)
        if paragraph and paragraph not in paragraphs:
            paragraphs.append(paragraph)
    if not paragraphs:
        return f"The query returned {len(results)} records, but no readable properties were recorded."
    if len(results) > max_records:
        paragraphs.append(f"This summary covers the first {max_records} of {len(results)} records. The remaining records are available in technical details.")
    return "\n\n".join(paragraphs)


def paragraph_answer(answer, question, results):
    if not isinstance(answer, str) or not answer.strip():
        return format_graph_answer(question, results)
    answer = answer.strip()
    if re.fullmatch(r"(?:Found \d+ (?:records|rows)(?: matching your query)?|(?:The )?query returned \d+ (?:records|rows)|Successfully executed Cypher query\.\s*Found \d+ rows)[.!]?", answer, re.IGNORECASE):
        return format_graph_answer(question, results)
    if answer.startswith(("{", "[")) or "```" in answer or re.search(r'\{\s*"[^"\n]+"\s*:', answer) or re.match(r"^(MATCH|RETURN|CALL|WITH)\b", answer, re.IGNORECASE):
        return format_graph_answer(question, results)
    try:
        json.loads(answer)
    except (ValueError, TypeError):
        pass
    else:
        return format_graph_answer(question, results)
    answer = re.sub(r"(?m)^\s*(?:[-*]\s+|\d+[.)]\s+|#+\s+)", "", answer).replace("**", "")
    return "\n\n".join(re.sub(r"\s+", " ", paragraph).strip() for paragraph in re.split(r"\n\s*\n", answer) if paragraph.strip())
