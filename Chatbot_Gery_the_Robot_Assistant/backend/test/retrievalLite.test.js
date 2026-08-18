import test from "node:test";
import assert from "node:assert/strict";
import { findStoredAnswer, rankKnowledge } from "../src/services/retrievalLite.js";

const entries = [
  {
    id: "vive",
    source: "vive-setup.md",
    title: "VIVE tracker setup",
    answer: "Start the Windows VIVE Server, then confirm Ubuntu receives tracker data.",
    questions: ["How do I set up the VIVE trackers?", "Why is the tracker still zero?"],
    keywords: ["vive", "tracker", "windows", "ubuntu"],
  },
  {
    id: "password",
    source: "accounts.md",
    title: "Password reset",
    answer: "Ask the Tech Team to reset the account.",
    questions: ["How do I reset my password?"],
    keywords: ["password", "account"],
  },
];

const troubleshootingEntries = [
  {
    id: "vive-zero",
    source: "troubleshooting.md",
    title: "VIVE tracker still detected as 0",
    answer: "Restart the tracker service, re-pair the tracker, and re-run detection.",
    questions: ["How do I fix VIVE tracker still detected as 0?", "VIVE tracker still detected as 0 is not working"],
    keywords: ["vive", "tracker", "zero", "binding", "detection"],
  },
  {
    id: "teleop-camera",
    source: "troubleshooting.md",
    title: "Teleop not working and camera is black",
    answer: "Check camera permissions, restart the camera stream, and relaunch teleop.",
    questions: ["How do I fix teleop not working and camera is black?"],
    keywords: ["teleop", "camera", "black", "permissions", "stream"],
  },
];

test("returns a saved answer for a paraphrased knowledge question", () => {
  const result = findStoredAnswer("My VIVE tracker is showing zero", entries);
  assert.equal(result?.entryId, "vive");
  assert.equal(result?.sources[0], "vive-setup.md");
});

test("does not invent a match for an unrelated question", () => {
  assert.equal(findStoredAnswer("What is today's cafeteria menu?", entries), null);
});

test("ranks exact representative questions first", () => {
  assert.equal(rankKnowledge("How do I reset my password?", entries)[0].id, "password");
});

test("prioritizes the named VIVE device over generic not-working words", () => {
  const result = findStoredAnswer("VIVE is not working", troubleshootingEntries);
  assert.equal(result?.entryId, "vive-zero");
  assert.match(result?.reply, /tracker service/i);
});

test("uses distinctive camera symptoms to select teleop troubleshooting", () => {
  const result = findStoredAnswer("The camera is black", troubleshootingEntries);
  assert.equal(result?.entryId, "teleop-camera");
});

test("asks for the affected topic instead of guessing from generic words", () => {
  const result = findStoredAnswer("It is not working", troubleshootingEntries);
  assert.equal(result?.answerMode, "clarification");
  assert.equal(result?.entryId, null);
});

test("keeps a vague follow-up on the previous knowledge topic", () => {
  const result = findStoredAnswer("That still did not work", troubleshootingEntries, {
    contextEntryId: "vive-zero",
  });
  assert.equal(result?.entryId, "vive-zero");
  assert.equal(result?.answerMode, "conversation-context");
});
