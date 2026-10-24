import re

_VERBS = r"(send|email|text|call|contact|approve|apply|issue|grant|refund|execute|deploy)"
_IMPERATIVE = re.compile(
    rf"^(please\s+|can you\s+|could you\s+|go ahead and\s+|just\s+)?{_VERBS}\b", re.I)
_URGENT = re.compile(r"\b(now|immediately|right away)\b", re.I)
_VERB_ANY = re.compile(rf"\b{_VERBS}\b", re.I)

_INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)"
    r"|disregard (the |all |any )?(previous|prior|above|rules|policy)"
    r"|system prompt|override|act as|you (must|should) now"
    r"|approve (all|every)|reveal .*(password|secret|key)", re.I)

DECLINE_TEXT = ("I can only recommend actions. I can't send offers, contact customers "
                "or approve spend. Recommendations are saved as 'pending review' for a "
                "human reviewer to approve.")


def is_action_request(text):
    t = text.strip()
    return bool(_IMPERATIVE.search(t) or (_VERB_ANY.search(t) and _URGENT.search(t)))


def is_injected(text):
    """Retrieved documents are evidence only. Flag text that tries to give orders."""
    return bool(_INJECTION.search(text or ""))