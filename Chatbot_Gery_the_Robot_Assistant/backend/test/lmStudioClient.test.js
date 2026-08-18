import test from "node:test";
import assert from "node:assert/strict";
import { chatCompletionsUrl } from "../src/services/lmStudioClient.js";

test("adds the OpenAI-compatible v1 path when the base URL omits it", () => {
  assert.equal(
    chatCompletionsUrl("http://host.docker.internal:1234/"),
    "http://host.docker.internal:1234/v1/chat/completions",
  );
});

test("does not duplicate v1 when a provider base URL already includes it", () => {
  assert.equal(
    chatCompletionsUrl("https://ai.internal.example/v1"),
    "https://ai.internal.example/v1/chat/completions",
  );
});
