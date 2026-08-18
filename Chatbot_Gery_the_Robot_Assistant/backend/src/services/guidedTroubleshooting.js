const ACTION_LABELS = new Set([
  "actions",
  "checks",
  "diagnostic steps",
  "fix",
  "fixes",
  "procedure",
  "recovery",
  "resolution",
  "solution",
  "steps",
  "troubleshooting",
  "troubleshooting steps",
]);

const ESCALATION_LABELS = new Set([
  "escalate",
  "escalation",
  "when to escalate",
]);

const OTHER_LABELS = new Set([
  "cause",
  "expected result",
  "issue",
  "notes",
  "prerequisites",
  "success criteria",
  "system context",
  "symptoms",
  "validation",
  "warnings",
]);

const STATUS_REPLIES = [
  "Not tried yet",
  "Tried - still not working",
  "Tried - problem solved",
  "Show full SOP",
  "Cancel troubleshooting",
];

const RESULT_REPLIES = [
  "Yes - problem solved",
  "No - still not working",
  "I cannot complete this check",
  "Show full SOP",
  "Cancel troubleshooting",
];

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function parseLabel(line) {
  const stripped = String(line || "").trim().replace(/^#{1,6}\s+/, "");
  const match = stripped.match(/^([^:]{2,60}?)(?:\s*:\s*(.*))?$/);
  if (!match) return null;
  const label = match[1].trim().toLowerCase();
  if (ACTION_LABELS.has(label)) return { mode: "actions", remainder: match[2]?.trim() || "" };
  if (ESCALATION_LABELS.has(label)) return { mode: "escalation", remainder: match[2]?.trim() || "" };
  if (OTHER_LABELS.has(label)) return { mode: "other", remainder: match[2]?.trim() || "" };
  return null;
}

function finalizeStep(steps, lines) {
  const text = lines.join("\n").trim();
  if (!text) return;
  const stepLines = text.split("\n");
  let confirmation = "";
  const instructionLines = [];
  for (const line of stepLines) {
    const confirmationMatch = line.trim().match(
      /^(?:confirm|confirmation|question|success criteria|verify result)\s*:\s*(.+)$/i,
    );
    if (confirmationMatch) {
      confirmation = confirmationMatch[1].trim();
    } else {
      instructionLines.push(line);
    }
  }
  const instruction = instructionLines.join("\n").trim();
  if (!instruction) return;
  steps.push({ instruction, confirmation });
}

export function extractTroubleshootingFlow(text) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const steps = [];
  const escalationLines = [];
  let mode = "other";
  let currentStep = [];
  let sawActionLabel = false;

  const flushStep = () => {
    finalizeStep(steps, currentStep);
    currentStep = [];
  };

  for (const rawLine of lines) {
    const label = parseLabel(rawLine);
    if (label) {
      flushStep();
      mode = label.mode;
      if (mode === "actions") sawActionLabel = true;
      if (mode === "actions" && label.remainder) currentStep = [label.remainder];
      if (mode === "escalation" && label.remainder) escalationLines.push(label.remainder);
      continue;
    }

    if (mode === "escalation") {
      const cleaned = rawLine.trim().replace(/^[-*]\s+/, "");
      if (cleaned) escalationLines.push(cleaned);
      continue;
    }

    const ordered = rawLine.match(/^\s*(?:step\s+)?\d+[.):]\s+(.+)$/i);
    const checkbox = rawLine.match(/^\s*[-*]\s+\[[ xX]\]\s+(.+)$/);
    const bullet = rawLine.match(/^(\s*)[-*]\s+(.+)$/);
    if (ordered || checkbox) {
      flushStep();
      mode = "actions";
      currentStep = [(ordered?.[1] || checkbox?.[1] || "").trim()];
      continue;
    }
    if (mode === "actions" && bullet) {
      if (currentStep.length && bullet[1].length > 0) {
        currentStep.push(rawLine.trimEnd());
      } else {
        flushStep();
        currentStep = [bullet[2].trim()];
      }
      continue;
    }
    if (mode === "actions" && currentStep.length) {
      if (rawLine.trim()) currentStep.push(rawLine.trimEnd());
      else if (currentStep.at(-1) !== "") currentStep.push("");
    }
  }
  flushStep();

  const usableSteps = steps
    .filter((step) => step.instruction.length >= 3)
    .slice(0, 24);
  return {
    steps: usableSteps,
    escalation: escalationLines.join("\n").trim(),
    explicitActionSection: sawActionLabel,
  };
}

