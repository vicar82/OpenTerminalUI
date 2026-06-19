from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _text(value: object) -> str:
    return str(value or "")


def _fallback_substring(items: list[dict], query: str, k: int) -> list[dict]:
    needle = query.casefold().strip()
    if not needle:
        return []
    matches: list[dict] = []
    for item in items:
        haystack = f"{_text(item.get('title'))} {_text(item.get('abstract'))}".casefold()
        if needle in haystack:
            matched = dict(item)
            matched["score"] = 1.0
            matches.append(matched)
        if len(matches) >= k:
            break
    return matches


def search_items(items: list[dict], query: str, k: int = 10) -> list[dict]:
    if not items or not query.strip() or k <= 0:
        return []

    try:
        corpus = [f"{_text(item.get('title'))}. {_text(item.get('abstract'))}" for item in items]
        vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
        matrix = vectorizer.fit_transform(corpus)
        query_vector = vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, matrix).ravel()

        ranked: list[tuple[int, float]] = sorted(
            ((idx, float(score)) for idx, score in enumerate(similarities) if score > 0),
            key=lambda pair: pair[1],
            reverse=True,
        )
        results: list[dict] = []
        for idx, score in ranked[:k]:
            item = dict(items[idx])
            item["score"] = float(round(score, 4))
            results.append(item)
        return results
    except Exception:
        return _fallback_substring(items, query, k)
