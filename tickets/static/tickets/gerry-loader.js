(function () {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 1400);

  fetch("/gerry/health", {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal: controller.signal,
  })
    .then((response) => {
      if (!response.ok) throw new Error("offline");
      return response.json();
    })
    .then((health) => {
      if (!health.ok) return;
      window.GeryWidgetConfig = {
        apiBase: "/gerry",
        title: "Gery Robot Assistant",
      };
      const script = document.createElement("script");
      script.src = "/gerry/widget-embed.js?v=2";
      script.async = true;
      document.head.appendChild(script);
    })
    .catch(() => undefined)
    .finally(() => window.clearTimeout(timeout));
})();
