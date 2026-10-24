import re
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HEADING = re.compile(r"^(\d)\.\s+([A-Z].+)$", re.MULTILINE)
MIN_SCORE = 0.10   # below this, a result counts as irrelevant

SYNONYMS = {
    "complaint": "open complaint service first escalate",
    "unsubscribe": "opted out contact consent",
    "stop": "opted out contact consent",
    "discount": "offer eligibility budget",
    "voucher": "offer eligibility budget",
    "season": "seasonal declines previous year",
    "new": "new customers missing data insufficient history",
    "approve": "human review pending escalation",
    "send": "human review pending never send offers",
}


def load_chunks(pdf_path="docs/retention_policy.pdf"):
    chunks = []
    for page_no, page in enumerate(PdfReader(pdf_path).pages, start=1):
        text = page.extract_text() or ""
        found = list(HEADING.finditer(text))
        for i, m in enumerate(found):
            end = found[i + 1].start() if i + 1 < len(found) else len(text)
            chunks.append({
                "section": int(m.group(1)),
                "title": m.group(2).strip(),
                "page": page_no,
                "text": " ".join(text[m.end():end].split()),
                "ref": f"Policy §{m.group(1)}, p.{page_no}",
            })
    return chunks


class PolicyIndex:
    def __init__(self, pdf_path="docs/retention_policy.pdf"):
        self.chunks = load_chunks(pdf_path)
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vec.fit_transform(
            [c["title"] + " " + c["text"] for c in self.chunks])

    def search(self, query, k=2):
        scores = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        ranked = sorted(zip(scores, self.chunks), key=lambda x: -x[0])[:k]
        return [{**c, "score": round(float(s), 3)} for s, c in ranked]


def _rewrite(query, attempt):
    q = query.lower()
    if attempt == 1:   # add policy vocabulary for words we recognise
        extra = " ".join(v for key, v in SYNONYMS.items() if key in q)
        return f"{query} {extra}".strip()
    return " ".join(w for w in q.split() if len(w) > 4)   # keep key words only


def retrieve(index, query, max_rewrites=2):
    """Search, grade, and rewrite up to max_rewrites times."""
    attempts = []
    current = query
    for attempt in range(max_rewrites + 1):
        hits = index.search(current)
        best = hits[0]["score"] if hits else 0.0
        attempts.append({"query": current, "best_score": best})
        if best >= MIN_SCORE:
            good = [h for h in hits if h["score"] >= MIN_SCORE]
            return {"status": "found", "hits": good, "attempts": attempts}
        if attempt < max_rewrites:
            current = _rewrite(query, attempt + 1)
    return {"status": "not_found", "hits": [], "attempts": attempts,
            "reason": "No policy section matched this question after rewrites."}