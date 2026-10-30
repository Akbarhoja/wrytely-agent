"""Narrow deterministic formatting checks; no policy or permission inference."""

import re

SEPARATE_DISCLOSURE = re.compile(
    r"^Include this disclosure separately from the word-counted body:[ \t]*\r?\n([^\r\n]+)",
    re.MULTILINE,
)
WORD_RANGE = re.compile(
    r"\bwrite\s+(?:a\s+)?(\d{1,5})\s*[-–—]\s*(\d{1,5})\s*-?\s*words?\b",
    re.IGNORECASE,
)
NUMERIC_WORDS = re.compile(r"\d+\s*(?:[-–—]\s*\d+)?\s*-?\s*words?\b", re.IGNORECASE)


def check_draft_format(draft, policy, policy_content, rubric):
    errors = []
    instructions = SEPARATE_DISCLOSURE.findall(policy_content)
    placement = "separate_field" if instructions else "body_and_field"
    if policy.status == "disclosure_required":
        if instructions:
            required = {text.strip() for text in instructions}
            if len(required) != 1 or not next(iter(required)):
                errors.append("disclosure_format_ambiguous")
            elif draft.disclosure != next(iter(required)):
                errors.append("disclosure_text_mismatch")
            if draft.disclosure.strip() and draft.disclosure in draft.body:
                errors.append("disclosure_must_be_separate")
        elif not draft.disclosure.strip() or draft.disclosure not in draft.body:
            errors.append("disclosure_missing_from_body")
    # Count whitespace-delimited tokens, including numbers and hyphenated tokens.
    # Separate disclosure is not in body; default body disclosure is counted.
    count = len(draft.body.split())
    ranges = []
    for item in rubric:
        matches = list(WORD_RANGE.finditer(item.quote))
        numeric = list(NUMERIC_WORDS.finditer(item.quote))
        unparsed = any(
            not any(m.start() <= n.start() and n.end() <= m.end() for m in matches) for n in numeric
        )
        if (
            not matches
            and re.search(r"\d", item.quote)
            and re.search(r"\bwords?\b", item.quote, re.I)
        ):
            unparsed = True
        if unparsed:
            errors.append("word_count_requirement_unparsed")
        for match in matches:
            low, high = map(int, match.groups())
            if not 1 <= low <= high <= 10000:
                errors.append("word_count_requirement_invalid")
                continue
            ranges.append(
                {
                    "version_id": str(item.version_id),
                    "quote": item.quote,
                    "minimum": low,
                    "maximum": high,
                }
            )
            if not low <= count <= high:
                errors.append("word_count_out_of_range")
    if ranges and max(row["minimum"] for row in ranges) > min(row["maximum"] for row in ranges):
        errors.append("word_count_bounds_conflict")
    return {
        "errors": list(dict.fromkeys(errors)),
        "word_count": count,
        "disclosure_placement": placement,
        "word_ranges": ranges,
        "limits": "Recognizes explicit Write N–M word ranges in supplied exact rubric quotes only; "
        "rubric completeness and other language require separate semantic review.",
    }
