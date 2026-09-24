import re
ALLOWED = 'allowed'
BANNED = 'banned'
SEPARATE = 'separate'
MIXED = 'mixed'
NOT_STATED = 'not_stated'
LABELS = {ALLOWED: '🤖 AI allowed', BANNED: '🚫 No AI', SEPARATE: '⚖️ Separate AI / human leaderboards', MIXED: '⚠️ Mixed AI rules, check the rules', NOT_STATED: '❔ AI policy not stated'}
AI = '(?:ai|a\\.i\\.|llms?|chatgpt|gpt(?:-?\\d+)?|claude|gemini|copilot|genai|generative ai|artificial intelligence|large language models?|ai agents?|ai tools?|ai assistance|agents?)'
GAP = '[^.!?\\n]{0,60}?'
SEPARATE_PATTERNS = [f'\\b(?:separate|two|different|dual)\\b{GAP}\\b(?:ai|human)\\b{GAP}\\b(?:leaderboards?|scoreboards?|brackets?|divisions?|tracks?|categories)\\b', '\\bai\\s*/\\s*human\\b|\\bhuman\\s*/\\s*ai\\b', '\\bhumans?\\b.{0,160}?\\bcyborgs?\\b']
NEGATED_BAN_PATTERNS = [f'\\b{AI}\\b{GAP}\\b(?:is|are)\\s+not\\s+(?:forbidden|prohibited|banned|disallowed)\\b', f'\\b(?:do|does|will)\\s+not\\s+(?:ban|prohibit|forbid|limit|restrict)\\b{GAP}\\b{AI}\\b', f"\\b(?:don'?t|doesn'?t|won'?t|never)\\s+(?:ban|prohibit|forbid|limit|restrict)\\b{GAP}\\b{AI}\\b"]
ALLOWED_PATTERNS = NEGATED_BAN_PATTERNS + [f'\\b(?:use|usage)\\s+of\\s+{AI}\\b{GAP}\\b(?:is|are)\\s+(?:allowed|permitted|welcome|encouraged|fine|ok)\\b', f'\\b{AI}\\b\\s+(?:is|are)\\s+(?:allowed|permitted|welcome|encouraged|fine|ok)\\b', f'\\b(?:allowed|permitted|free|welcome)\\s+to\\s+use\\s+{AI}\\b', f'\\bany\\s+tools?\\b{GAP}\\bincluding\\s+{AI}\\b', f'\\b(?:leverage|use)\\s+{AI}\\s+(?:as\\s+part|in\\s+your|to\\s+help)\\b']
BANNED_PATTERNS = [f'\\b{AI}\\b{GAP}\\b(?:is|are|will\\s+be)\\s+(?:strictly\\s+)?(?:prohibited|forbidden|banned|disallowed|not\\s+allowed|not\\s+permitted)\\b', f'\\b(?:solving|use|usage)\\b{GAP}\\b{AI}\\b{GAP}\\b(?:is|are)\\s+(?:strictly\\s+)?(?:prohibited|forbidden|banned|not\\s+allowed|not\\s+permitted)\\b', f'\\b(?:no|without(?:\\s+any)?)\\s+{AI}\\b(?!\\s*/)', f'\\b{AI}[-\\s]free\\b', f'\\b{AI}\\s+usage\\b{GAP}\\bresult\\s+in\\b{GAP}\\b(?:disqualification|ban)', f'\\b(?:prohibit|forbid|ban)s?\\s+(?:the\\s+)?(?:use\\s+of\\s+)?{AI}\\b', f'\\b{AI}\\b{GAP}\\bbut\\s+(?:strictly\\s+)?(?:prohibited|forbidden|banned|not\\s+allowed|not\\s+permitted)\\b']
_SEPARATE = [re.compile(p, re.I) for p in SEPARATE_PATTERNS]
_ALLOWED = [re.compile(p, re.I) for p in ALLOWED_PATTERNS]
_BANNED = [re.compile(p, re.I) for p in BANNED_PATTERNS]
_NEGATED_BANS = [re.compile(p, re.I) for p in NEGATED_BAN_PATTERNS]

def classify(event: dict) -> str:
    result = classify_text(f"{event.get('description') or ''} {event.get('restrictions') or ''}")
    if result == NOT_STATED:
        return event.get('_ai_policy_website', NOT_STATED)
    return result

def from_website(event: dict) -> bool:
    return classify_text(f"{event.get('description') or ''} {event.get('restrictions') or ''}") == NOT_STATED and event.get('_ai_policy_website', NOT_STATED) != NOT_STATED

def classify_text(text: str) -> str:
    text = ' '.join(text.split())
    if any((rx.search(text) for rx in _SEPARATE)):
        return SEPARATE
    allowed = any((rx.search(text) for rx in _ALLOWED))
    for rx in _NEGATED_BANS:
        text = rx.sub(' ', text)
    banned = any((rx.search(text) for rx in _BANNED))
    if allowed and banned:
        return MIXED
    if allowed:
        return ALLOWED
    if banned:
        return BANNED
    return NOT_STATED

def label(event: dict) -> str:
    return LABELS[classify(event)] + (' (from website)' if from_website(event) else '')