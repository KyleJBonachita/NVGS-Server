import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPreprocessingPrompts,
  buildSystemPrompt,
} from "../src/utils/promptBuilder.js";

test("live AI prompt requires complete operational SOP details", () => {
  const prompt = buildSystemPrompt();
  assert.match(prompt, /operational SOP/i);
  assert.match(prompt, /exact command/i);
  assert.match(prompt, /validation check/i);
  assert.match(prompt, /escalation instruction/i);
  assert.match(prompt, /focused clarification question/i);
});

test("ingestion AI is limited to search metadata and cannot rewrite the source", () => {
  const prompts = buildPreprocessingPrompts({
    title: "VIVE recovery",
    text: "1. Stop collection.\n2. Restart the tracker service.",
  });
  assert.match(prompts.systemPrompt, /search metadata/i);
  assert.match(prompts.systemPrompt, /Do not rewrite, summarize, or answer/i);
  assert.doesNotMatch(prompts.systemPrompt, /"answer"/i);
});
