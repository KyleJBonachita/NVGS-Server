export function chatCompletionsUrl(baseUrl) {
  const trimmed = String(baseUrl || "").replace(/\/+$/, "");
  const apiRoot = /\/v1$/i.test(trimmed) ? trimmed : `${trimmed}/v1`;
  return `${apiRoot}/chat/completions`;
}

export async function askLmStudio({
  baseUrl,
  model,
  apiKey = "",
  systemPrompt,
  userPrompt,
  maxTokens = 450,
  temperature = 0.2,
}) {
  const url = chatCompletionsUrl(baseUrl);
  const headers = { "Content-Type": "application/json" };
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model,
      temperature,
      max_tokens: maxTokens,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
    }),
    signal: AbortSignal.timeout(45_000),
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Model endpoint returned ${response.status}: ${details.slice(0, 300)}`);
  }

  const json = await response.json();
  return json?.choices?.[0]?.message?.content?.trim() || "";
}
