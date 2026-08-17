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