export function isTroubleshootingRequest(message) {
  const value = normalize(message);
  return /\b(broken|cannot|cant|detect|detected|disconnect|error|fail|failed|failing|fix|issue|not working|offline|problem|stuck|troubleshoot|unable|zero)\b/.test(value);
}

function entryAnswer(entry) {
  return String(entry?.canonicalAnswer || entry?.answer || "").trim();
}

function entryTitle(entry) {
  return String(entry?.sectionTitle || entry?.title || "approved troubleshooting SOP").trim();
}

function validSteps(entry) {
  return Array.isArray(entry?.troubleshootingSteps)
    ? entry.troubleshootingSteps.filter((step) => step?.instruction).slice(0, 24)
    : [];
}

function stateFor(entry, stepIndex, phase) {
  return { version: 1, entryId: entry.id, stepIndex, phase };
}

function responseFor(entry, reply, state, quickReplies, answerMode) {
  return {
    reply,
    sources: [entry.source],
    answerMode,
    usedAI: false,
    contextEntryId: entry.id,
    troubleshootingState: state,
    quickReplies,
  };
}

function checkPrompt(entry, stepIndex, prefix = "") {
  const steps = validSteps(entry);
  const step = steps[stepIndex];
  const lead = prefix ? `${prefix}\n\n` : "";
  return responseFor(
    entry,
    `${lead}Check ${stepIndex + 1} of ${steps.length}\n${step.instruction}\n\nHave you already completed this exact check?`,
    stateFor(entry, stepIndex, "status"),
    STATUS_REPLIES,
    "guided-troubleshooting",
  );
}

function resultPrompt(entry, stepIndex, prefix = "Complete this check now") {
  const steps = validSteps(entry);
  const step = steps[stepIndex];
  const confirmation = step.confirmation || "After completing it, is the original problem solved?";
  return responseFor(
    entry,
    `${prefix}:\n${step.instruction}\n\n${confirmation}`,
    stateFor(entry, stepIndex, "result"),
    RESULT_REPLIES,
    "guided-troubleshooting",
  );
}

function escalationText(entry, reason) {
  const documented = String(entry?.troubleshootingEscalation || "").trim();
  const escalation = documented || "File an NVGS ticket or contact the Tech Team or your Team Lead with the exact symptom and the checks already completed.";
  return `${reason}\n\nEscalation\n${escalation}`;
}

function classifyReply(message, phase) {
  const value = normalize(message);
  if (/\b(show|display|give)\b.*\b(full|complete)\b.*\bsop\b|^show full sop$/.test(value)) return "show-sop";
  if (/\b(cancel|stop|exit|different issue|new issue)\b/.test(value)) return "cancel";
  if (/\b(cannot|cant|unable|blocked|no access|permission denied)\b/.test(value)) return "blocked";

  const unresolved = /\b(still|not fixed|not solved|not resolved|not working|did not work|didnt work|same problem|failed)\b/.test(value);
  if (unresolved) return "unresolved";
  const solved = /\b(problem solved|solved|fixed|resolved|working now|works now|detected now|all detected)\b/.test(value);
  if (solved) return "solved";

  if (/^(yes|y|yep|yeah|done)$/.test(value)) return phase === "result" ? "solved" : "tried";
  if (/^(no|n|nope)$/.test(value)) return phase === "result" ? "unresolved" : "not-tried";
  if (/\b(not yet|havent|have not|never tried|didnt try|did not try)\b/.test(value)) return "not-tried";
  if (/\b(already|completed|done|tried|checked|restarted|verified)\b/.test(value)) return "tried";
  return "unknown";
}

