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

  if (page === "home") initHome();
  if (page === "results") initResults();

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

      if (fixture) {
        matchesBox.append(C.notice("fixture", C.el("span", {},
          C.el("strong", { text: "Matching is a labeled stub. " }),
          "Nothing below has been checked against your requirements yet, so every listing appears under \"needs confirmation\". These are real current listings, not invented results.")));
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

      // Excluded (collapsed)
      if (rejected.length) {
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

  // Key/value editor for specifications. Returns {root, control, value(), setError, clearError}.
  function kvEditor(title, hint, initial) {
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
    const legend = C.el("legend", {}, title + " ", entries.length ? null : C.badge("none known", "neutral"));
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
