"""
Work out a CTF's AI policy from the text organisers write on CTFtime.

CTFtime has no "AI policy" field, so this reads the event description and
looks for *rules* about AI use. Merely mentioning AI (for example "AI" as a
challenge category) is not a rule, and those events are reported as NOT_STATED.
The result is a best guess from the description: always check the official rules.
"""

import re

ALLOWED = "allowed"
BANNED = "banned"
SEPARATE = "separate"      # separate leaderboards for AI-assisted and human-only play
MIXED = "mixed"            # the text says both (e.g. allowed in quals, banned in finals)
NOT_STATED = "not_stated"

LABELS = {
    ALLOWED: "🤖 AI allowed",
    BANNED: "🚫 No AI",
    SEPARATE: "⚖️ Separate AI / human leaderboards",
    MIXED: "⚠️ Mixed AI rules, check the rules",
    NOT_STATED: "❔ AI policy not stated",
}

# Words that refer to AI tools (not "AI" as a topic on its own; that is checked in context)
AI = r"(?:ai|a\.i\.|llms?|chatgpt|gpt(?:-?\d+)?|claude|gemini|copilot|genai|generative ai|" \
     r"artificial intelligence|large language models?|ai agents?|ai tools?|ai assistance|agents?)"
GAP = r"[^.!?\n]{0,60}?"   # up to 60 characters within the same sentence

SEPARATE_PATTERNS = [
    rf"\b(?:separate|two|different|dual)\b{GAP}\b(?:ai|human)\b{GAP}\b(?:leaderboards?|scoreboards?|brackets?|divisions?|tracks?|categories)\b",
    r"\bai\s*/\s*human\b|\bhuman\s*/\s*ai\b",
    r"\bhumans?\b.{0,160}?\bcyborgs?\b",   # "Humans solve clean... Cyborgs bring any tools"
]

# Negated bans: "AI is not forbidden", "we don't ban AI", "we do not limit how teams use AI".
# They count as allowed, and are hidden before looking for bans so they can't count as one.
NEGATED_BAN_PATTERNS = [
    rf"\b{AI}\b{GAP}\b(?:is|are)\s+not\s+(?:forbidden|prohibited|banned|disallowed)\b",
    rf"\b(?:do|does|will)\s+not\s+(?:ban|prohibit|forbid|limit|restrict)\b{GAP}\b{AI}\b",
    rf"\b(?:don'?t|doesn'?t|won'?t|never)\s+(?:ban|prohibit|forbid|limit|restrict)\b{GAP}\b{AI}\b",
]

ALLOWED_PATTERNS = NEGATED_BAN_PATTERNS + [
    rf"\b(?:use|usage)\s+of\s+{AI}\b{GAP}\b(?:is|are)\s+(?:allowed|permitted|welcome|encouraged|fine|ok)\b",
    rf"\b{AI}\b\s+(?:is|are)\s+(?:allowed|permitted|welcome|encouraged|fine|ok)\b",
    rf"\b(?:allowed|permitted|free|welcome)\s+to\s+use\s+{AI}\b",
    rf"\bany\s+tools?\b{GAP}\bincluding\s+{AI}\b",
    rf"\b(?:leverage|use)\s+{AI}\s+(?:as\s+part|in\s+your|to\s+help)\b",
]

BANNED_PATTERNS = [
    rf"\b{AI}\b{GAP}\b(?:is|are|will\s+be)\s+(?:strictly\s+)?(?:prohibited|forbidden|banned|disallowed|not\s+allowed|not\s+permitted)\b",
    rf"\b(?:solving|use|usage)\b{GAP}\b{AI}\b{GAP}\b(?:is|are)\s+(?:strictly\s+)?(?:prohibited|forbidden|banned|not\s+allowed|not\s+permitted)\b",
    rf"\b(?:no|without(?:\s+any)?)\s+{AI}\b(?!\s*/)",
    rf"\b{AI}[-\s]free\b",
    rf"\b{AI}\s+usage\b{GAP}\bresult\s+in\b{GAP}\b(?:disqualification|ban)",
    rf"\b(?:prohibit|forbid|ban)s?\s+(?:the\s+)?(?:use\s+of\s+)?{AI}\b",
    rf"\b{AI}\b{GAP}\bbut\s+(?:strictly\s+)?(?:prohibited|forbidden|banned|not\s+allowed|not\s+permitted)\b",
]

_SEPARATE = [re.compile(p, re.I) for p in SEPARATE_PATTERNS]
_ALLOWED = [re.compile(p, re.I) for p in ALLOWED_PATTERNS]
_BANNED = [re.compile(p, re.I) for p in BANNED_PATTERNS]
_NEGATED_BANS = [re.compile(p, re.I) for p in NEGATED_BAN_PATTERNS]


def classify(event: dict) -> str:
    """Return one of ALLOWED, BANNED, SEPARATE, MIXED or NOT_STATED for a CTFtime event.
    Uses the CTFtime description first, then a result from the CTF's website if the bot found one."""
    result = classify_text(f"{event.get('description') or ''} {event.get('restrictions') or ''}")
    if result == NOT_STATED:
        return event.get("_ai_policy_website", NOT_STATED)
    return result


def from_website(event: dict) -> bool:
    """True if the policy came from the CTF's own website rather than CTFtime."""
    return (classify_text(f"{event.get('description') or ''} {event.get('restrictions') or ''}") == NOT_STATED
            and event.get("_ai_policy_website", NOT_STATED) != NOT_STATED)


def classify_text(text: str) -> str:
    text = " ".join(text.split())

    if any(rx.search(text) for rx in _SEPARATE):
        return SEPARATE

    allowed = any(rx.search(text) for rx in _ALLOWED)
    # Hide "AI is not forbidden" before looking for bans, so it can't count as one.
    for rx in _NEGATED_BANS:
        text = rx.sub(" ", text)
    banned = any(rx.search(text) for rx in _BANNED)

    if allowed and banned:
        return MIXED
    if allowed:
        return ALLOWED
    if banned:
        return BANNED
    return NOT_STATED


def label(event: dict) -> str:
    return LABELS[classify(event)] + (" (from website)" if from_website(event) else "")
