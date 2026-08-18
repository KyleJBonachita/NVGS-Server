import test from "node:test";
import assert from "node:assert/strict";
import {
  continueGuidedTroubleshooting,
  extractTroubleshootingFlow,
  isTroubleshootingRequest,
  startGuidedTroubleshooting,
} from "../src/services/guidedTroubleshooting.js";

const viveSop = [
  "Issue:",
  "VIVE trackers are not detected.",
  "",
  "Troubleshooting:",
  "1. Completely close VIVE Server, then start it again. When many trackers are connected, a full restart may be required to detect new trackers.",
  "   Confirm: Are all expected trackers detected after restarting VIVE Server?",
  "2. Restart the tracker laptop.",
  "   Confirm: Are all expected trackers detected after the laptop restarts?",
  "3. Verify that the configured IP address matches the approved VIVE setup.",
  "   Confirm: Is the configured IP address correct and are the trackers detected?",
  "",
  "Escalation:",
  "- Send the VIVE Server log and configured IP address to the Tech Team.",
].join("\n");

function viveEntry() {
  const flow = extractTroubleshootingFlow(viveSop);
  return {
    id: "vive-flow",
    sourceId: "uploaded:vive.md",
    source: "vive.md",
    title: "VIVE trackers not detected",
    sectionTitle: "VIVE trackers not detected",
    answer: viveSop,
    canonicalAnswer: viveSop,
    troubleshootingSteps: flow.steps,
    troubleshootingEscalation: flow.escalation,
  };
}

test("extracts ordered checks, confirmation questions, and escalation from an SOP", () => {
  const flow = extractTroubleshootingFlow(viveSop);
  assert.equal(flow.steps.length, 3);
  assert.match(flow.steps[0].instruction, /Completely close VIVE Server/);
  assert.equal(
    flow.steps[0].confirmation,
    "Are all expected trackers detected after restarting VIVE Server?",
  );
  assert.match(flow.steps[2].instruction, /configured IP address/);
  assert.match(flow.escalation, /VIVE Server log/);
});

test("recognizes a troubleshooting request without using AI", () => {
  assert.equal(isTroubleshootingRequest("My VIVE trackers are not working"), true);
  assert.equal(isTroubleshootingRequest("Show me the VIVE architecture overview"), false);
});

test("guides an agent through one documented check at a time and remembers progress", () => {
  const entry = viveEntry();
  const entries = [entry];

  const started = startGuidedTroubleshooting(entry);
  assert.match(started.reply, /Check 1 of 3/);
  assert.match(started.reply, /Completely close VIVE Server/);
  assert.equal(started.troubleshootingState.phase, "status");
  assert.equal(started.usedAI, false);

  const notTried = continueGuidedTroubleshooting(
    "Not tried yet",
    started.troubleshootingState,
    entries,
  );
  assert.match(notTried.reply, /Are all expected trackers detected/);
  assert.equal(notTried.troubleshootingState.phase, "result");

  const stillBroken = continueGuidedTroubleshooting(
    "No - still not working",
    notTried.troubleshootingState,
    entries,
  );
  assert.match(stillBroken.reply, /Check 2 of 3/);
  assert.match(stillBroken.reply, /Restart the tracker laptop/);

  const triedLaptop = continueGuidedTroubleshooting(
    "Tried - still not working",
    stillBroken.troubleshootingState,
    entries,
  );
  assert.match(triedLaptop.reply, /Check 3 of 3/);
  assert.match(triedLaptop.reply, /configured IP address/);

  const solved = continueGuidedTroubleshooting(
    "Yes - problem solved",
    triedLaptop.troubleshootingState,
    entries,
  );
  assert.equal(solved.answerMode, "guided-troubleshooting-resolved");
  assert.equal(solved.troubleshootingState, null);
  assert.match(solved.reply, /Problem resolved at check 3/);
});

test("exhausting the checks returns the documented escalation instead of inventing another fix", () => {
  const entry = viveEntry();
  const response = continueGuidedTroubleshooting(
    "No - still not working",
    { version: 1, entryId: entry.id, stepIndex: 2, phase: "result" },
    [entry],
  );
  assert.equal(response.answerMode, "guided-troubleshooting-exhausted");
  assert.equal(response.troubleshootingState, null);
  assert.match(response.reply, /Send the VIVE Server log/);
  assert.doesNotMatch(response.reply, /reinstall|factory reset/i);
});

test("full SOP remains available without losing the current guided step", () => {
  const entry = viveEntry();
  const response = continueGuidedTroubleshooting(
    "Show full SOP",
    { version: 1, entryId: entry.id, stepIndex: 1, phase: "status" },
    [entry],
  );
  assert.equal(response.answerMode, "guided-troubleshooting-full-sop");
  assert.equal(response.troubleshootingState.stepIndex, 1);
  assert.match(response.reply, /Full approved SOP/);
  assert.match(response.reply, /Your guided session is still waiting at check 2/);
});
