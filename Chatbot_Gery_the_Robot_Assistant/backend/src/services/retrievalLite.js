const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "did", "do", "does",
  "for", "from", "how", "i", "in", "is", "it", "me", "my", "not", "of", "on", "or", "our",
  "please", "that", "the", "this", "to", "was", "we", "what", "when", "where", "which", "with",
  "would", "you", "your",
]);

// These describe the user's intent but not the affected device or workflow. They
// may influence ranking, but they can never select an answer on their own.
const GENERIC_INTENT_WORDS = new Set([
  "again", "broken", "explain", "fail", "fix", "handle", "help", "issue", "next",
  "problem", "still", "then", "troubleshoot", "unable", "work",
]);

const TOKEN_ALIASES = new Map([
  ["0", "zero"],
  ["cameras", "camera"],
  ["couldnt", "unable"],
  ["didnt", "fail"],
  ["doesnt", "fail"],
  ["failed", "fail"],
  ["failing", "fail"],
  ["fails", "fail"],
  ["issues", "issue"],
  ["problems", "problem"],
  ["trackers", "tracker"],
  ["tracking", "tracker"],
  ["troubleshooting", "troubleshoot"],
  ["webcam", "camera"],
  ["worked", "work"],
  ["working", "work"],
  ["works", "work"],
]);

export function normalizeText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function canonicalToken(word) {
  return TOKEN_ALIASES.get(word) || word;
}

export function tokenize(text) {
  return normalizeText(text)
    .split(" ")
    .filter((word) => word.length > 1 && !STOP_WORDS.has(word))
    .map(canonicalToken);
}

function entryFields(entry) {
  const questions = Array.isArray(entry.questions) ? entry.questions : [];
  const keywords = Array.isArray(entry.keywords) ? entry.keywords.join(" ") : "";
  return {
    title: new Set(tokenize(entry.title)),
    questions: new Set(tokenize(questions.join(" "))),
    keywords: new Set(tokenize(keywords)),
    answer: new Set(tokenize(entry.answer)),
    all: new Set(tokenize([entry.title, questions.join(" "), keywords, entry.answer].join(" "))),
    normalizedQuestions: questions.map(normalizeText),
  };
}

function corpusStats(entries) {
  const fields = entries.map(entryFields);
  const frequencies = new Map();
  for (const field of fields) {
    for (const token of field.all) {
      frequencies.set(token, (frequencies.get(token) || 0) + 1);
    }
  }
  return { fields, frequencies };
}

function inverseDocumentFrequency(token, frequencies, documentCount) {
  const frequency = frequencies.get(token) || 0;
  return Math.log((documentCount + 1) / (frequency + 1)) + 1;
}

function scoreEntry(question, entry, fields, frequencies, documentCount) {
  const normalizedQuestion = normalizeText(question);
  const queryTokens = [...new Set(tokenize(question))];
  const specificTokens = queryTokens.filter((token) => !GENERIC_INTENT_WORDS.has(token));
  let score = 0;
  let specificMatches = 0;

  for (const token of queryTokens) {
    const isSpecific = !GENERIC_INTENT_WORDS.has(token);
    const idf = inverseDocumentFrequency(token, frequencies, documentCount);
    let tokenScore = 0;
    if (fields.title.has(token)) tokenScore = 12;
    else if (fields.questions.has(token)) tokenScore = 7;
    else if (fields.keywords.has(token)) tokenScore = 5;
    else if (fields.answer.has(token)) tokenScore = 2;

    if (tokenScore > 0) {
      score += tokenScore * idf * (isSpecific ? 1 : 0.15);
      if (isSpecific) specificMatches += 1;
    }
  }

  const normalizedTitle = normalizeText(entry.title);
  const exactTitle = normalizedTitle === normalizedQuestion;
  const exactQuestion = fields.normalizedQuestions.includes(normalizedQuestion);
  if (exactTitle) score += 45;
  if (exactQuestion) score += 50;
  if (
    normalizedQuestion.length >= 4 &&
    (normalizedTitle.includes(normalizedQuestion) || normalizedQuestion.includes(normalizedTitle))
  ) {
    score += 20;
  }

  const specificCoverage = specificTokens.length ? specificMatches / specificTokens.length : 0;
  score += specificCoverage * 16;
  if (specificTokens.some((token) => fields.title.has(token))) score += 10;

  return {
    score,
    specificMatches,
    specificCoverage,
    exactMatch: exactTitle || exactQuestion,
    querySpecificTokenCount: specificTokens.length,
  };
}

export function rankKnowledge(question, entries, limit = 5) {
  const safeEntries = Array.isArray(entries) ? entries : [];
  const { fields, frequencies } = corpusStats(safeEntries);
  return safeEntries
    .map((entry, index) => ({
      ...entry,
      ...scoreEntry(question, entry, fields[index], frequencies, safeEntries.length),
    }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

function contextAnswer(contextEntry) {
  return {
    reply: `Staying with “${contextEntry.title}”:\n\n${contextEntry.answer}`,
    sources: [contextEntry.source],
    score: 0,
    entryId: contextEntry.id,
    answerMode: "conversation-context",
  };
}

function clarificationAnswer() {
  return {
    reply: "Which device, system, or workflow is having the problem? For example, say ‘VIVE tracker’, ‘teleop camera’, or the exact error shown. I will only choose an answer when the topic is clear.",
    sources: [],
    score: 0,
    entryId: null,
    answerMode: "clarification",
  };
}

export function findStoredAnswer(question, entries, { contextEntryId = null } = {}) {
  const safeEntries = Array.isArray(entries) ? entries : [];
  const specificTokens = [...new Set(tokenize(question))]
    .filter((token) => !GENERIC_INTENT_WORDS.has(token));
  const contextEntry = contextEntryId
    ? safeEntries.find((entry) => entry.id === contextEntryId)
    : null;

  if (!specificTokens.length) {
    if (contextEntry) return contextAnswer(contextEntry);
    return safeEntries.length ? clarificationAnswer() : null;
  }

  const ranked = rankKnowledge(question, safeEntries, 3);
  const best = ranked[0];
  const second = ranked[1];
  const requiredScore = specificTokens.length === 1 ? 24 : 28;
  const ambiguous = Boolean(
    second &&
    !best?.exactMatch &&
    second.specificMatches >= best.specificMatches &&
    second.score >= best.score * 0.88
  );

  if (
    !best ||
    best.specificMatches < 1 ||
    best.score < requiredScore ||
    (specificTokens.length > 1 && best.specificCoverage < 0.5) ||
    ambiguous
  ) {
    return ambiguous ? clarificationAnswer() : null;
  }

  return {
    reply: best.answer,
    sources: [best.source],
    score: best.score,
    entryId: best.id,
    answerMode: "stored-knowledge",
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
