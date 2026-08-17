const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from",
  "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "please",
  "the", "this", "to", "we", "what", "when", "where", "which", "with", "you", "your",
]);

export function normalizeText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function tokenize(text) {
  return normalizeText(text)
    .split(" ")
    .filter((word) => word.length > 1 && !STOP_WORDS.has(word));
}

function overlapCount(queryTokens, value) {
  const valueTokens = new Set(tokenize(value));
  return queryTokens.reduce((total, token) => total + (valueTokens.has(token) ? 1 : 0), 0);
}

function scoreEntry(question, entry) {
  const normalizedQuestion = normalizeText(question);
  const queryTokens = [...new Set(tokenize(question))];
  if (!queryTokens.length) {
    return 0;
  }

  const questions = Array.isArray(entry.questions) ? entry.questions : [];
  const keywords = Array.isArray(entry.keywords) ? entry.keywords.join(" ") : "";
  let score = 0;

  if (normalizeText(entry.title) === normalizedQuestion) score += 24;
  if (normalizeText(entry.title).includes(normalizedQuestion)) score += 10;

  for (const candidate of questions) {
    const normalizedCandidate = normalizeText(candidate);
    if (normalizedCandidate === normalizedQuestion) score += 30;
    else if (normalizedCandidate.includes(normalizedQuestion) || normalizedQuestion.includes(normalizedCandidate)) {
      score += 12;
    }
  }

  score += overlapCount(queryTokens, entry.title) * 7;
  score += questions.reduce((total, value) => total + overlapCount(queryTokens, value) * 5, 0);
  score += overlapCount(queryTokens, keywords) * 4;
  score += overlapCount(queryTokens, entry.answer) * 1.5;

  const searchable = normalizeText(
    [entry.title, questions.join(" "), keywords, entry.answer].join(" ")
  );
  const coverage = queryTokens.filter((token) => searchable.includes(token)).length / queryTokens.length;
  score += coverage * 10;

  return score;
}

export function rankKnowledge(question, entries, limit = 5) {
  return entries
    .map((entry) => ({ ...entry, score: scoreEntry(question, entry) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export function findStoredAnswer(question, entries) {
  const ranked = rankKnowledge(question, entries, 3);
  const best = ranked[0];
  const queryTokenCount = new Set(tokenize(question)).size;
  const requiredScore = queryTokenCount <= 1 ? 16 : 13;

  if (!best || best.score < requiredScore) {
    return null;
  }

  return {
    reply: best.answer,
    sources: [...new Set(ranked.filter((item) => item.score >= best.score * 0.72).map((item) => item.source))],
    score: best.score,
    entryId: best.id,
  };
}

// Backwards-compatible helper used by the optional live-AI fallback.
export function findRelevantSections(question, entries, maxSections = 5, maxChars = 8000) {
  const ranked = rankKnowledge(question, entries, maxSections * 2);
  const selected = [];
  let charCount = 0;

  for (const item of ranked) {
    const text = item.answer || "";
    if (selected.length >= maxSections || charCount + text.length > maxChars) {
      continue;
    }
    selected.push({ source: item.source, text, title: item.title });
    charCount += text.length;
  }

  return selected;
}