export function startGuidedTroubleshooting(entry) {
  const steps = validSteps(entry);
  if (!steps.length) return null;
  return checkPrompt(
    entry,
    0,
    `I found the approved SOP “${entryTitle(entry)}”. I’ll guide you through one documented check at a time and remember your progress.`,
  );
}

export function continueGuidedTroubleshooting(message, rawState, entries) {
  if (!rawState || typeof rawState !== "object") return null;
  const entryId = String(rawState.entryId || "").slice(0, 100);
  const stepIndex = Number(rawState.stepIndex);
  const phase = rawState.phase === "result" ? "result" : "status";
  const entry = Array.isArray(entries) ? entries.find((candidate) => candidate.id === entryId) : null;
  const steps = validSteps(entry);
  if (!entry || !Number.isInteger(stepIndex) || stepIndex < 0 || stepIndex >= steps.length) {
    return {
      reply: "That troubleshooting session is no longer available because the knowledge library changed. Ask the original issue again to start from the updated SOP.",
      sources: [],
      answerMode: "guided-troubleshooting-expired",
      usedAI: false,
      contextEntryId: null,
      troubleshootingState: null,
      quickReplies: [],
    };
  }

  const classification = classifyReply(message, phase);
  if (classification === "cancel") {
    return responseFor(
      entry,
      "Guided troubleshooting cancelled. Ask about another issue whenever you’re ready.",
      null,
      [],
      "guided-troubleshooting-cancelled",
    );
  }
  if (classification === "show-sop") {
    const quickReplies = phase === "result" ? RESULT_REPLIES : STATUS_REPLIES;
    return responseFor(
      entry,
      `Full approved SOP — ${entryTitle(entry)}\n\n${entryAnswer(entry)}\n\nYour guided session is still waiting at check ${stepIndex + 1} of ${steps.length}.`,
      stateFor(entry, stepIndex, phase),
      quickReplies,
      "guided-troubleshooting-full-sop",
    );
  }
  if (classification === "blocked") {
    return responseFor(
      entry,
      escalationText(entry, `Stop at check ${stepIndex + 1}; do not silently skip a documented check that you cannot complete.`),
      null,
      [],
      "guided-troubleshooting-blocked",
    );
  }
  if (classification === "solved") {
    return responseFor(
      entry,
      `Problem resolved at check ${stepIndex + 1} of ${steps.length}.\n\nSuccessful documented check\n${steps[stepIndex].instruction}`,
      null,
      [],
      "guided-troubleshooting-resolved",
    );
  }
  if (classification === "unresolved") {
    if (stepIndex + 1 < steps.length) {
      return checkPrompt(entry, stepIndex + 1, "That check did not solve the problem. Continue with the next documented check.");
    }
    return responseFor(
      entry,
      escalationText(entry, `The problem remains after all ${steps.length} documented checks.`),
      null,
      [],
      "guided-troubleshooting-exhausted",
    );
  }
  if (classification === "not-tried") {
    return resultPrompt(entry, stepIndex);
  }
  if (classification === "tried") {
    if (phase === "result") {
      return resultPrompt(entry, stepIndex, "Please confirm the result of this completed check");
    }
    return resultPrompt(entry, stepIndex, "You completed this check");
  }

  const expected = phase === "result"
    ? "Reply whether the problem is solved, still not working, or you cannot complete the check."
    : "Reply whether you have not tried it, tried it and the problem remains, or tried it and solved the problem.";
  return responseFor(
    entry,
    `${expected}\n\nCheck ${stepIndex + 1} of ${steps.length}\n${steps[stepIndex].instruction}`,
    stateFor(entry, stepIndex, phase),
    phase === "result" ? RESULT_REPLIES : STATUS_REPLIES,
    "guided-troubleshooting-clarification",
  );
}
