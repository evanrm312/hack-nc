// Campus Current marketplace pages (Person 3).
// Home (request box -> normalize -> create -> results), results (editable
// interpretation + matches), listing form/detail, public request feed.
// Every request goes through window.api; every piece of UI goes through
// window.components. Server strings are rendered as text only.

(function () {
  "use strict";
  const C = window.components;
  const $ = (id) => document.getElementById(id);
  const page = document.body.dataset.page;
  const enc = encodeURIComponent;

  const CATEGORIES = [
    ["", "Unknown / not sure"],
    ["formalwear", "Formalwear"], ["clothing", "Clothing"], ["electronics", "Electronics"],
    ["textbooks", "Textbooks"], ["calculators", "Calculators"], ["furniture", "Furniture"],
    ["appliances", "Appliances"], ["sports", "Sports & outdoors"], ["tools", "Tools"],
    ["kitchen", "Kitchen"], ["other", "Other"],
  ];
  // Search preference used only when the interpreter gave no mode. It is
  // shown as "needs confirmation" until the user confirms it.
  const DEFAULT_MODES = ["borrow", "sale"];

  const CONDITIONS = [["", "Unknown"], ["new", "New"], ["like_new", "Like new"], ["good", "Good"], ["fair", "Fair"], ["worn", "Worn"]];
  const conditionLabel = (c) => (CONDITIONS.find(([v]) => v === c) || [c, c ? String(c).replace("_", " ") : "unknown"])[1];

  if (page === "home") initHome();
  if (page === "results") initResults();
  if (page === "listing-form") initListingForm();
  if (page === "listing-detail") initListingDetail();
  if (page === "requests-feed") initRequestsFeed();

  // ------------------------------------------------------------ shared bits
  function authMessage(err) {
    return C.el("span", {}, C.errorMessage(err), " ", C.el("a", { href: "/sign-in", text: "Sign in" }), ".");
  }

  function showNotice(container, content) {
    C.clear(container);
    if (content === null || content === undefined || content === "") { container.hidden = true; return; }
    container.append(C.el("div", {}, content));
    container.hidden = false;
    if (container.getAttribute("role") === "alert") {
      container.setAttribute("tabindex", "-1");
      container.focus();
    }
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  const nonNegInt = (v) => (Number.isInteger(v) && v >= 0 ? v : null);
  const cleanModes = (modes) => (Array.isArray(modes) ? modes.filter((m) => m === "sale" || m === "borrow") : []);

  function manualNormalized(text, question) {
    return {
      source: "manual", modes: null, category: null,
      required_specifications: {}, preferred_specifications: {},
      budget_cents: null, max_deposit_cents: null, needed_by: null, use_start: null, use_end: null, area: null,
      ambiguous_dates: [], follow_up_questions: [question], original_text: text,
    };
  }

  // ====================================================================== HOME
  function initHome() {
    const form = $("request-form");
    const textarea = $("request-text");
    const textError = $("request-text-error");
    const submit = $("request-submit");
    const status = $("request-status");
    const formError = $("request-error");
    const authGate = $("auth-gate");

    function refreshGate() {
      const signedIn = !!api.getToken();
      authGate.hidden = signedIn;
      submit.disabled = !signedIn;
      submit.title = signedIn ? "" : "Sign in first";
    }
    document.addEventListener("campus:auth-changed", refreshGate);
    refreshGate();

    document.querySelectorAll("[data-example]").forEach((chip) => {
      chip.addEventListener("click", () => {
        textarea.value = chip.dataset.example;
        textarea.focus();
        textError.textContent = "";
        textarea.removeAttribute("aria-invalid");
      });
    });
    textarea.addEventListener("input", () => { textError.textContent = ""; textarea.removeAttribute("aria-invalid"); });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      showNotice(formError, null);
      const text = textarea.value.trim();
      if (!text) {
        textError.textContent = "Describe what you need first.";
        textarea.setAttribute("aria-invalid", "true");
        textarea.focus();
        return;
      }
      C.setBusy(submit, true, "Interpreting your request");
      status.textContent = "Interpreting…";

      // Step 1: interpret. A non-auth failure falls back to a manual
      // interpretation (all unknown) so the user still gets an editable form.
      let normalized;
      try {
        const result = await api.post("/api/requests/normalize", { text });
        normalized = result.normalized || manualNormalized(text, "The interpreter returned nothing. Fill in the fields yourself.");
      } catch (err) {
        if (C.isAuthError(err)) {
          if (err.status === 401) api.setToken(null);
          status.textContent = "";
          C.setBusy(submit, false);
          showNotice(formError, authMessage(err));
          return;
        }
        normalized = manualNormalized(text, "The interpreter could not be reached (" + C.errorMessage(err) + "). Nothing was guessed; fill in the fields yourself.");
      }

      // Step 2: save the request and go to results, where every field is editable.
      status.textContent = "Saving your request…";
      try {
        const request = await createRequestFrom(text, normalized);
        window.location.href = "/results/" + enc(request.id);
      } catch (err) {
        status.textContent = "";
        C.setBusy(submit, false);
        if (C.isAuthError(err)) {
          if (err.status === 401) api.setToken(null);
          showNotice(formError, authMessage(err));
        } else {
          showNotice(formError, C.errorMessage(err));
        }
      }
    });

    loadListings();
  }

  async function createRequestFrom(text, normalized) {
    const modes = cleanModes(normalized.modes);
    const body = {
      original_text: text,
      normalized,
      modes: modes.length ? modes : DEFAULT_MODES.slice(),
      budget_cents: nonNegInt(normalized.budget_cents),
      max_deposit_cents: nonNegInt(normalized.max_deposit_cents),
      needed_by: normalized.needed_by || null,
      use_start: normalized.use_start || null,
      use_end: normalized.use_end || null,
      pickup_windows: [],
      area: typeof normalized.area === "string" ? normalized.area.slice(0, 80) : null,
    };
    try {
      return (await api.post("/api/requests", body)).request;
    } catch (err) {
      if (!(err instanceof api.ApiError && err.code === "validation_error")) throw err;
      // Interpreted values were rejected by the server. Keep the text, drop
      // the rejected values, and tell the user on the results page.
      const rejected = Object.keys(err.fields || {}).join(", ");
      const retry = {
        original_text: text,
        normalized: Object.assign({}, normalized, {
          budget_cents: null, max_deposit_cents: null, needed_by: null, use_start: null, use_end: null, area: null,
          follow_up_questions: (normalized.follow_up_questions || []).concat(
            "Some interpreted values were rejected by the server (" + (rejected || "unknown fields") + ") and were cleared. Please enter them."),
        }),
        modes: DEFAULT_MODES.slice(),
        pickup_windows: [],
      };
      return (await api.post("/api/requests", retry)).request;
    }
  }

  // =================================================================== RESULTS
  function initResults() {
    const root = $("results-root");
    const requestId = root.dataset.requestId;
    const interpBody = $("interp-body");
    const interpBadges = $("interp-badges");
    const matchesBox = $("matches");
    let request = null;

    document.addEventListener("campus:auth-changed", loadRequest);
    loadRequest();

    async function loadRequest() {
      C.state.loading(interpBody, "Loading your request…");
      C.state.loading(matchesBox, "Loading matches…");
      if (!api.getToken()) {
        gate(new api.ApiError(401, { error: { code: "auth_required" } }));
        return;
      }
      try {
        const data = await api.get("/api/requests/" + enc(requestId));
        if (data.view !== "owner") {
          notYours();
          return;
        }
        request = data.request;
        renderHead();
        renderInterpretation();
        loadMatches();
      } catch (err) {
        if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); gate(err); return; }
        if (err instanceof api.ApiError && err.status === 404) { notYours(); return; }
        C.state.error(interpBody, err, { title: "Could not load this request", retry: loadRequest });
        C.state.clear(matchesBox);
        matchesBox.removeAttribute("aria-busy");
      }
    }

    function gate(err) {
      C.clear(interpBody).append(C.notice("info", authMessage(err)));
      C.state.clear(matchesBox);
      matchesBox.removeAttribute("aria-busy");
    }

    function notYours() {
      C.state.error(interpBody, { message: "Only the person who made a request can see its matches, and private requests are not revealed to anyone else." },
        { title: "This request is not available", action: C.button({ label: "Start a new request", variant: "primary", size: "sm", href: "/" }) });
      C.state.clear(matchesBox);
      matchesBox.removeAttribute("aria-busy");
    }

    function renderHead() {
      $("results-original").textContent = request.original_text || "";
      const badges = C.clear($("results-badges"));
      const src = (request.normalized || {}).source || "unknown";
      if (src === "gemini") badges.append(C.badge("Interpreted by Gemini", "info"));
      else if (src === "stub") badges.append(C.fixtureBadge("Stub interpretation, not Gemini"));
      else badges.append(C.badge("Entered manually", "neutral"));
      badges.append(C.statusBadge(request.status));
      if (request.visibility === "public") badges.append(C.badge("Published", "sale"));
      else badges.append(C.badge("Private", "neutral"));
    }

    // ---- editable interpretation --------------------------------------
    function renderInterpretation() {
      const n = request.normalized || {};
      C.clear(interpBadges);
      C.clear(interpBody);

      const source = n.source || "unknown";
      if (source === "stub") {
        interpBadges.append(C.fixtureBadge("Stub output, not Gemini"));
        interpBody.append(C.notice("fixture", C.el("span", {},
          C.el("strong", { text: "Nothing was extracted. " }),
          "Request interpretation is a labeled stub right now, so every field below started unknown. Fill in what you know; unknown stays unknown.")));
      } else if (source === "manual") {
        interpBadges.append(C.badge("Manual entry", "warn"));
        interpBody.append(C.notice("warn", "Nothing was guessed for this request. Fill in the fields you know and update the results."));
      } else {
        interpBadges.append(C.badge("Proposed by Gemini", "info"));
        interpBody.append(C.notice("info", "These are proposals from the interpreter, not facts. Edit anything that is wrong; blank means unknown."));
      }

      const questions = (n.follow_up_questions || []).filter(Boolean);
      const ambiguous = Array.isArray(n.ambiguous_dates) ? n.ambiguous_dates : [];
      if (questions.length || ambiguous.length) {
        const list = C.el("ul", { style: { margin: "0", paddingLeft: "1.2em" } });
        questions.forEach((q) => list.append(C.el("li", { text: String(q) })));
        ambiguous.forEach((a) => list.append(C.el("li", {},
          C.el("strong", { text: "Date needs confirmation: " }),
          `"${a.text}" was read as ${api.formatTime(a.proposed)} (America/New_York). Correct it below if that is wrong.`)));
        interpBody.append(C.el("div", { className: "notice notice--warn", role: "note" },
          C.el("div", {}, C.el("strong", { text: "Please confirm" }), list)));
      }

      const modesKnown = cleanModes(n.modes).length > 0;
      const values = {
        modes: request.modes || [],
        category: n.category || "",
        required_specifications: n.required_specifications || {},
        preferred_specifications: n.preferred_specifications || {},
        budget_cents: request.budget_cents,
        max_deposit_cents: request.max_deposit_cents,
        needed_by: request.needed_by,
        use_start: request.use_start,
        use_end: request.use_end,
        area: request.area,
      };
      const meta = { modesUnknown: !modesKnown, ambiguous };

      const form = C.el("form", { id: "interp-form", novalidate: true });
      const editor = buildInterpretationForm(form, values, meta);
      const errorBox = C.el("div", { className: "notice notice--error", role: "alert", hidden: true });
      const submit = C.button({ label: "Update results", variant: "leaf", type: "submit" });
      form.append(errorBox, C.el("div", { className: "cluster cluster--between" },
        C.el("div", { className: "cluster" }, submit, C.button({ label: "New request", variant: "ghost", href: "/" })),
        C.el("span", { className: "muted", text: "Your request stays private until you choose to publish it." })));
      interpBody.append(form);

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        showNotice(errorBox, null);
        const read = editor.read();
        if (!read.ok) return;
        const v = read.values;
        const body = {
          modes: v.modes,
          budget_cents: v.budget_cents,
          max_deposit_cents: v.max_deposit_cents,
          needed_by: v.needed_by,
          use_start: v.use_start,
          use_end: v.use_end,
          area: v.area,
          normalized: Object.assign({}, n, {
            source: source === "stub" ? "manual" : source,
            modes: v.modes,
            category: v.category || null,
            required_specifications: v.required_specifications,
            preferred_specifications: v.preferred_specifications,
            budget_cents: v.budget_cents,
            max_deposit_cents: v.max_deposit_cents,
            needed_by: v.needed_by,
            use_start: v.use_start,
            use_end: v.use_end,
            area: v.area,
            // The user has reviewed every field, so pending questions are resolved.
            ambiguous_dates: [],
            follow_up_questions: [],
          }),
        };
        C.setBusy(submit, true, "Updating results");
        try {
          const data = await api.patch("/api/requests/" + enc(requestId), body);
          request = data.request;
          C.setBusy(submit, false);
          renderHead();
          renderInterpretation(); // rebuilds the form, so move focus deliberately
          $("interp-heading").focus();
          C.toast("Request updated. Searching again…", "leaf");
          await loadMatches();
        } catch (err) {
          C.setBusy(submit, false);
          if (err instanceof api.ApiError && err.code === "validation_error") {
            const leftovers = C.applyFieldErrors(editor.fields, err.fields);
            showNotice(errorBox, leftovers.length ? "Please fix: " + leftovers.join("; ") : "Some fields need attention.");
          } else if (err instanceof api.ApiError && err.code === "request_closed") {
            showNotice(errorBox, "This request is closed and can no longer be edited.");
          } else if (C.isAuthError(err)) {
            if (err.status === 401) api.setToken(null);
            showNotice(errorBox, authMessage(err));
          } else {
            showNotice(errorBox, C.errorMessage(err));
          }
        }
      });
    }

    // ---- matches --------------------------------------------------------
    async function loadMatches() {
      matchesBox.setAttribute("aria-busy", "true");
      C.state.loading(matchesBox, "Checking listings against your request…");
      try {
        const data = await api.get("/api/requests/" + enc(requestId) + "/matches");
        matchesBox.removeAttribute("aria-busy");
        renderMatches(data);
      } catch (err) {
        matchesBox.removeAttribute("aria-busy");
        if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); C.clear(matchesBox).append(C.notice("info", authMessage(err))); return; }
        C.state.error(matchesBox, err, { title: "Could not load matches", retry: loadMatches });
      }
    }

    function renderMatches(data) {
      C.clear(matchesBox);
      const confirmed = Array.isArray(data.confirmed) ? data.confirmed : [];
      const needs = Array.isArray(data.needs_confirmation) ? data.needs_confirmation : [];
      const rejected = Array.isArray(data.rejected) ? data.rejected : [];
      const fixture = !!data.fixture || data.source === "stub";

      // Dev preview of the no-match state (?preview=no-match). The stub
      // matcher never produces it. Real results are hidden, never altered.
      const previewNoMatch = new URLSearchParams(window.location.search).get("preview") === "no-match";
      if (previewNoMatch) {
        const hidden = confirmed.length + needs.length;
        matchesBox.append(C.notice("fixture", C.el("span", {},
          C.el("strong", { text: "Preview mode. " }),
          "Showing the no-match state for review. " + hidden + " real result" + (hidden === 1 ? " is" : "s are") + " hidden. ",
          C.el("a", { href: window.location.pathname, text: "Leave preview" }), ".")));
        renderNoMatch([], { preview: true });
        return;
      }

      if (fixture) {
        matchesBox.append(C.notice("fixture", C.el("span", {},
          C.el("strong", { text: "Matching is a labeled stub. " }),
          "Nothing below has been checked against your requirements yet, so every listing appears under \"needs confirmation\". These are real current listings, not invented results.")));
      }

      if (!confirmed.length && !needs.length) {
        renderNoMatch(rejected, { preview: false });
        appendExcluded(rejected);
        return;
      }

      // Confirmed
      const confirmedSection = C.el("section", { className: "section", "aria-labelledby": "confirmed-heading" },
        C.el("div", { className: "section__head" },
          C.el("h2", { id: "confirmed-heading", text: "Confirmed matches" }),
          C.badge(confirmed.length + (confirmed.length === 1 ? " match" : " matches"), confirmed.length ? undefined : "neutral")));
      if (confirmed.length) {
        confirmedSection.append(C.el("div", { className: "grid" }, confirmed.map((e) => matchCard(e, "confirmed"))));
      } else {
        confirmedSection.append(C.state.block("empty", {
          title: needs.length ? "No confirmed matches yet" : "No matches yet",
          message: needs.length
            ? "Some listings could match but have details that still need confirmation. See the section below."
            : "No current listing meets your requirements. Adjust the interpretation above and update the results.",
        }));
      }
      matchesBox.append(confirmedSection);

      // Needs confirmation (visibly separate)
      if (needs.length) {
        const needsSection = C.el("section", { className: "section section--needs", "aria-labelledby": "needs-heading" },
          C.el("div", { className: "section__head" },
            C.el("h2", { id: "needs-heading", text: "Needs confirmation before it counts" }),
            C.badge(needs.length + (needs.length === 1 ? " option" : " options"), "warn")),
          C.el("p", { className: "muted", style: { marginBottom: "var(--space-3)" }, text: "These are not confirmed matches. A required detail is unknown or has not been checked. Confirm it with the owner before relying on it." }),
          C.el("div", { className: "grid" }, needs.map((e) => matchCard(e, "needs"))));
        matchesBox.append(needsSection);
      }

      appendExcluded(rejected);
    }

    // Excluded listings, collapsed, with the matcher's own reasons.
    function appendExcluded(rejected) {
      if (!rejected.length) return;
      const list = C.el("ul", { className: "stack--tight", style: { margin: "0", paddingLeft: "1.2em" } });
      rejected.forEach((e) => {
        const l = e.listing || {};
        list.append(C.el("li", {},
          C.el("a", { href: "/listings/" + enc(l.id || ""), text: l.title || "Listing" }),
          " — ",
          C.el("span", { className: "muted", text: (e.shortcomings && e.shortcomings.length) ? e.shortcomings.join("; ") : "did not meet a requirement" })));
      });
      matchesBox.append(C.el("details", { className: "card card--compact" },
        C.el("summary", { className: "excluded-summary" }, "Excluded listings (" + rejected.length + ") and why"),
        C.el("div", { style: { marginTop: "var(--space-3)" } }, list)));
    }

    // ---- no-match state + publish ----------------------------------------
    // What the matcher looked for, taken only from the stored request.
    function criteriaChips() {
      const n = request.normalized || {};
      const chips = [];
      const modes = request.modes || [];
      if (modes.length === 2) chips.push("buy or borrow");
      else if (modes.length === 1) chips.push(modes[0] === "sale" ? "buy" : "borrow");
      if (n.category) chips.push("category: " + n.category);
      Object.entries(n.required_specifications || {}).forEach(([k, v]) => chips.push(k.replace(/_/g, " ") + " = " + String(v) + " (required)"));
      if (request.budget_cents != null) chips.push("budget up to " + api.formatCents(request.budget_cents));
      if (request.max_deposit_cents != null) chips.push("deposit up to " + api.formatCents(request.max_deposit_cents));
      if (request.needed_by) chips.push("needed by " + api.formatTime(request.needed_by));
      if (request.use_start && request.use_end) chips.push("borrow " + api.formatTime(request.use_start) + " to " + api.formatTime(request.use_end));
      if (request.area) chips.push("pickup around " + request.area);
      return chips;
    }

    // Counts of the matcher's exclusion reasons, most common first.
    function exclusionSummary(rejected) {
      const counts = new Map();
      rejected.forEach((e) => (e.shortcomings || []).forEach((s) => counts.set(String(s), (counts.get(String(s)) || 0) + 1)));
      return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4);
    }

    function renderNoMatch(rejected, opts) {
      const chips = criteriaChips();
      const card = C.el("section", { className: "card card--leaf no-match", "aria-labelledby": "no-match-heading" },
        C.el("div", { className: "no-match__icon", "aria-hidden": "true" }),
        C.el("h2", { id: "no-match-heading", tabindex: "-1", text: "Nothing found yet" }));

      const why = C.el("div", { className: "no-match__why" });
      why.append(C.el("p", {}, chips.length
        ? "Every current listing was checked against what you asked for:"
        : "Every current listing was checked, but your request has no specific requirements yet, so nothing could be confirmed as a match."));
      if (chips.length) why.append(C.el("ul", { className: "chips", "aria-label": "Your requirements" }, chips.map((c) => C.el("li", { className: "chip", text: c }))));

      const reasons = exclusionSummary(rejected);
      if (opts.preview) {
        why.append(C.el("p", { className: "muted", text: "Exclusion reasons are hidden in preview mode." }));
      } else if (reasons.length) {
        why.append(C.el("p", {}, C.el("strong", { text: "Why the closest listings were excluded:" })));
        why.append(C.el("ul", { className: "reasons" }, reasons.map(([text, count]) =>
          C.el("li", { className: "reason reason--warn", text: text + (count > 1 ? " (" + count + " listings)" : "") }))));
      } else if (rejected.length) {
        why.append(C.el("p", { className: "muted", text: rejected.length + " listing" + (rejected.length === 1 ? " was" : "s were") + " excluded without a stated reason." }));
      } else {
        why.append(C.el("p", { className: "muted", text: "There are no available listings from other members to check right now." }));
      }
      why.append(C.el("p", { className: "muted", text: "Only real listings in the database are ever shown. You can loosen a requirement above and update the results, or let other members know what you need." }));
      card.append(why);

      const publishBox = C.el("div", { className: "no-match__publish", id: "publish-box" });
      card.append(publishBox);
      renderPublishBlock(publishBox);
      matchesBox.append(card);
    }

    let publishing = false;

    function renderPublishBlock(box) {
      C.clear(box);
      if (request.visibility === "public") {
        renderPublishSuccess(box, null);
        return;
      }
      const btn = C.button({ label: "Publish Request", variant: "leaf", attrs: { id: "publish-btn" } });
      box.append(
        C.el("h3", { text: "Let other members know" }),
        C.el("p", { className: "muted", text: "Publishing shares a sanitized version of this request in the public feed: the item, buy or borrow, the day you need it by, and your campus area. Your exact times, borrowing dates, deposit limit, and contact details stay private. Nothing is published until you confirm." }),
        C.el("div", { className: "cluster" }, btn));
      btn.addEventListener("click", () => openPublishPreview(btn, box));
    }

    // Mirrors the server's public view (docs/contracts.md -> NeedRequest public view).
    function buildPublicPreview(profile) {
      const n = request.normalized || {};
      const fmtSpecs = (obj) => Object.entries(obj || {}).map(([k, v]) => k.replace(/_/g, " ") + " = " + String(v)).join(", ") || "none";
      const modes = request.modes || [];
      const neededDate = request.needed_by ? request.needed_by.slice(0, 10) : null;
      const publicRows = [
        ["Who", profile ? profile.display_name + " (" + profile.badge + ")" : "your display name and verification badge"],
        ["Item category", n.category || "unknown"],
        ["Required details", fmtSpecs(n.required_specifications)],
        ["Preferred details", fmtSpecs(n.preferred_specifications)],
        ["Buy or borrow", modes.length ? modes.map((m) => (m === "sale" ? "buy" : "borrow")).join(" or ") : "unknown"],
        ["Budget", request.budget_cents != null ? api.formatCents(request.budget_cents) : "unknown"],
        ["Needed by", neededDate ? neededDate + " (date only)" : "unknown"],
        ["Campus area", request.area || "unknown"],
      ];
      const privateRows = [
        ["Your original wording", request.original_text ? "“" + request.original_text.slice(0, 80) + (request.original_text.length > 80 ? "…" : "") + "”" : "—"],
        ["Exact needed-by time", request.needed_by ? api.formatTime(request.needed_by) : "unknown"],
        ["Borrowing dates", request.use_start || request.use_end ? api.formatTime(request.use_start) + " to " + api.formatTime(request.use_end) : "unknown"],
        ["Pickup windows", (request.pickup_windows || []).length ? (request.pickup_windows.length + " window(s)") : "none set"],
        ["Deposit you can afford", request.max_deposit_cents != null ? api.formatCents(request.max_deposit_cents) : "unknown"],
        ["Email and contact details", "never shown"],
      ];
      const list = (rows, lock) => C.el("dl", { className: "privacy-list" }, rows.flatMap(([k, v]) => [
        C.el("dt", {}, C.el("span", { className: "privacy-list__lock privacy-list__lock--" + lock, "aria-hidden": "true" }), k),
        C.el("dd", { text: v })]));
      return C.el("div", { className: "stack" },
        C.el("section", { "aria-labelledby": "pub-public" },
          C.el("h3", { id: "pub-public", className: "privacy-list__title" }, C.badge("Will be public", "sale"), " Visible to everyone"),
          list(publicRows, "open")),
        C.el("section", { "aria-labelledby": "pub-private" },
          C.el("h3", { id: "pub-private", className: "privacy-list__title" }, C.badge("Stays private", "neutral"), " Only you can see these"),
          list(privateRows, "closed")),
        C.el("p", { className: "muted", text: "Publishing sets the request to open. You can cancel it later from your requests." }));
    }

    async function openPublishPreview(opener, box) {
      if (publishing) return;
      const body = C.el("div", {}, C.el("div", { className: "state" }, C.el("div", { className: "spinner", "aria-hidden": "true" }), C.el("p", { text: "Preparing preview…" })));
      const errorBox = C.el("div", { className: "notice notice--error", role: "alert", hidden: true });
      const cancel = C.button({ label: "Cancel", onClick: () => dlg.close("cancel") });
      const confirm = C.button({ label: "Publish now", variant: "leaf", attrs: { disabled: true } });
      const dlg = C.dialog({ title: "Publish this request?", body: C.el("div", {}, errorBox, body), actions: [cancel, confirm] });
      dlg.open(opener);

      let profile = null;
      try { profile = (await api.get("/api/me")).profile; } catch (_) { /* preview falls back to generic wording */ }
      C.clear(body).append(buildPublicPreview(profile));
      confirm.disabled = false;
      confirm.focus();

      confirm.addEventListener("click", async () => {
        if (publishing) return;            // guards double clicks and double submits
        publishing = true;
        showNotice(errorBox, null);
        C.setBusy(confirm, true, "Publishing");
        cancel.disabled = true;
        try {
          const data = await api.post("/api/requests/" + enc(requestId) + "/publish");
          request = data.request;
          dlg.close("published");
          renderHead();
          renderPublishSuccess(box, data.public_preview || null);
          C.toast("Request published.", "leaf");
          const h = box.querySelector("h3"); if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
        } catch (err) {
          C.setBusy(confirm, false);
          cancel.disabled = false;
          if (err instanceof api.ApiError && err.code === "request_closed") showNotice(errorBox, "This request is closed and cannot be published.");
          else if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); showNotice(errorBox, authMessage(err)); }
          else showNotice(errorBox, C.errorMessage(err));
        } finally {
          publishing = false;
        }
      });
    }

    function renderPublishSuccess(box, publicPreview) {
      C.clear(box);
      const pub = publicPreview;
      box.append(
        C.el("div", { className: "notice notice--leaf", role: "status" }, C.el("div", {},
          C.el("h3", { style: { marginBottom: "4px" }, text: publicPreview ? "Published" : "Already published" }),
          C.el("p", { text: "Other members can now see the sanitized version in the public feed. Your exact times, dates, deposit limit, and contact details stay private." }),
          C.el("div", { className: "cluster" },
            C.button({ label: "See it in the public feed", variant: "primary", href: "/requests" }),
            C.statusBadge(request.status), C.badge("Published", "sale")))));
      if (pub) {
        const specs = (o) => Object.entries(o || {}).map(([k, v]) => k.replace(/_/g, " ") + " = " + String(v)).join(", ") || "none";
        box.append(C.el("p", { className: "muted", style: { margin: "var(--space-3) 0 var(--space-1)" }, text: "Exactly what was published:" }),
          C.el("dl", { className: "privacy-list" }, [
            ["Who", pub.requester ? pub.requester.display_name + " (" + pub.requester.badge + ")" : "unknown"],
            ["Item category", pub.category || "unknown"],
            ["Required details", specs(pub.required_specifications)],
            ["Preferred details", specs(pub.preferred_specifications)],
            ["Buy or borrow", (pub.modes || []).length ? pub.modes.map((m) => (m === "sale" ? "buy" : "borrow")).join(" or ") : "unknown"],
            ["Budget", pub.budget_cents != null ? api.formatCents(pub.budget_cents) : "unknown"],
            ["Needed by", pub.needed_by_date || "unknown"],
            ["Campus area", pub.area || "unknown"],
          ].flatMap(([k, v]) => [C.el("dt", {}, C.el("span", { className: "privacy-list__lock privacy-list__lock--open", "aria-hidden": "true" }), k), C.el("dd", { text: v })])));
      }
    }

    function matchCard(entry, kind) {
      const listing = entry.listing || {};
      const owner = listing.owner || {};
      const allowed = listing.allowed_modes || [];
      const mode = entry.mode || (allowed.length === 1 ? allowed[0] : null);

      const badges = [];
      if (mode) badges.push(C.modeBadge(mode));
      else allowed.forEach((m) => badges.push(C.modeBadge(m)));
      if (kind === "needs") badges.push(C.badge("Needs confirmation", "warn"));
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));

      // Money: show only what the listing actually offers for the relevant mode(s).
      const money = C.el("div", { className: "stack--tight match-money" });
      const showSale = allowed.includes("sale") && (mode === "sale" || !mode);
      const showBorrow = allowed.includes("borrow") && (mode === "borrow" || !mode);
      if (showSale) {
        money.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.sale_price_cents) }), C.el("span", { className: "muted", text: " to buy" })));
      }
      if (showBorrow) {
        const fee = listing.rental_fee_cents === 0 ? "Free loan" : api.formatCents(listing.rental_fee_cents) + " rental fee";
        money.append(C.el("div", {}, C.el("span", { className: "price", text: fee })));
        money.append(C.el("div", { className: "muted" }, depositProposalText(listing)));
      }
      if (!showSale && !showBorrow) money.append(C.el("div", { className: "muted", text: "Terms unknown" }));

      const reasons = C.el("ul", { className: "reasons" });
      (entry.reasons || []).forEach((r) => reasons.append(C.el("li", { className: "reason reason--ok", text: String(r) })));
      (entry.unknown_required || []).forEach((u) => reasons.append(C.el("li", { className: "reason reason--unknown", text: "Needs confirmation: " + String(u).replace(/_/g, " ") })));
      (entry.shortcomings || []).forEach((s) => reasons.append(C.el("li", { className: "reason reason--warn", text: String(s) })));
      if (!reasons.children.length) reasons.append(C.el("li", { className: "reason reason--unknown", text: "No explanation was provided." }));

      const specs = Object.entries(listing.specifications || {}).slice(0, 4);
      const specList = specs.length ? C.el("dl", { className: "specs" }, specs.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: String(v) })])) : null;

      const footer = [
        C.el("span", { className: "cluster" }, C.el("span", { className: "muted", text: owner.display_name || "Owner" }), C.profileBadge(owner)),
        C.el("span", { className: "cluster" },
          typeof entry.score === "number" ? C.badge("fit " + entry.score.toFixed(2), "neutral") : null,
          C.button({ label: "View listing", size: "sm", variant: kind === "confirmed" ? "primary" : "default", href: "/listings/" + enc(listing.id || "") })),
      ];

      return C.card({
        variant: ["compact"].concat(kind === "needs" ? ["needs"] : []),
        media: { src: listing.public_photo_url, alt: listing.public_photo_url ? "Photo of " + (listing.title || "listing") : "" },
        title: listing.title || "Untitled listing",
        subtitle: [listing.category, listing.condition ? "condition " + String(listing.condition).replace("_", " ") : "condition unknown"].filter(Boolean).join(" · "),
        badges,
        body: [money, specList, C.el("h4", { className: "reasons__title", text: kind === "confirmed" ? "Why it matches" : "What still needs checking" }), reasons],
        footer,
      });
    }
  }

  // Owner's deposit proposal in dollars and percent. Pure arithmetic on the
  // listing's own fields; "unknown" when either input is missing.
  function depositProposalText(listing) {
    const value = listing.proposed_item_value_cents;
    const pct = listing.collateral_percent;
    if (!Number.isInteger(value) || !Number.isInteger(pct)) return "Deposit proposal unknown (owner has not set value or percent)";
    const deposit = Math.round((value * pct) / 100);
    return "Proposed deposit " + api.formatCents(deposit) + " (" + pct + "% of " + api.formatCents(value) + " agreed value). Simulated in this prototype.";
  }

  // ------------------------------------------------ interpretation form (shared)
  // buildInterpretationForm(container, values, meta) -> {fields, read()}
  // Unknown values show an "unknown" badge; ambiguous dates and an unconfirmed
  // mode show "needs confirmation". read() validates and returns {ok, values}.
  function buildInterpretationForm(container, values, meta) {
    meta = meta || {};
    const F = {};
    const unknownBadge = () => C.badge("unknown", "neutral");
    const confirmBadge = () => C.badge("needs confirmation", "warn");
    const markLabel = (fieldApi, badge) => { fieldApi.root.querySelector(".field__label").append(badge); };

    const modesErr = C.el("p", { className: "field__error", id: "modes-error", role: "alert" });
    const modesGroup = C.el("fieldset", {},
      C.el("legend", {}, "Buy or borrow? ", meta.modesUnknown ? confirmBadge() : null),
      C.el("p", { className: "field__hint", id: "modes-hint", text: meta.modesUnknown
        ? "The interpreter did not say. Both are selected as a search preference; confirm or narrow it."
        : "Pick at least one. Both is fine as a search preference." }),
      C.el("div", { className: "choices" },
        choice("modes", "borrow", "Borrow", (values.modes || []).includes("borrow")),
        choice("modes", "sale", "Buy", (values.modes || []).includes("sale"))),
      modesErr);
    F.modes = { control: modesGroup, setError(m) { modesErr.textContent = m || ""; }, clearError() { modesErr.textContent = ""; } };

    F.category = C.field({ id: "f-category", label: "Category", type: "select", value: values.category || "",
      options: CATEGORIES.map(([value, label]) => ({ value, label })) });
    if (values.category && !CATEGORIES.some(([v]) => v === values.category)) {
      F.category.control.append(C.el("option", { value: values.category, text: values.category }));
      F.category.control.value = values.category;
    }
    if (!values.category) markLabel(F.category, unknownBadge());

    const requiredSpecs = kvEditor("Required specifications", "Must match exactly, e.g. jacket_size = 40R. Unknown required details become “needs confirmation”, never a confirmed match.", values.required_specifications || {});
    const preferredSpecs = kvEditor("Preferred specifications", "Nice to have, e.g. color = navy. Used for ranking only.", values.preferred_specifications || {});
    F.required_specifications = requiredSpecs;
    F.preferred_specifications = preferredSpecs;

    F.budget_cents = C.field({ id: "f-budget", label: "Purchase or rental budget", type: "text", prefix: "$", optional: true,
      attrs: { inputmode: "decimal" }, placeholder: "unknown", value: C.centsToDollars(values.budget_cents),
      hint: "The most you would pay to buy, or as a rental fee." });
    F.max_deposit_cents = C.field({ id: "f-deposit", label: "Deposit you can afford", type: "text", prefix: "$", optional: true,
      attrs: { inputmode: "decimal" }, placeholder: "unknown", value: C.centsToDollars(values.max_deposit_cents),
      hint: "Separate from your budget. A free loan can still be unaffordable if the deposit is too high. Deposits are simulated in this prototype." });
    if (values.budget_cents == null) markLabel(F.budget_cents, unknownBadge());
    if (values.max_deposit_cents == null) markLabel(F.max_deposit_cents, unknownBadge());

    F.needed_by = C.field({ id: "f-needed-by", label: "Needed by", type: "datetime-local", optional: true, value: C.isoToLocal(values.needed_by),
      hint: "Times are read in your browser's time zone and shown in America/New_York." });
    F.use_start = C.field({ id: "f-use-start", label: "Borrowing starts", type: "datetime-local", optional: true, value: C.isoToLocal(values.use_start) });
    F.use_end = C.field({ id: "f-use-end", label: "Borrowing ends", type: "datetime-local", optional: true, value: C.isoToLocal(values.use_end) });
    const ambiguousTargets = new Set((meta.ambiguous || []).map((a) => a.field).filter(Boolean));
    [["needed_by", F.needed_by], ["use_start", F.use_start], ["use_end", F.use_end]].forEach(([key, f]) => {
      if (ambiguousTargets.has(key) || ((meta.ambiguous || []).length && values[key])) markLabel(f, confirmBadge());
      else if (!values[key]) markLabel(f, unknownBadge());
    });

    F.area = C.field({ id: "f-area", label: "Campus area for pickup", type: "text", optional: true, placeholder: "unknown", value: values.area || "", attrs: { maxlength: 80 } });
    if (!values.area) markLabel(F.area, unknownBadge());

    container.append(
      modesGroup,
      C.el("div", { className: "field-row" }, F.category.root, F.area.root),
      requiredSpecs.root,
      preferredSpecs.root,
      C.el("div", { className: "field-row" }, F.budget_cents.root, F.max_deposit_cents.root),
      C.el("div", { className: "field-row" }, F.needed_by.root, F.use_start.root, F.use_end.root),
    );

    function read() {
      Object.values(F).forEach((f) => f.clearError && f.clearError());
      const modes = Array.from(container.querySelectorAll('input[name="modes"]:checked')).map((i) => i.value);
      let bad = false;
      if (!modes.length) { F.modes.setError("Choose buy, borrow, or both."); bad = true; }
      const budget = C.dollarsToCents(F.budget_cents.value());
      if (budget.error) { F.budget_cents.setError(budget.error); bad = true; }
      const deposit = C.dollarsToCents(F.max_deposit_cents.value());
      if (deposit.error) { F.max_deposit_cents.setError(deposit.error); bad = true; }
      const dates = {};
      for (const key of ["needed_by", "use_start", "use_end"]) {
        const iso = C.localToIso(F[key].value());
        if (iso === undefined) { F[key].setError("Enter a valid date and time."); bad = true; }
        dates[key] = iso || null;
      }
      if (dates.use_start && dates.use_end && dates.use_end <= dates.use_start) { F.use_end.setError("Must be after the start."); bad = true; }
      if (modes.length === 1 && modes[0] === "sale" && (dates.use_start || dates.use_end)) {
        F.use_start.setError("Borrowing dates only apply when borrowing is selected."); bad = true;
      }
      if (bad) {
        const first = (!modes.length && container.querySelector('input[name="modes"]')) || container.querySelector('[aria-invalid="true"]');
        if (first) first.focus();
        return { ok: false };
      }
      return {
        ok: true,
        values: {
          modes,
          category: F.category.value() || null,
          required_specifications: requiredSpecs.value(),
          preferred_specifications: preferredSpecs.value(),
          budget_cents: budget.cents,
          max_deposit_cents: deposit.cents,
          needed_by: dates.needed_by,
          use_start: dates.use_start,
          use_end: dates.use_end,
          area: F.area.value().trim() || null,
        },
      };
    }

    return { fields: F, read };
  }

  function choice(name, value, label, checked) {
    const input = C.el("input", { type: "checkbox", name, value, "aria-describedby": "modes-hint modes-error" });
    input.checked = !!checked;
    return C.el("label", { className: "choice" }, input, C.el("span", { text: label }));
  }

  // ============================================================ LISTING FORM
  function initListingForm() {
    const form = $("listing-form");
    const fieldsBox = $("listing-fields");
    const errorBox = $("listing-error");
    const submit = $("listing-submit");
    const status = $("listing-status");
    const authGate = $("auth-gate");
    let submitting = false;

    function refreshGate() {
      const signedIn = !!api.getToken();
      authGate.hidden = signedIn;
      submit.disabled = !signedIn;
    }
    document.addEventListener("campus:auth-changed", refreshGate);
    refreshGate();

    // ---- basics
    const F = {};
    F.title = C.field({ id: "l-title", label: "Title", required: true, placeholder: "e.g. Navy suit, 40R", attrs: { maxlength: 120 }, hint: "Required." });
    F.category = C.field({ id: "l-category", label: "Category", type: "select", required: true,
      options: CATEGORIES.map(([value, label]) => ({ value, label: value ? label : "Choose a category" })), hint: "Required." });
    F.description = C.field({ id: "l-description", label: "Description", type: "textarea", optional: true, rows: 4, attrs: { maxlength: 4000 },
      placeholder: "What it is, how it has been used, anything a borrower or buyer should know." });
    F.condition = C.field({ id: "l-condition", label: "Condition", type: "select", options: CONDITIONS.map(([value, label]) => ({ value, label })), hint: "Leave as unknown if you are not sure." });
    const specs = kvEditor("Specifications", "Size, model, dimensions, color: anything a matcher should check exactly (e.g. jacket_size = 40R).", {}, { badge: false });
    F.specifications = specs;
    F.accessories = C.field({ id: "l-accessories", label: "Included accessories", type: "textarea", optional: true, rows: 2, placeholder: "One per line, e.g. garment bag", hint: "One per line." });
    F.known_defects = C.field({ id: "l-defects", label: "Known defects", type: "textarea", optional: true, rows: 2, placeholder: "One per line, e.g. missing one cuff button", hint: "One per line. Be honest; condition is confirmed at handoff." });

    // ---- photo
    F.photo = C.field({ id: "l-photo", label: "Photo", type: "file", optional: true, attrs: { accept: "image/jpeg,image/png,image/webp" },
      hint: "JPEG, PNG, or WebP up to 5 MB. Uploaded after the listing is created." });
    const photoPreview = C.el("div", { className: "photo-preview", hidden: true }, C.el("img", { alt: "Preview of the chosen photo" }));
    F.photo.root.append(photoPreview);
    F.photo.control.addEventListener("change", () => {
      const file = F.photo.control.files[0];
      F.photo.clearError();
      if (!file) { photoPreview.hidden = true; return; }
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) { F.photo.setError("Choose a JPEG, PNG, or WebP image."); photoPreview.hidden = true; return; }
      if (file.size > 5 * 1024 * 1024) { F.photo.setError("That photo is over 5 MB."); photoPreview.hidden = true; return; }
      photoPreview.querySelector("img").src = URL.createObjectURL(file);
      photoPreview.hidden = false;
    });

    // ---- modes
    const modesErr = C.el("p", { className: "field__error", id: "l-modes-error", role: "alert" });
    const modeSale = choiceInput("allowed_modes", "sale", "For sale", false, "l-modes-hint l-modes-error");
    const modeBorrow = choiceInput("allowed_modes", "borrow", "To borrow", true, "l-modes-hint l-modes-error");
    const modesGroup = C.el("fieldset", {},
      C.el("legend", { text: "How can people get it?" }),
      C.el("p", { className: "field__hint", id: "l-modes-hint", text: "Required. Pick one or both. Only the matching price fields are shown." }),
      C.el("div", { className: "choices" }, modeSale.label, modeBorrow.label),
      modesErr);
    F.allowed_modes = { control: modesGroup, setError(m) { modesErr.textContent = m || ""; }, clearError() { modesErr.textContent = ""; } };

    // ---- sale terms
    F.sale_price_cents = C.field({ id: "l-sale-price", label: "Asking sale price", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "e.g. 90", hint: "Required for sale." });
    const saleGroup = C.el("fieldset", { id: "l-sale-group" }, C.el("legend", { text: "Sale terms" }), F.sale_price_cents.root);

    // ---- borrow terms
    F.rental_fee_cents = C.field({ id: "l-rental-fee", label: "Rental fee", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "0", value: "0",
      hint: "$0 means an explicit free loan. This is payment for use, separate from the deposit." });
    F.proposed_item_value_cents = C.field({ id: "l-item-value", label: "Agreed item value", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "e.g. 200",
      hint: "Required for borrowing. The reference value if the item is not returned; not a market guarantee." });
    F.collateral_percent = C.field({ id: "l-percent", label: "Deposit you propose", type: "number", value: "100", attrs: { min: 0, max: 100, step: 1, inputmode: "numeric" },
      hint: "Percent of the agreed value, 0 to 100. Default 100%. Lowering it is voluntary and leaves the rest of the value at your risk." });
    const slider = C.el("input", { type: "range", min: 0, max: 100, step: 1, value: 100, "aria-label": "Deposit percent slider", className: "range" });
    F.collateral_percent.root.insertBefore(slider, F.collateral_percent.root.querySelector(".field__error"));
    const depositCalc = C.el("div", { className: "deposit-calc", "aria-live": "polite" });
    const lowNote = C.el("div", { className: "notice notice--warn", role: "note", hidden: true },
      C.el("div", {}, C.el("strong", { text: "Below full value. " }), "When an offer is made, you will be asked to explicitly acknowledge the amount not covered before your acceptance counts. The platform does not guarantee reimbursement."));
    F.available_from = C.field({ id: "l-avail-from", label: "Available from", type: "datetime-local", optional: true });
    F.available_until = C.field({ id: "l-avail-until", label: "Available until", type: "datetime-local", optional: true });
    F.availability_notes = C.field({ id: "l-avail-notes", label: "Availability notes", optional: true, placeholder: "e.g. most weekdays after 2pm", attrs: { maxlength: 200 } });
    const borrowGroup = C.el("fieldset", { id: "l-borrow-group" },
      C.el("legend", { text: "Borrowing terms" }),
      C.el("div", { className: "field-row" }, F.rental_fee_cents.root, F.proposed_item_value_cents.root),
      F.collateral_percent.root,
      depositCalc, lowNote,
      C.el("h3", { style: { marginTop: "var(--space-4)" }, text: "Availability" }),
      C.el("div", { className: "field-row" }, F.available_from.root, F.available_until.root),
      F.availability_notes.root);

    // ---- meeting spots
    const spotsBox = C.el("div", { id: "l-spots" });
    const spotsErr = C.el("p", { className: "field__error", role: "alert" });
    const spotsGroup = C.el("fieldset", {},
      C.el("legend", { text: "Preferred public meeting spots" }),
      C.el("p", { className: "field__hint", text: "Optional. Public, well-lit campus spots. Suggested locations do not guarantee safety." }),
      spotsBox, spotsErr);
    F.meeting_spot_ids = { control: spotsBox, setError(m) { spotsErr.textContent = m || ""; }, clearError() { spotsErr.textContent = ""; } };
    loadSpots();
    async function loadSpots() {
      C.state.loading(spotsBox, "Loading meeting spots…");
      try {
        const { meeting_spots } = await api.get("/api/meeting-spots");
        C.clear(spotsBox);
        if (!meeting_spots.length) { C.state.empty(spotsBox, { title: "No meeting spots yet", message: "You can still post; spots can be agreed in the exchange." }); return; }
        spotsBox.append(C.el("div", { className: "choices" }, meeting_spots.map((s) =>
          choiceInput("meeting_spot_ids", s.id, s.label + " (" + s.public_area + ")", false).label)));
      } catch (err) {
        C.state.error(spotsBox, err, { title: "Could not load meeting spots", retry: loadSpots });
      }
    }

    fieldsBox.append(
      C.el("div", { className: "field-row" }, F.title.root, F.category.root),
      F.description.root,
      C.el("div", { className: "field-row" }, F.condition.root, F.photo.root),
      specs.root, F.accessories.root, F.known_defects.root,
      modesGroup, saleGroup, borrowGroup, spotsGroup);

    // ---- live behavior
    function syncModes() {
      saleGroup.hidden = !modeSale.input.checked;
      borrowGroup.hidden = !modeBorrow.input.checked;
      if (modeSale.input.checked || modeBorrow.input.checked) F.allowed_modes.clearError();
    }
    modeSale.input.addEventListener("change", syncModes);
    modeBorrow.input.addEventListener("change", syncModes);
    syncModes();

    function updateDeposit() {
      const value = C.dollarsToCents(F.proposed_item_value_cents.value());
      let pct = parseInt(F.collateral_percent.value(), 10);
      if (Number.isNaN(pct)) pct = null;
      C.clear(depositCalc);
      if (value.cents == null || pct == null || pct < 0 || pct > 100) {
        depositCalc.append(C.el("p", { className: "muted", text: "Enter the agreed value and a percent to see the proposed deposit." }));
        lowNote.hidden = true;
        return;
      }
      const deposit = Math.round((value.cents * pct) / 100);
      const uncovered = Math.max(value.cents - deposit, 0);
      depositCalc.append(
        C.el("dl", { className: "kv-list" },
          C.el("dt", { text: "Proposed deposit (simulated)" }), C.el("dd", { text: api.formatCents(deposit) + " (" + pct + "% of " + api.formatCents(value.cents) + ")" }),
          C.el("dt", { text: "Not covered by deposit" }), C.el("dd", { className: uncovered > 0 ? "kv-list__warn" : "", text: api.formatCents(uncovered) })));
      lowNote.hidden = uncovered === 0;
    }
    slider.addEventListener("input", () => { F.collateral_percent.control.value = slider.value; updateDeposit(); });
    F.collateral_percent.control.addEventListener("input", () => { const v = parseInt(F.collateral_percent.value(), 10); if (!Number.isNaN(v)) slider.value = Math.min(100, Math.max(0, v)); updateDeposit(); });
    F.proposed_item_value_cents.control.addEventListener("input", updateDeposit);
    updateDeposit();

    // ---- submit
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (submitting) return;
      showNotice(errorBox, null);
      Object.values(F).forEach((f) => f.clearError && f.clearError());

      let bad = false;
      const title = F.title.value().trim();
      if (!title) { F.title.setError("Give the item a title."); bad = true; }
      const category = F.category.value();
      if (!category) { F.category.setError("Choose a category."); bad = true; }
      const modes = [modeSale.input.checked ? "sale" : null, modeBorrow.input.checked ? "borrow" : null].filter(Boolean);
      if (!modes.length) { F.allowed_modes.setError("Pick sale, borrowing, or both."); bad = true; }

      const body = {
        title, category,
        description: F.description.value().trim() || null,
        condition: F.condition.value() || null,
        specifications: specs.value(),
        accessories: lines(F.accessories.value()),
        known_defects: lines(F.known_defects.value()),
        allowed_modes: modes,
        meeting_spot_ids: Array.from(spotsBox.querySelectorAll('input[name="meeting_spot_ids"]:checked')).map((i) => i.value),
        availability: {},
      };

      if (modes.includes("sale")) {
        const p = C.dollarsToCents(F.sale_price_cents.value());
        if (p.error) { F.sale_price_cents.setError(p.error); bad = true; }
        else if (p.cents == null) { F.sale_price_cents.setError("Enter an asking price for sale."); bad = true; }
        body.sale_price_cents = p.cents;
      }
      if (modes.includes("borrow")) {
        const fee = C.dollarsToCents(F.rental_fee_cents.value());
        if (fee.error) { F.rental_fee_cents.setError(fee.error); bad = true; }
        body.rental_fee_cents = fee.cents == null ? 0 : fee.cents; // blank = explicit free loan
        const value = C.dollarsToCents(F.proposed_item_value_cents.value());
        if (value.error) { F.proposed_item_value_cents.setError(value.error); bad = true; }
        else if (value.cents == null) { F.proposed_item_value_cents.setError("Enter the agreed item value for borrowing."); bad = true; }
        body.proposed_item_value_cents = value.cents;
        const pct = parseInt(F.collateral_percent.value(), 10);
        if (Number.isNaN(pct) || pct < 0 || pct > 100) { F.collateral_percent.setError("Enter a whole number from 0 to 100."); bad = true; }
        body.collateral_percent = Number.isNaN(pct) ? null : pct;
        const from = C.localToIso(F.available_from.value());
        const until = C.localToIso(F.available_until.value());
        if (from === undefined) { F.available_from.setError("Enter a valid date and time."); bad = true; }
        if (until === undefined) { F.available_until.setError("Enter a valid date and time."); bad = true; }
        if (from && until && until <= from) { F.available_until.setError("Must be after the start."); bad = true; }
        body.availability = { available_from: from || null, available_until: until || null, notes: F.availability_notes.value().trim() || null };
      }
      const file = F.photo.control.files[0] || null;
      if (file && F.photo.root.querySelector(".field__error").textContent) bad = true;

      if (bad) {
        showNotice(errorBox, "Some fields need attention; see the messages next to them.");
        const first = form.querySelector('[aria-invalid="true"]') || (!modes.length ? modeSale.input : null);
        if (first) first.focus(); // after the banner so the first invalid field keeps focus
        return;
      }

      submitting = true;
      C.setBusy(submit, true, "Saving listing");
      status.textContent = "Saving listing…";
      let listing;
      try {
        listing = (await api.post("/api/listings", body)).listing;
      } catch (err) {
        submitting = false;
        C.setBusy(submit, false);
        status.textContent = "";
        if (err instanceof api.ApiError && err.code === "validation_error") {
          const leftovers = C.applyFieldErrors(F, err.fields);
          showNotice(errorBox, leftovers.length ? "Please fix: " + leftovers.join("; ") : "Some fields need attention; see the messages next to them.");
        } else if (C.isAuthError(err)) {
          if (err.status === 401) api.setToken(null);
          showNotice(errorBox, authMessage(err));
        } else {
          showNotice(errorBox, C.errorMessage(err));
        }
        return;
      }
      let photoFailed = false;
      if (file) {
        status.textContent = "Uploading photo…";
        try { await api.upload("/api/listings/" + enc(listing.id) + "/photo", "photo", file); }
        catch (err) { photoFailed = true; C.toast("Listing saved, but the photo upload failed: " + C.errorMessage(err), "error", 6000); }
      }
      window.location.href = "/listings/" + enc(listing.id) + (photoFailed ? "?photo=failed" : "?created=1");
    });

    function lines(text) { return String(text || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean); }
  }

  function choiceInput(name, value, label, checked, describedBy) {
    const input = C.el("input", { type: "checkbox", name, value, "aria-describedby": describedBy || null });
    input.checked = !!checked;
    return { input, label: C.el("label", { className: "choice" }, input, C.el("span", { text: label })) };
  }

  // ========================================================== LISTING DETAIL
  function initListingDetail() {
    const root = $("listing-root");
    const listingId = root.dataset.listingId;
    const params = new URLSearchParams(window.location.search);
    load();
    document.addEventListener("campus:auth-changed", load);

    async function load() {
      root.setAttribute("aria-busy", "true");
      C.state.loading(root, "Loading listing…");
      try {
        const [{ listing }, spotsRes, me] = await Promise.all([
          api.get("/api/listings/" + enc(listingId)),
          api.get("/api/meeting-spots").catch(() => null),
          api.getToken() ? api.get("/api/me").catch(() => null) : Promise.resolve(null),
        ]);
        root.removeAttribute("aria-busy");
        render(listing, spotsRes ? spotsRes.meeting_spots : null, me ? me.profile : null);
      } catch (err) {
        root.removeAttribute("aria-busy");
        if (err instanceof api.ApiError && err.status === 404) {
          C.state.error(root, { message: "It may have been removed, or the link is wrong." }, { title: "Listing not found", action: C.button({ label: "Browse listings", variant: "primary", size: "sm", href: "/" }) });
        } else {
          C.state.error(root, err, { title: "Could not load this listing", retry: load });
        }
      }
    }

    function render(listing, spots, me) {
      C.clear(root);
      document.title = listing.title + " · Campus Current";
      const owner = listing.owner || {};
      const isMine = me && me.id === listing.owner_id;
      const allowed = listing.allowed_modes || [];

      if (params.get("created") === "1") root.append(C.notice("leaf", C.el("span", {}, C.el("strong", { text: "Listing published. " }), "It now appears in search results and on the home page.")));
      if (params.get("photo") === "failed") root.append(C.notice("warn", "The listing was saved, but the photo upload failed. You can add a photo later."));

      // ---- header
      const badges = [];
      allowed.forEach((m) => badges.push(C.modeBadge(m)));
      badges.push(C.statusBadge(listing.status));
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));
      if (isMine) badges.push(C.badge("Your listing", "info"));

      const media = C.el("div", { className: "detail-media" + (listing.public_photo_url ? "" : " detail-media--empty") });
      if (listing.public_photo_url) media.append(C.el("img", { src: listing.public_photo_url, alt: "Photo of " + listing.title }));
      else media.append(C.el("span", { text: "No photo provided" }));

      const facts = C.el("div", { className: "stack" },
        C.el("div", { className: "cluster" }, badges),
        C.el("h1", { style: { marginBottom: "4px" }, text: listing.title }),
        C.el("div", { className: "meta" }, C.el("span", { text: listing.category || "uncategorized" }), C.el("span", { text: "condition: " + conditionLabel(listing.condition) })),
        listing.description ? C.el("p", { text: listing.description }) : C.el("p", { className: "muted", text: "No description provided." }),
        section("Specifications", kv(listing.specifications, "No specifications listed.")),
        section("Included accessories", stringList(listing.accessories, "None listed.")),
        section("Known defects", stringList(listing.known_defects, "None listed.")));

      // ---- terms: every amount on its own row, never derived from each other
      const terms = C.el("dl", { className: "kv-list" });
      const row = (k, v, cls) => terms.append(C.el("dt", { text: k }), C.el("dd", { className: cls || "" }, v));
      if (allowed.includes("sale")) row("Sale price", api.formatCents(listing.sale_price_cents));
      if (allowed.includes("borrow")) {
        row("Rental fee", listing.rental_fee_cents === 0 ? "Free loan ($0.00)" : api.formatCents(listing.rental_fee_cents));
        row("Agreed item value", api.formatCents(listing.proposed_item_value_cents));
        const value = listing.proposed_item_value_cents, pct = listing.collateral_percent;
        if (Number.isInteger(value) && Number.isInteger(pct)) {
          const deposit = Math.round((value * pct) / 100);
          const uncovered = Math.max(value - deposit, 0);
          row("Deposit proposed (simulated)", api.formatCents(deposit) + " (" + pct + "% of value)");
          row("Not covered by deposit", api.formatCents(uncovered), uncovered > 0 ? "kv-list__warn" : "");
        } else {
          row("Deposit proposed (simulated)", "unknown");
        }
        const av = listing.availability || {};
        row("Available", (av.available_from || av.available_until)
          ? (av.available_from ? "from " + api.formatTime(av.available_from) : "") + (av.available_until ? " until " + api.formatTime(av.available_until) : "")
          : "no fixed dates");
        if (av.notes) row("Availability notes", av.notes);
      }
      if (!allowed.length) row("Terms", "unknown");

      // ---- meeting spots
      const spotIds = new Set(listing.meeting_spot_ids || []);
      let spotsNode;
      if (!spotIds.size) spotsNode = C.el("p", { className: "muted", text: "No preferred spots listed; agree one in the exchange." });
      else if (!spots) spotsNode = C.el("p", { className: "muted", text: spotIds.size + " preferred spot(s); details could not be loaded." });
      else {
        const chosen = spots.filter((s) => spotIds.has(s.id));
        spotsNode = C.el("ul", { className: "spot-list" }, chosen.map((s) => C.el("li", {}, C.el("strong", { text: s.label }), C.el("span", { className: "muted", text: " · " + s.public_area + (s.access_notes ? " · " + s.access_notes : "") }))));
      }

      const startBtn = C.button({ label: "Start exchange", variant: "primary", attrs: { disabled: true, "aria-describedby": "start-hint" } });
      const startHint = C.el("p", { className: "muted", id: "start-hint", text: isMine
        ? "This is your own listing."
        : listing.status !== "available" ? "This item is " + listing.status + " right now."
        : "Messaging and offers are coming next (exchange room). This button will open a private exchange with the owner." });

      const side = C.el("div", { className: "stack" },
        C.el("section", { className: "card card--sky", "aria-labelledby": "terms-heading" },
          C.el("h2", { id: "terms-heading", text: "Terms" }), terms,
          C.simulationNotice()),
        C.el("section", { className: "card", "aria-labelledby": "spots-heading" },
          C.el("h2", { id: "spots-heading", text: "Meeting spots" }), spotsNode),
        C.el("section", { className: "card card--leaf", "aria-labelledby": "owner-heading" },
          C.el("h2", { id: "owner-heading", text: "Owner" }),
          C.el("div", { className: "cluster" }, C.el("strong", { text: owner.display_name || "Unknown" }), C.profileBadge(owner)),
          C.el("p", { className: "muted", style: { marginTop: "8px" }, text: "A verification badge only confirms a UNC email; it is not proof of student status or trustworthiness." }),
          C.el("div", { style: { marginTop: "var(--space-3)" } }, startBtn), startHint));

      root.append(C.el("div", { className: "detail-grid" },
        C.el("div", { className: "card" }, media, facts),
        side));
      const h1 = root.querySelector("h1"); h1.setAttribute("tabindex", "-1"); h1.focus();
    }

    function section(title, node) { return C.el("section", {}, C.el("h2", { style: { fontSize: "1.05rem", marginBottom: "6px" }, text: title }), node); }
    function kv(obj, emptyText) {
      const entries = Object.entries(obj || {});
      if (!entries.length) return C.el("p", { className: "muted", text: emptyText });
      return C.el("dl", { className: "specs" }, entries.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: typeof v === "object" ? JSON.stringify(v) : String(v) })]));
    }
    function stringList(arr, emptyText) {
      if (!arr || !arr.length) return C.el("p", { className: "muted", text: emptyText });
      return C.el("ul", { style: { margin: 0, paddingLeft: "1.2em" } }, arr.map((s) => C.el("li", { text: String(s) })));
    }
  }

  // =========================================================== REQUEST FEED
  function initRequestsFeed() {
    const grid = $("feed");
    const authBox = $("feed-auth");
    const modeSel = $("filter-mode");
    const areaSel = $("filter-area");
    const count = $("feed-count");
    let requests = [];
    let me = null;      // public profile of the signed-in user, or null

    modeSel.addEventListener("change", renderFeed);
    areaSel.addEventListener("change", renderFeed);
    document.addEventListener("campus:auth-changed", load);
    load();

    async function load() {
      grid.setAttribute("aria-busy", "true");
      C.state.loading(grid, "Loading open requests…");
      count.textContent = "";
      me = null;
      try {
        const [feed, meRes] = await Promise.all([
          api.get("/api/requests"),
          api.getToken() ? api.get("/api/me").catch(() => null) : Promise.resolve(null),
        ]);
        me = meRes ? meRes.profile : null;
        // Defensive: the server already returns only open + public requests.
        requests = (feed.requests || []).filter((r) => r.status === "open");
        grid.removeAttribute("aria-busy");
        renderAuthNotice();
        fillAreas();
        renderFeed();
      } catch (err) {
        grid.removeAttribute("aria-busy");
        C.state.error(grid, err, { title: "Could not load requests", retry: load });
      }
    }

    function renderAuthNotice() {
      C.clear(authBox);
      if (me) { authBox.hidden = true; return; }
      authBox.append(C.el("div", {},
        C.el("strong", { text: "Browsing only. " }),
        "To respond to a request you need a confirmed UNC email. ",
        C.el("a", { href: "/sign-in", text: "Sign in" }), "."));
      authBox.hidden = false;
    }

    function fillAreas() {
      const current = areaSel.value;
      const areas = Array.from(new Set(requests.map((r) => r.area).filter(Boolean))).sort((a, b) => a.localeCompare(b));
      C.clear(areaSel).append(C.el("option", { value: "", text: "Any area" }));
      areas.forEach((a) => areaSel.append(C.el("option", { value: a, text: a })));
      if (requests.some((r) => !r.area)) areaSel.append(C.el("option", { value: "__none__", text: "Area not given" }));
      if (Array.from(areaSel.options).some((o) => o.value === current)) areaSel.value = current;
    }

    function renderFeed() {
      const mode = modeSel.value;
      const area = areaSel.value;
      const shown = requests.filter((r) =>
        (!mode || (r.modes || []).includes(mode)) &&
        (!area || (area === "__none__" ? !r.area : r.area === area)));
      C.clear(grid);
      if (!requests.length) {
        count.textContent = "";
        C.state.empty(grid, { title: "No open requests right now", message: "When someone publishes a request, it will appear here.",
          action: C.button({ label: "Post a request", variant: "primary", size: "sm", href: "/" }) });
        return;
      }
      count.textContent = shown.length === requests.length
        ? requests.length + (requests.length === 1 ? " open request" : " open requests")
        : shown.length + " of " + requests.length + " open requests match";
      if (!shown.length) {
        C.state.empty(grid, { title: "No requests match these filters", message: "Try a different area or clear the buy/borrow filter.",
          action: C.button({ label: "Clear filters", size: "sm", onClick: () => { modeSel.value = ""; areaSel.value = ""; renderFeed(); modeSel.focus(); } }) });
        return;
      }
      shown.forEach((r) => grid.append(requestCard(r)));
    }

    // Public fields only (docs/contracts.md -> NeedRequest public view).
    function requestCard(r) {
      const requester = r.requester || {};
      const mine = !!(me && requester.id && requester.id === me.id);
      const modes = r.modes || [];
      const badges = modes.map((m) => C.badge(m === "sale" ? "Wants to buy" : "Wants to borrow", m === "sale" ? "sale" : "borrow"));
      if (mine) badges.push(C.badge("Your request", "info"));
      if (requester.is_demo) badges.push(C.badge("Demo account", "fixture"));

      const specs = Object.entries(r.required_specifications || {});
      const prefs = Object.entries(r.preferred_specifications || {});
      const item = C.el("div", { className: "stack--tight" },
        C.el("div", { className: "req-item", text: r.category ? capitalize(r.category) : "Item not specified" }),
        specs.length ? C.el("dl", { className: "specs" }, specs.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: String(v) })])) : C.el("p", { className: "muted", text: "No required details given." }),
        prefs.length ? C.el("p", { className: "muted", text: "Prefers " + prefs.map(([k, v]) => k.replace(/_/g, " ") + " " + String(v)).join(", ") }) : null);

      const facts = C.el("dl", { className: "kv-list kv-list--plain" },
        C.el("dt", { text: "Needed by" }), C.el("dd", { text: formatDateOnly(r.needed_by_date) }),
        C.el("dt", { text: "Campus area" }), C.el("dd", { text: r.area || "not given" }),
        C.el("dt", { text: "Budget" }), C.el("dd", { text: r.budget_cents != null ? "up to " + api.formatCents(r.budget_cents) : "not given" }));

      let action;
      if (mine) {
        action = C.button({ label: "View matches", size: "sm", href: "/results/" + enc(r.id) });
      } else if (me) {
        action = C.el("span", { className: "cluster" },
          C.button({ label: "I have this", variant: "leaf", size: "sm", attrs: { disabled: true, "aria-describedby": "have-hint-" + r.id } }),
          C.el("span", { className: "visually-hidden", id: "have-hint-" + r.id, text: "Responding to requests is coming soon." }));
      } else {
        action = C.button({ label: "Sign in to respond", size: "sm", href: "/sign-in" });
      }

      return C.card({
        variant: ["compact"],
        badges,
        body: [item, facts],
        footer: [
          C.el("span", { className: "cluster" }, C.el("span", { className: "muted", text: requester.display_name || "Member" }), C.profileBadge(requester),
            C.el("span", { className: "muted", text: "posted " + api.formatTime(r.created_at) })),
          action,
        ],
      });
    }
  }

  // "2026-10-14" (a date, not a moment) -> "Oct 14, 2026" without time-zone shifting.
  function formatDateOnly(iso) {
    if (!iso) return "not given";
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!m) return String(iso);
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function capitalize(s) { s = String(s); return s.charAt(0).toUpperCase() + s.slice(1); }

  // Key/value editor for specifications. Returns {root, control, value(), setError, clearError}.
  function kvEditor(title, hint, initial, opts) {
    opts = opts || {};
    const rows = C.el("div", { className: "kv-rows" });
    const error = C.el("p", { className: "field__error", role: "alert" });
    const addRow = (key, value) => {
      const k = C.el("input", { type: "text", placeholder: "attribute (e.g. jacket_size)", "aria-label": title + " attribute name", maxlength: 60 });
      const v = C.el("input", { type: "text", placeholder: "value (e.g. 40R)", "aria-label": title + " attribute value", maxlength: 120 });
      if (key != null) k.value = key;
      if (value != null) v.value = typeof value === "object" ? JSON.stringify(value) : String(value);
      const row = C.el("div", { className: "kv-row" }, k, v,
        C.button({ label: "Remove", size: "sm", attrs: { "aria-label": "Remove this " + title.toLowerCase() + " row" }, onClick: () => { row.remove(); if (!rows.children.length) addRow(); } }));
      rows.append(row);
      return row;
    };
    const entries = Object.entries(initial || {});
    if (entries.length) entries.forEach(([k, v]) => addRow(k, v)); else addRow();
    const add = C.button({ label: "+ Add another", size: "sm", onClick: () => { const r = addRow(); r.querySelector("input").focus(); } });
    const legend = C.el("legend", {}, title + " ", (entries.length || opts.badge === false) ? null : C.badge("none known", "neutral"));
    const root = C.el("fieldset", {}, legend, C.el("p", { className: "field__hint", text: hint }), rows, C.el("div", { style: { marginTop: "8px" } }, add), error);
    return {
      root,
      control: rows,
      value() {
        const out = {};
        rows.querySelectorAll(".kv-row").forEach((row) => {
          const [k, v] = row.querySelectorAll("input");
          const key = k.value.trim().toLowerCase().replace(/\s+/g, "_");
          const val = v.value.trim();
          if (key && val) out[key] = /^-?\d+$/.test(val) ? parseInt(val, 10) : val;
        });
        return out;
      },
      setError(m) { error.textContent = m || ""; },
      clearError() { error.textContent = ""; },
    };
  }

  // ------------------------------------------------------------ listings grid
  async function loadListings() {
    const grid = $("listings");
    if (!grid) return;
    grid.setAttribute("aria-busy", "true");
    C.state.loading(grid, "Loading available listings…");
    try {
      const { listings } = await api.get("/api/listings");
      grid.removeAttribute("aria-busy");
      if (!listings || !listings.length) {
        C.state.empty(grid, {
          title: "Nothing listed yet",
          message: "Be the first to offer something for sale or to borrow.",
          action: C.button({ label: "List an item", variant: "primary", size: "sm", href: "/listings/new" }),
        });
        return;
      }
      C.clear(grid);
      listings.forEach((listing) => grid.append(listingCard(listing)));
    } catch (err) {
      grid.removeAttribute("aria-busy");
      C.state.error(grid, err, { title: "Could not load listings", retry: loadListings });
    }
  }

  function listingCard(listing) {
    const owner = listing.owner || {};
    const badges = [];
    (listing.allowed_modes || []).forEach((m) => badges.push(C.modeBadge(m)));
    if (listing.status !== "available") badges.push(C.statusBadge(listing.status));
    if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));

    const money = C.el("div", { className: "stack--tight" });
    if ((listing.allowed_modes || []).includes("sale")) {
      money.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.sale_price_cents) }), C.el("span", { className: "muted", text: " to buy" })));
    }
    if ((listing.allowed_modes || []).includes("borrow")) {
      const fee = listing.rental_fee_cents === 0 ? "Free loan" : api.formatCents(listing.rental_fee_cents) + " fee";
      money.append(C.el("div", {}, C.el("span", { className: "price", text: fee }),
        C.el("span", { className: "muted", text: " · agreed value " + api.formatCents(listing.proposed_item_value_cents) + " · deposit proposal " + (listing.collateral_percent == null ? "unknown" : listing.collateral_percent + "%") })));
    }

    const specs = Object.entries(listing.specifications || {}).slice(0, 4);
    const specList = specs.length ? C.el("dl", { className: "specs" }, specs.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: String(v) })])) : null;

    const meta = C.el("div", { className: "meta" },
      C.el("span", { text: listing.category || "uncategorized" }),
      listing.condition ? C.el("span", { text: "condition: " + String(listing.condition).replace("_", " ") }) : C.el("span", { text: "condition unknown" }),
      listing.known_defects && listing.known_defects.length ? C.el("span", { text: listing.known_defects.length + " known defect" + (listing.known_defects.length > 1 ? "s" : "") }) : null);

    const title = C.el("a", { className: "card__link", href: "/listings/" + enc(listing.id), text: listing.title });

    return C.card({
      variant: ["compact"], interactive: true,
      media: { src: listing.public_photo_url, alt: listing.public_photo_url ? "Photo of " + listing.title : "" },
      title, badges,
      body: [meta, money, specList],
      footer: [C.el("span", { className: "muted", text: owner.display_name || "Owner" }), C.profileBadge(owner)],
    });
  }
})();
