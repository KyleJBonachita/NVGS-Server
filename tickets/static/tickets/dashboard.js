(function () {
  "use strict";

  const state = {
    user: null,
    config: null,
    users: [],
    assignableUsers: [],
    currentView: "overview",
    queueMode: "mine",
    page: 1,
    pageCount: 1,
    currentTicketId: null,
    selectedTicketIds: new Set(),
    analyticsPeriod: 30,
  };

  const byId = function (id) {
    return document.getElementById(id);
  };

  function csrfToken() {
    const cookie = document.cookie
      .split(";")
      .map(function (value) { return value.trim(); })
      .find(function (value) { return value.startsWith("csrftoken="); });
    return cookie ? decodeURIComponent(cookie.slice("csrftoken=".length)) : "";
  }

  function flattenError(value) {
    if (!value) return [];
    if (typeof value === "string") return [value];
    if (Array.isArray(value)) {
      return value.reduce(function (items, entry) {
        return items.concat(flattenError(entry));
      }, []);
    }
    if (typeof value === "object") {
      return Object.keys(value).reduce(function (items, key) {
        return items.concat(flattenError(value[key]));
      }, []);
    }
    return [String(value)];
  }

  async function api(path, options) {
    const requestOptions = Object.assign(
      { credentials: "same-origin", headers: {} },
      options || {}
    );
    requestOptions.headers = Object.assign(
      { Accept: "application/json" },
      requestOptions.headers || {}
    );
    if (requestOptions.body && typeof requestOptions.body !== "string") {
      requestOptions.headers["Content-Type"] = "application/json";
      requestOptions.body = JSON.stringify(requestOptions.body);
    }
    if (requestOptions.method && requestOptions.method !== "GET") {
      requestOptions.headers["X-CSRFToken"] = csrfToken();
    }

    const response = await fetch(path, requestOptions);
    const data = response.status === 204
      ? null
      : await response.json().catch(function () { return null; });
    if (!response.ok) {
      const messages = flattenError(data);
      const message = messages.join(" ") || "The server could not complete this request.";
      if (
        response.status === 401 ||
        (response.status === 403 && /credentials were not provided/i.test(message))
      ) {
        window.location.assign("/login/");
        throw new Error("Your session expired. Sign in again.");
      }
      throw new Error(message);
    }
    return data;
  }

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value == null ? "" : String(value);
    return element.innerHTML;
  }

  function slug(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  function formatDate(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return parsed.toLocaleString("en-PH", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function timeAgo(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    const seconds = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + "m ago";
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + "h ago";
    const days = Math.floor(hours / 24);
    if (days < 30) return days + "d ago";
    return formatDate(value);
  }

  function displayRole(role) {
    return {
      agent: "Agent",
      team: "Tech Team / TL / Manager",
      system_admin: "System administrator",
    }[role] || role;
  }

  function statusBadge(value) {
    return (
      '<span class="status-badge status-' + slug(value) + '">' +
      escapeHtml(value || "Unknown") +
      "</span>"
    );
  }

  function priorityBadge(value) {
    return (
      '<span class="priority-badge priority-' + slug(value) + '">' +
      escapeHtml(value || "—") +
      "</span>"
    );
  }

  function isManager() {
    return Boolean(state.user && ["team", "system_admin"].includes(state.user.role));
  }

  function showToast(message, kind) {
    const toast = document.createElement("div");
    toast.className = "toast " + (kind || "");
    toast.textContent = message;
    byId("toast-region").appendChild(toast);
    window.setTimeout(function () { toast.remove(); }, 4200);
  }

  function showView(name) {
    document.querySelectorAll(".view").forEach(function (view) {
      view.classList.toggle("active", view.id === "view-" + name);
    });
    document.querySelectorAll(".nav-button").forEach(function (button) {
      if (button.dataset.view !== name) {
        button.classList.remove("active");
        return;
      }
      if (name !== "tickets") {
        button.classList.add("active");
        return;
      }
      const teamQueue = button.dataset.teamQueue === "true";
      button.classList.toggle(
        "active",
        state.queueMode === "all" ? teamQueue : !teamQueue
      );
    });
    state.currentView = name;
    byId("sidebar").classList.remove("open");
  }

  function selectOptions(element, values, firstLabel, selectedValue) {
    element.replaceChildren();
    const first = document.createElement("option");
    first.value = "";
    first.textContent = firstLabel;
    element.appendChild(first);
    (values || []).forEach(function (value) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      option.selected = value === selectedValue;
      element.appendChild(option);
    });
  }

  function resetCreateForm() {
    byId("create-ticket-form").reset();
    fillConfiguration();
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    byId("ticket-downtime").value = now.toISOString().slice(0, 16);
    byId("create-error").hidden = true;
  }

  function fillConfiguration() {
    selectOptions(
      byId("ticket-category"),
      state.config.ticket_types,
      "Select issue type"
    );
    selectOptions(
      byId("ticket-priority"),
      state.config.priorities,
      "Select urgency",
      "Moderate"
    );
    selectOptions(
      byId("ticket-workstation"),
      state.config.workstations,
      "Select workstation"
    );
    selectOptions(byId("ticket-location"), state.config.locations, "Select location");
    selectOptions(
      byId("ticket-impact"),
      state.config.impact_levels,
      "Select impact"
    );
    selectOptions(byId("filter-status"), state.config.statuses, "All statuses");
    selectOptions(
      byId("filter-priority"),
      state.config.priorities,
      "All priorities"
    );
    selectOptions(
      byId("filter-category"),
      state.config.ticket_types,
      "All issue types"
    );
    selectOptions(byId("bulk-status"), state.config.statuses, "Select status");
  }

  function fillPeople() {
    const reporterSelect = byId("ticket-reporter");
    state.users
      .filter(function (user) { return user.role === "agent"; })
      .forEach(function (user) {
        const option = document.createElement("option");
        option.value = String(user.id);
        option.textContent = user.display_name + " (" + user.email + ")";
        reporterSelect.appendChild(option);
      });
  }

  function ticketRows(tickets, maximum) {
    const selected = typeof maximum === "number" ? tickets.slice(0, maximum) : tickets;
    if (!selected.length) {
      return (
        '<div class="empty-state compact">' +
        '<span class="empty-icon" aria-hidden="true">✓</span>' +
        "<p>No tickets found.</p></div>"
      );
    }
    return selected.map(function (ticket) {
      const reporter = ticket.reporter ? ticket.reporter.display_name : "Unknown";
      return (
        '<button class="ticket-row" type="button" data-ticket-id="' + ticket.id + '">' +
        '<span class="ticket-row-main"><strong>' + escapeHtml(ticket.title) + "</strong>" +
        '<span class="ticket-meta"><span>' + escapeHtml(ticket.reference) + "</span>" +
        "<span>" + escapeHtml(ticket.workstation || "No workstation") + "</span>" +
        (isManager() ? "<span>" + escapeHtml(reporter) + "</span>" : "") +
        "<span>" + timeAgo(ticket.updated_at) + "</span></span></span>" +
        '<span class="ticket-row-side">' +
        priorityBadge(ticket.priority) + statusBadge(ticket.status) +
        "</span></button>"
      );
    }).join("");
  }

  function attachTicketOpeners(container) {
    container.querySelectorAll("[data-ticket-id]").forEach(function (element) {
      element.addEventListener("click", function (event) {
        if (event.target.closest("[data-select-ticket]")) return;
        openTicket(Number(element.dataset.ticketId));
      });
    });
  }

  async function loadOverview() {
    showView("overview");
    byId("recent-tickets").innerHTML =
      '<div class="loading-card"><span class="spinner"></span><p>Loading tickets…</p></div>';
    try {
      const params = new URLSearchParams();
      if (isManager() && state.queueMode === "mine") {
        params.set("reporter", String(state.user.id));
      }
      const suffix = params.toString() ? "?" + params.toString() : "";
      const results = await Promise.all([
        api("/api/tickets/summary/" + suffix),
        api("/api/tickets/" + suffix),
      ]);
      const summary = results[0];
      const ticketPage = results[1];
      const cards = isManager()
        ? [
          ["Total tickets", summary.total],
          ["Active", summary.active],
          ["Unassigned", summary.unassigned],
          ["Urgent", summary.urgent],
        ]
        : [
          ["Total filed", summary.total],
          ["Active", summary.active],
          ["Resolved", summary.resolved],
          ["Urgent", summary.urgent],
        ];
      byId("summary-cards").innerHTML = cards.map(function (card) {
        return (
          '<article class="summary-card"><span>' + escapeHtml(card[0]) +
          "</span><strong>" + escapeHtml(card[1]) + "</strong></article>"
        );
      }).join("");
      byId("active-ticket-count").textContent = summary.active;
      byId("active-ticket-count").hidden = summary.active === 0;
      byId("recent-tickets").innerHTML = ticketRows(ticketPage.results || [], 8);
      attachTicketOpeners(byId("recent-tickets"));
    } catch (error) {
      byId("recent-tickets").innerHTML =
        '<div class="empty-state compact"><p>' + escapeHtml(error.message) + "</p></div>";
    }
  }

  function ticketQuery(includePage) {
    const params = new URLSearchParams();
    const form = new FormData(byId("ticket-filters"));
    form.forEach(function (value, key) {
      if (String(value).trim()) params.set(key, String(value).trim());
    });
    if (isManager() && state.queueMode === "mine") {
      params.set("reporter", String(state.user.id));
    }
    if (includePage !== false) params.set("page", String(state.page));
    return params;
  }

  function refreshBulkSelection() {
    const selectedCount = state.selectedTicketIds.size;
    byId("selected-ticket-count").textContent = selectedCount;
    byId("apply-bulk-status").disabled = selectedCount === 0;
    document.querySelectorAll("[data-ticket-id]").forEach(function (row) {
      row.classList.toggle(
        "selected",
        state.selectedTicketIds.has(Number(row.dataset.ticketId))
      );
    });
    const checkboxes = Array.from(
      document.querySelectorAll("[data-select-ticket]")
    );
    byId("select-all-tickets").checked =
      checkboxes.length > 0 && checkboxes.every(function (box) { return box.checked; });
  }

  function attachTicketSelectors() {
    document.querySelectorAll("[data-select-ticket]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        const ticketId = Number(checkbox.dataset.selectTicket);
        if (checkbox.checked) state.selectedTicketIds.add(ticketId);
        else state.selectedTicketIds.delete(ticketId);
        refreshBulkSelection();
      });
    });
    refreshBulkSelection();
  }

  async function loadTickets(resetPage) {
    if (resetPage) state.page = 1;
    showView("tickets");
    byId("queue-status").textContent = "Loading tickets…";
    byId("tickets-table-body").innerHTML = "";
    try {
      const result = await api("/api/tickets/?" + ticketQuery().toString());
      const rows = result.results || [];
      state.selectedTicketIds.clear();
      byId("select-all-tickets").checked = false;
      const total = result.count || 0;
      state.pageCount = Math.max(1, Math.ceil(total / 25));
      byId("queue-status").textContent =
        total + (total === 1 ? " ticket" : " tickets") + " found";
      byId("pagination-label").textContent =
        "Page " + state.page + " of " + state.pageCount;
      byId("previous-page").disabled = state.page <= 1;
      byId("next-page").disabled = state.page >= state.pageCount;
      if (!rows.length) {
        byId("tickets-table-body").innerHTML =
          '<tr><td colspan="' + (isManager() ? "7" : "6") +
          '"><div class="empty-state compact">' +
          "<p>No tickets match these filters.</p></div></td></tr>";
        refreshBulkSelection();
        return;
      }
      byId("tickets-table-body").innerHTML = rows.map(function (ticket) {
        return (
          '<tr data-ticket-id="' + ticket.id + '">' +
          (isManager()
            ? '<td><input type="checkbox" data-select-ticket="' + ticket.id +
              '" aria-label="Select ' + escapeHtml(ticket.reference) + '"></td>'
            : "") +
          '<td class="ticket-cell"><strong>' + escapeHtml(ticket.title) +
          "</strong><small>" + escapeHtml(ticket.reference) + "</small></td>" +
          "<td>" + priorityBadge(ticket.priority) + "</td>" +
          "<td>" + statusBadge(ticket.status) + "</td>" +
          "<td>" + escapeHtml(ticket.workstation || "—") + "</td>" +
          "<td>" + escapeHtml(
            ticket.reporter ? ticket.reporter.display_name : "—"
          ) + "</td>" +
          "<td>" + escapeHtml(timeAgo(ticket.updated_at)) + "</td></tr>"
        );
      }).join("");
      attachTicketOpeners(byId("tickets-table-body"));
      attachTicketSelectors();
    } catch (error) {
      byId("queue-status").textContent = error.message;
      showToast(error.message, "error");
    }
  }

  function detailField(label, value) {
    return (
      '<div class="detail-field"><span>' + escapeHtml(label) +
      "</span><strong>" + value + "</strong></div>"
    );
  }

  function commentMarkup(comment) {
    return (
      '<article class="comment' + (comment.is_internal ? " internal" : "") + '">' +
      '<div class="comment-head"><strong>' +
      escapeHtml(comment.author.display_name) + "</strong><span>" +
      (comment.is_internal ? "Internal • " : "") +
      escapeHtml(formatDate(comment.created_at)) +
      "</span></div><p>" + escapeHtml(comment.body) + "</p></article>"
    );
  }

  function managementMarkup(ticket) {
    if (!isManager()) return "";
    const assigneeOptions = state.assignableUsers.map(function (user) {
      const selected = ticket.assignee === user.id ? " selected" : "";
      return (
        '<option value="' + user.id + '"' + selected + ">" +
        escapeHtml(user.display_name) + "</option>"
      );
    }).join("");
    const transitions = (state.config.status_transitions[ticket.status] || [])
      .map(function (status) {
        return '<option value="' + escapeHtml(status) + '">' +
          escapeHtml(status) + "</option>";
      }).join("");
    const rootCauses = state.config.root_causes.map(function (cause) {
      return '<option value="' + escapeHtml(cause) + '">' +
        escapeHtml(cause) + "</option>";
    }).join("");
    return (
      '<section class="detail-section" id="management-actions">' +
      "<h3>Team actions</h3>" +
      '<div class="action-bar">' +
      '<label>Assign to<select id="detail-assignee"><option value="">Select team member</option>' +
      assigneeOptions + "</select></label>" +
      '<button id="assign-ticket" class="button button-secondary" type="button">Assign</button>' +
      '<button id="assign-to-me" class="button button-secondary" type="button">Assign to me</button>' +
      "</div>" +
      (transitions
        ? '<div class="action-bar detail-section">' +
          '<label>Next status<select id="detail-status"><option value="">Select status</option>' +
          transitions + "</select></label>" +
          '<label>Root cause<select id="detail-root-cause"><option value="">If known</option>' +
          rootCauses + "</select></label>" +
          '<label>Resolution / action notes<input id="detail-resolution" placeholder="Required when resolving"></label>' +
          '<button id="transition-ticket" class="button button-primary" type="button">Update status</button>' +
          "</div>"
        : "") +
      '<div class="action-bar detail-section">' +
      '<label>Escalate to<input id="detail-escalated-to" placeholder="Team or person"></label>' +
      '<label>Escalation note<input id="detail-escalation-note" placeholder="Reason"></label>' +
      '<button id="escalate-ticket" class="button button-danger" type="button">Escalate</button>' +
      "</div></section>"
    );
  }

  function commentsMarkup(comments) {
    return (
      '<section class="detail-section"><h3>Comments</h3>' +
      '<div class="comment-list">' +
      (comments.length
        ? comments.map(commentMarkup).join("")
        : '<p class="muted">No comments yet.</p>') +
      "</div>" +
      '<form id="comment-form" class="comment-form">' +
      '<textarea id="comment-body" required placeholder="Add an update…"></textarea>' +
      (isManager()
        ? '<label class="check-label"><input id="comment-internal" type="checkbox"> Internal note</label>'
        : "") +
      '<button class="button button-primary" type="submit">Add comment</button>' +
      "</form></section>"
    );
  }

  function historyMarkup(events) {
    if (!isManager() || !events.length) return "";
    return (
      '<section class="detail-section"><h3>Audit history</h3>' +
      '<div class="comment-list">' +
      events.map(function (event) {
        const status = event.from_status || event.to_status
          ? " • " + [event.from_status, event.to_status].filter(Boolean).join(" → ")
          : "";
        return (
          '<article class="comment"><div class="comment-head"><strong>' +
          escapeHtml(event.actor.display_name) + "</strong><span>" +
          escapeHtml(formatDate(event.created_at)) + "</span></div><p>" +
          escapeHtml(event.action.replaceAll("_", " ") + status) +
          (event.note ? "\n" + escapeHtml(event.note) : "") +
          "</p></article>"
        );
      }).join("") +
      "</div></section>"
    );
  }

  function attachDetailActions(ticket) {
    byId("comment-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      const body = byId("comment-body").value.trim();
      if (!body) return;
      try {
        await api("/api/tickets/" + ticket.id + "/comments/", {
          method: "POST",
          body: {
            body: body,
            is_internal: isManager() && byId("comment-internal").checked,
          },
        });
        showToast("Comment added.");
        await openTicket(ticket.id);
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    if (!isManager()) return;
    byId("assign-ticket").addEventListener("click", async function () {
      const assignee = byId("detail-assignee").value;
      if (!assignee) {
        showToast("Select a team member first.", "error");
        return;
      }
      await runTicketAction(
        ticket,
        "/assign/",
        { assignee: Number(assignee) },
        "Ticket assigned."
      );
    });
    byId("assign-to-me").addEventListener("click", function () {
      runTicketAction(ticket, "/assign-to-me/", {}, "Ticket assigned to you.");
    });
    if (byId("transition-ticket")) {
      byId("transition-ticket").addEventListener("click", async function () {
        const nextStatus = byId("detail-status").value;
        if (!nextStatus) {
          showToast("Select the next status.", "error");
          return;
        }
        const resolutionNotes = byId("detail-resolution").value.trim();
        const rootCause = byId("detail-root-cause").value;
        const payload = {
          status: nextStatus,
          note: resolutionNotes,
        };
        if (resolutionNotes || nextStatus === "Resolved") {
          payload.resolution_notes = resolutionNotes;
        }
        if (rootCause) payload.root_cause = rootCause;
        await runTicketAction(
          ticket,
          "/transition/",
          payload,
          "Status changed to " + nextStatus + "."
        );
      });
    }
    byId("escalate-ticket").addEventListener("click", async function () {
      const target = byId("detail-escalated-to").value.trim();
      if (!target) {
        showToast("Enter who should receive the escalation.", "error");
        return;
      }
      await runTicketAction(
        ticket,
        "/escalate/",
        {
          escalated_to: target,
          note: byId("detail-escalation-note").value.trim(),
        },
        "Ticket escalated."
      );
    });
  }

  async function runTicketAction(ticket, suffix, payload, successMessage) {
    try {
      await api("/api/tickets/" + ticket.id + suffix, {
        method: "POST",
        body: payload,
      });
      showToast(successMessage);
      await openTicket(ticket.id);
      if (state.currentView === "tickets") await loadTickets(false);
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function openTicket(ticketId) {
    state.currentTicketId = ticketId;
    byId("dialog-reference").textContent = "Loading";
    byId("dialog-title").textContent = "Ticket details";
    byId("dialog-body").innerHTML =
      '<div class="loading-card"><span class="spinner"></span><p>Loading ticket…</p></div>';
    if (!byId("ticket-dialog").open) byId("ticket-dialog").showModal();
    try {
      const calls = [
        api("/api/tickets/" + ticketId + "/"),
        api("/api/tickets/" + ticketId + "/comments/"),
      ];
      if (isManager()) calls.push(api("/api/tickets/" + ticketId + "/history/"));
      const results = await Promise.all(calls);
      const ticket = results[0];
      const comments = results[1];
      const events = results[2] || [];
      byId("dialog-reference").textContent = ticket.reference;
      byId("dialog-title").textContent = ticket.title;
      byId("dialog-body").innerHTML =
        '<div class="detail-grid">' +
        detailField("Status", statusBadge(ticket.status)) +
        detailField("Priority", priorityBadge(ticket.priority)) +
        detailField("Issue type", escapeHtml(ticket.category)) +
        detailField("Workstation", escapeHtml(ticket.workstation || "—")) +
        detailField("Location", escapeHtml(ticket.location || "—")) +
        detailField("Impact", escapeHtml(ticket.impact_level || "—")) +
        detailField(
          "Requester",
          escapeHtml(ticket.reporter ? ticket.reporter.display_name : "—")
        ) +
        detailField(
          "Assigned to",
          escapeHtml(
            ticket.assignee_details ? ticket.assignee_details.display_name : "Unassigned"
          )
        ) +
        detailField("Created", escapeHtml(formatDate(ticket.created_at))) +
        "</div>" +
        '<section class="detail-section"><h3>Description</h3><p class="detail-copy">' +
        escapeHtml(ticket.description) + "</p></section>" +
        (ticket.resolution_notes
          ? '<section class="detail-section"><h3>Resolution</h3><p class="detail-copy">' +
            escapeHtml(ticket.resolution_notes) + "</p></section>"
          : "") +
        managementMarkup(ticket) +
        commentsMarkup(comments) +
        historyMarkup(events);
      attachDetailActions(ticket);
    } catch (error) {
      byId("dialog-body").innerHTML =
        '<div class="empty-state compact"><p>' + escapeHtml(error.message) + "</p></div>";
    }
  }

  async function createTicket(event) {
    event.preventDefault();
    const button = byId("create-ticket-button");
    const errorBox = byId("create-error");
    const form = new FormData(byId("create-ticket-form"));
    const payload = {};
    form.forEach(function (value, key) {
      if (String(value).trim()) payload[key] = String(value).trim();
    });
    if (payload.reporter_id) payload.reporter_id = Number(payload.reporter_id);
    if (payload.downtime_start) {
      payload.downtime_start = new Date(payload.downtime_start).toISOString();
    }
    errorBox.hidden = true;
    button.disabled = true;
    button.textContent = "Creating ticket…";
    try {
      const ticket = await api("/api/tickets/", { method: "POST", body: payload });
      showToast(ticket.reference + " was created.");
      resetCreateForm();
      state.queueMode = isManager() ? "all" : "mine";
      await loadOverview();
      await openTicket(ticket.id);
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Submit ticket";
    }
  }

  async function applyBulkStatus() {
    const status = byId("bulk-status").value;
    if (!status || state.selectedTicketIds.size === 0) {
      showToast("Select tickets and a new status first.", "error");
      return;
    }
    const button = byId("apply-bulk-status");
    button.disabled = true;
    button.textContent = "Updating…";
    const resolutionNotes = byId("bulk-resolution-notes").value.trim();
    const payload = {
      ticket_ids: Array.from(state.selectedTicketIds),
      status: status,
      note: resolutionNotes,
    };
    if (resolutionNotes || status === "Resolved") {
      payload.resolution_notes = resolutionNotes;
    }
    try {
      const results = await api("/api/tickets/bulk-status/", {
        method: "POST",
        body: payload,
      });
      const succeeded = results.filter(function (result) { return result.ok; }).length;
      const failed = results.length - succeeded;
      showToast(
        succeeded + " ticket(s) updated" +
        (failed ? "; " + failed + " could not use that transition." : "."),
        failed ? "error" : ""
      );
      byId("bulk-resolution-notes").value = "";
      await loadTickets(false);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Apply to selected";
    }
  }

  async function exportTickets() {
    const button = byId("export-tickets");
    button.disabled = true;
    button.textContent = "Preparing CSV…";
    try {
      const response = await fetch(
        "/api/tickets/export/?" + ticketQuery(false).toString(),
        {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "text/csv" },
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(function () { return null; });
        throw new Error(flattenError(data).join(" ") || "CSV export failed.");
      }
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "nvgs_tickets_" + new Date().toISOString().slice(0, 10) + ".csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      showToast("CSV export downloaded.");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Export filtered CSV";
    }
  }

  function populateProfile() {
    byId("profile-first-name").value = state.user.first_name || "";
    byId("profile-last-name").value = state.user.last_name || "";
    byId("profile-department").value = state.user.department || "";
    byId("profile-email").value = state.user.email;
    byId("profile-role").value = displayRole(state.user.role);
  }

  async function saveProfile(event) {
    event.preventDefault();
    const button = byId("save-profile");
    const errorBox = byId("profile-error");
    errorBox.hidden = true;
    button.disabled = true;
    button.textContent = "Saving…";
    try {
      state.user = await api("/api/auth/me/", {
        method: "PATCH",
        body: {
          first_name: byId("profile-first-name").value.trim(),
          last_name: byId("profile-last-name").value.trim(),
          department: byId("profile-department").value.trim(),
        },
      });
      configureUserInterface();
      populateProfile();
      showToast("Profile saved.");
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Save profile";
    }
  }

  function renderBarChart(element, rows, labelForRow) {
    if (!rows.length) {
      element.innerHTML = '<p class="muted">No data in this period.</p>';
      return;
    }
    const maximum = Math.max.apply(null, rows.map(function (row) {
      return Number(row.count) || 0;
    }));
    element.innerHTML = rows.slice(0, 15).map(function (row) {
      const count = Number(row.count) || 0;
      return (
        '<div class="bar-row"><span class="bar-label" title="' +
        escapeHtml(labelForRow(row)) + '">' + escapeHtml(labelForRow(row)) +
        '</span><progress class="bar-track" max="' + (maximum || 1) +
        '" value="' + count + '"></progress><span class="bar-value">' +
        count + "</span></div>"
      );
    }).join("");
  }

  async function loadAnalytics() {
    if (!isManager()) return;
    showView("analytics");
    byId("analytics-metrics").innerHTML =
      '<div class="loading-card"><span class="spinner"></span></div>';
    try {
      const data = await api(
        "/api/tickets/analytics/?period=" + state.analyticsPeriod
      );
      const metrics = data.metrics;
      const cards = [
        ["Tickets", metrics.total || 0],
        ["Active", metrics.active || 0],
        ["Resolved", metrics.resolved || 0],
        ["Avg downtime", (metrics.average_downtime || 0) + " min"],
        ["Avg response", (metrics.average_response || 0) + " min"],
        ["Avg resolution", (metrics.average_resolution || 0) + " min"],
      ];
      byId("analytics-metrics").innerHTML = cards.map(function (card) {
        return (
          '<article class="summary-card"><span>' + escapeHtml(card[0]) +
          "</span><strong>" + escapeHtml(card[1]) + "</strong></article>"
        );
      }).join("");
      renderBarChart(byId("chart-trend"), data.trend, function (row) {
        return row.day;
      });
      renderBarChart(byId("chart-status"), data.by_status, function (row) {
        return row.status || "Unknown";
      });
      renderBarChart(byId("chart-priority"), data.by_priority, function (row) {
        return row.priority || "Unknown";
      });
      renderBarChart(byId("chart-category"), data.by_category, function (row) {
        return row.category || "Unknown";
      });
      renderBarChart(
        byId("chart-workstation"),
        data.by_workstation,
        function (row) { return row.workstation || "Not recorded"; }
      );
      renderBarChart(byId("chart-resolved-by"), data.resolved_by, function (row) {
        const name = [
          row.resolved_by__first_name,
          row.resolved_by__last_name,
        ].filter(Boolean).join(" ");
        return name || row.resolved_by__email;
      });
    } catch (error) {
      byId("analytics-metrics").innerHTML =
        '<div class="empty-state compact"><p>' +
        escapeHtml(error.message) + "</p></div>";
    }
  }

  async function loadSystemStatus() {
    if (!isManager()) return;
    showView("settings");
    byId("system-status-cards").innerHTML =
      '<div class="loading-card"><span class="spinner"></span></div>';
    try {
      const status = await api("/api/system-status/");
      const cards = [
        ["Database", status.database],
        [
          "Google login",
          status.appscript_login_enabled ? "Enabled" : "Disabled",
        ],
        [
          "Ticket webhook",
          status.ticket_webhook_configured ? "Configured" : "Disabled",
        ],
        ["Queued alerts", status.pending_notifications],
        ["Failed attempts", status.failed_notifications],
        ["Needs review", status.abandoned_notifications],
      ];
      byId("system-status-cards").innerHTML = cards.map(function (card) {
        return (
          '<article class="summary-card"><span>' + escapeHtml(card[0]) +
          "</span><strong>" + escapeHtml(card[1]) + "</strong></article>"
        );
      }).join("");
    } catch (error) {
      byId("system-status-cards").innerHTML =
        '<div class="empty-state compact"><p>' +
        escapeHtml(error.message) + "</p></div>";
    }
  }

  function configureUserInterface() {
    byId("user-name").textContent = state.user.display_name;
    byId("user-email").textContent = state.user.email;
    byId("user-role").textContent = displayRole(state.user.role);
    byId("welcome-name").textContent = state.user.first_name || state.user.display_name;
    populateProfile();
    if (isManager()) {
      byId("team-navigation").hidden = false;
      byId("reporter-field").hidden = false;
      byId("overview-subtitle").textContent =
        "Monitor the queue and help the Robotics Team move quickly.";
      byId("recent-heading").textContent = "Recent queue activity";
      byId("requester-column").hidden = false;
      byId("selection-column").hidden = false;
      byId("bulk-actions").hidden = false;
    } else {
      byId("requester-column").hidden = true;
      byId("selection-column").hidden = true;
      byId("bulk-actions").hidden = true;
    }
    if (state.user.role === "system_admin") byId("admin-link").hidden = false;
  }

  async function initialize() {
    showView("loading");
    try {
      const base = await Promise.all([
        api("/api/auth/me/"),
        api("/api/tickets/configuration/"),
      ]);
      state.user = base[0];
      state.config = base[1];
      state.queueMode = isManager() ? "all" : "mine";
      if (isManager()) {
        const people = await Promise.all([
          api("/api/auth/users/"),
          api("/api/auth/users/assignable/"),
        ]);
        state.users = people[0];
        state.assignableUsers = people[1];
      }
      configureUserInterface();
      fillConfiguration();
      fillPeople();
      resetCreateForm();
      await loadOverview();
      const ticketId = new URLSearchParams(window.location.search).get("ticket");
      if (ticketId && /^\d+$/.test(ticketId)) await openTicket(Number(ticketId));
    } catch (error) {
      byId("fatal-message").textContent = error.message;
      showView("fatal");
    }
  }

  document.querySelectorAll("[data-view-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      const target = button.dataset.viewTarget;
      if (target === "tickets") loadTickets(true);
      else showView(target);
    });
  });

  document.querySelectorAll(".nav-button[data-view]").forEach(function (button) {
    button.addEventListener("click", function () {
      const target = button.dataset.view;
      if (target === "tickets") {
        state.queueMode = button.dataset.teamQueue === "true" ? "all" : "mine";
        byId("tickets-heading").textContent =
          state.queueMode === "all" ? "Complete queue" : "My tickets";
        byId("tickets-description").textContent =
          state.queueMode === "all"
            ? "All tickets visible to the Tech Team, TLs, and Managers."
            : "Tickets you have filed.";
        loadTickets(true);
      } else if (target === "overview") {
        loadOverview();
      } else if (target === "analytics") {
        loadAnalytics();
      } else if (target === "settings") {
        loadSystemStatus();
      } else if (target === "profile") {
        populateProfile();
        showView("profile");
      } else {
        showView(target);
      }
    });
  });

  byId("create-ticket-form").addEventListener("submit", createTicket);
  byId("profile-form").addEventListener("submit", saveProfile);
  byId("ticket-filters").addEventListener("submit", function (event) {
    event.preventDefault();
    loadTickets(true);
  });
  byId("clear-filters").addEventListener("click", function () {
    byId("ticket-filters").reset();
    fillConfiguration();
    loadTickets(true);
  });
  byId("previous-page").addEventListener("click", function () {
    if (state.page > 1) {
      state.page -= 1;
      loadTickets(false);
    }
  });
  byId("next-page").addEventListener("click", function () {
    if (state.page < state.pageCount) {
      state.page += 1;
      loadTickets(false);
    }
  });
  byId("select-all-tickets").addEventListener("change", function () {
    document.querySelectorAll("[data-select-ticket]").forEach(function (checkbox) {
      checkbox.checked = byId("select-all-tickets").checked;
      const ticketId = Number(checkbox.dataset.selectTicket);
      if (checkbox.checked) state.selectedTicketIds.add(ticketId);
      else state.selectedTicketIds.delete(ticketId);
    });
    refreshBulkSelection();
  });
  byId("apply-bulk-status").addEventListener("click", applyBulkStatus);
  byId("export-tickets").addEventListener("click", exportTickets);
  document.querySelectorAll(".analytics-period").forEach(function (button) {
    button.addEventListener("click", function () {
      state.analyticsPeriod = Number(button.dataset.period);
      document.querySelectorAll(".analytics-period").forEach(function (periodButton) {
        periodButton.classList.toggle(
          "button-secondary",
          periodButton === button
        );
        periodButton.classList.toggle(
          "button-ghost",
          periodButton !== button
        );
      });
      loadAnalytics();
    });
  });
  byId("refresh-system-status").addEventListener("click", loadSystemStatus);
  byId("close-dialog").addEventListener("click", function () {
    byId("ticket-dialog").close();
  });
  byId("ticket-dialog").addEventListener("click", function (event) {
    if (event.target === byId("ticket-dialog")) byId("ticket-dialog").close();
  });
  byId("menu-button").addEventListener("click", function () {
    byId("sidebar").classList.toggle("open");
  });
  byId("retry-button").addEventListener("click", initialize);
  byId("logout-button").addEventListener("click", async function () {
    try {
      await api("/api/auth/logout/", { method: "POST" });
    } finally {
      window.location.assign("/login/");
    }
  });

  initialize();
}());
