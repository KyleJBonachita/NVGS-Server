export function buildSystemPrompt() {
  return [
    'You are "Gery - The Gr00t Robot Assistant".',
    "Answer only from the supplied internal knowledge.",
    "Keep the answer concise, structured, and operationally safe.",
    "Do not invent undocumented NVIDIA, robot, network, or security details.",
    'If the context is insufficient, answer exactly: "I am not sure based on current internal documentation. Please file an NVGS ticket or contact the Tech Team or your Team Lead."',
  ].join(" ");
}

export function buildUserPrompt(question, contextSections) {
  const contextText = contextSections
    .map((section, index) => `[Source ${index + 1}: ${section.source}]\n${section.text}`)
    .join("\n\n");

  return [
    "User question:",
    question,
    "",
    "Internal knowledge:",
    contextText || "(No matching knowledge found)",
  ].join("\n");
}

export function buildPreprocessingPrompts(section) {
  return {
    systemPrompt: [
      "You prepare reusable internal knowledge for a token-free retrieval chatbot.",
      "Use only the supplied document section.",
      "Return one JSON object and no markdown.",
      'Schema: {"answer":"concise reusable answer","questions":["3 to 8 likely user questions"],"keywords":["important terms"]}.',
      "Preserve warnings, prerequisites, exact commands, and escalation instructions.",
      "Never add facts that are not present in the section.",
    ].join(" "),
    userPrompt: `Section title: ${section.title}\n\nSection content:\n${section.text}`,
  };
}
