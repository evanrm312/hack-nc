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
    ["academic supplies", "Academic supplies"], ["dorm essentials", "Dorm essentials"],
    ["event equipment", "Event equipment"], ["outdoor gear", "Outdoor gear"],
    ["mobility", "Mobility"], ["tools", "Tools"],
  ];
  // Search preference used only when the interpreter gave no mode. It is
  // shown as "needs confirmation" until the user confirms it.
  const DEFAULT_MODES = ["borrow", "sale"];

  // =============================================================== SERVICES
  // Third listing kind, per docs/contracts.md (Person 1, p1-services):
  //   Listing: allowed_modes exactly ["service"], category in
  //     the eight service categories below, description required,
  //     service_price_cents (may be 0), service_duration_minutes (1-1440),
  //     service_available_windows (nonempty, at least one fits the duration).
  //     Item fields (condition, specs, accessories, defects, prices, collateral,
  //     availability, meeting_spot_ids) are rejected for services.
  //   NeedRequest: modes exactly ["service"], normalized.category a service
  //     category; max_deposit_cents, use_start, use_end, pickup_windows must be
  //     absent/null; optional service_duration_minutes and private
  //     service_time_windows. Public view adds service_duration_minutes.
  const SERVICE_CATEGORIES = [
    ["tutoring", "Tutoring"], ["proofreading", "Proofreading"], ["moving help", "Moving help"],
    ["tech help", "Tech help"], ["repair and mending", "Repair and mending"],
    ["bike repair", "Bike repair"], ["photography", "Photography"], ["event help", "Event help"],
  ];
  const serviceCategoryLabel = (c) => (SERVICE_CATEGORIES.find(([v]) => v === c) || [c, c ? String(c) : "Unknown"])[1];
  const categoryLabel = (c) => ([...CATEGORIES, ...SERVICE_CATEGORIES].find(([v]) => v && v === c) || [c, c ? String(c) : "Uncategorized"])[1];
  const modeLabel = (m) => ({ sale: "Buy", borrow: "Borrow", service: "Service" })[m] || String(m);
  const isServiceCategory = (c) => SERVICE_CATEGORIES.some(([v]) => v === c);
  const isService = (listing) => !!listing && (listing.allowed_modes || []).includes("service");
  const isServiceRequest = (r) => !!r && ((r.modes || []).includes("service") || (r.normalized && (r.normalized.modes || []).includes("service")));
  const formatDuration = (min) => (Number.isInteger(min) ? (min >= 60 ? (min / 60).toFixed(min % 60 ? 1 : 0) + " h" : min + " min") : "Unknown");

  const CONDITIONS = [["", "Unknown"], ["new", "New"], ["like_new", "Like new"], ["good", "Good"], ["fair", "Fair"], ["worn", "Worn"]];
  const conditionLabel = C.conditionLabel;
  let listingLoadVersion = 0;

  if (page === "home") initHome();
  if (page === "results") initResults();
  if (page === "listing-form") initListingForm();
  // /listings/mine is served by the detail route until Person 1 registers
  // pages.my_listings; the same controller runs either way.
  if (page === "listing-detail" && $("listing-root") && $("listing-root").dataset.listingId === "mine") initMyListings($("listing-root"));
  else if (page === "listing-detail") initListingDetail();
  if (page === "my-listings") initMyListings($("my-listings-root"));
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
  const cleanModes = (modes) => (Array.isArray(modes) ? modes.filter((m) => m === "sale" || m === "borrow" || m === "service") : []);

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
    try { textarea.value = sessionStorage.getItem("campus_request_draft") || textarea.value; } catch (_) {}
    function saveQuery() { try {sessionStorage.setItem("campus_request_draft",textarea.value);} catch (_) {} }
    textarea.addEventListener("input",saveQuery);
    document.querySelectorAll("[data-example]").forEach(chip=>chip.addEventListener("click",saveQuery));
    textarea.addEventListener("input", () => { textError.textContent = ""; textarea.removeAttribute("aria-invalid"); });

    // ---- optional reference photo (validated here; sent only with the request)
    const photoInput = $("request-photo");
    const photoPreview = $("request-photo-preview");
    const photoError = $("request-photo-error");
    const photoLimit = Math.min(Number((window.CAMPUS_CONFIG || {}).max_upload_bytes) || Infinity, 5 * 1024 * 1024);
    let photoFile = null;
    function setPhotoError(message) {
      photoError.textContent = message || "";
      if (message) photoInput.setAttribute("aria-invalid", "true"); else photoInput.removeAttribute("aria-invalid");
    }
    function clearPhoto(focusInput) {
      photoFile = null;
      photoInput.value = "";
      const img = photoPreview.querySelector("img");
      if (img.src) { URL.revokeObjectURL(img.src); img.removeAttribute("src"); }
      photoPreview.hidden = true;
      setPhotoError("");
      if (focusInput) photoInput.focus();
    }
    photoInput.addEventListener("change", () => {
      const file = photoInput.files[0];
      if (!file) { clearPhoto(false); return; }
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) { clearPhoto(false); setPhotoError("Choose a JPEG, PNG, or WebP image."); return; }
      if (file.size > photoLimit) { clearPhoto(false); setPhotoError("That photo is over " + Math.round(photoLimit / (1024 * 1024)) + " MB."); return; }
      photoFile = file;
      setPhotoError("");
      photoPreview.querySelector("img").src = URL.createObjectURL(file);
      $("request-photo-name").textContent = file.name + " (" + (file.size / 1024).toFixed(0) + " KB)";
      photoPreview.hidden = false;
    });
    $("request-photo-remove").addEventListener("click", () => clearPhoto(true));

    let submitting = false;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (submitting) return;
      showNotice(formError, null);
      const text = textarea.value.trim();
      if (!text && !photoFile) {
        textError.textContent = "Describe what you need, or add a reference photo.";
        textarea.setAttribute("aria-invalid", "true");
        textarea.focus();
        return;
      }
      if (photoError.textContent) { photoInput.focus(); return; }
      submitting = true;
      C.setBusy(submit, true, photoFile ? "Analyzing your photo" : "Interpreting your request");
      status.textContent = photoFile ? "Analyzing photo…" : "Interpreting…";

      // Step 1: interpret. Photo first (if any), then text, then the manual
      // all-unknown form. Nothing is ever guessed on the client.
      let normalized = null;
      let photoNote = null;
      if (photoFile) {
        const fd = new FormData();
        fd.append("photo", photoFile);            // assumed multipart field names: photo, text
        if (text) fd.append("text", text);
        try {
          const result = await api.post("/api/requests/normalize-photo", fd);
          normalized = markPhotoProposals(result.normalized, text);
        } catch (err) {
          if (C.isAuthError(err)) {
            if (err.status === 401) api.setToken(null);
            status.textContent = ""; C.setBusy(submit, false); submitting = false;
            showNotice(formError, authMessage(err));
            return;
          }
          if (err instanceof api.ApiError && (err.code === "unsupported_image" || err.code === "payload_too_large" || err.code === "invalid_image")) {
            status.textContent = ""; C.setBusy(submit, false); submitting = false;
            setPhotoError(err.message || "That photo could not be used.");
            photoInput.focus();
            return;
          }
          const missing = err instanceof api.ApiError && (err.status === 404 || err.status === 405 || err.status === 501);
          photoNote = missing
            ? "Photo analysis is not available on the server yet, so the photo was not used."
            : "The photo could not be analyzed (" + C.errorMessage(err) + "), so it was not used.";
          if (!text) {
            status.textContent = ""; C.setBusy(submit, false); submitting = false;
            showNotice(formError, photoNote + " Add a short description to continue.");
            textarea.focus();
            return;
          }
        }
      }
      if (!normalized) {
        status.textContent = "Interpreting…";
        try {
          const result = await api.post("/api/requests/normalize", { text });
          normalized = result.normalized || manualNormalized(text, "The interpreter returned nothing. Fill in the fields yourself.");
        } catch (err) {
          if (C.isAuthError(err)) {
            if (err.status === 401) api.setToken(null);
            status.textContent = ""; C.setBusy(submit, false); submitting = false;
            showNotice(formError, authMessage(err));
            return;
          }
          normalized = manualNormalized(text, "The interpreter could not be reached (" + C.errorMessage(err) + "). Nothing was guessed; fill in the fields yourself.");
        }
        if (photoNote) normalized.follow_up_questions = [photoNote].concat(normalized.follow_up_questions || []);
      }

      // Step 2: anything that still needs the user's decision stops here, on
      // the page, before a request exists: photo proposals to accept or
      // dismiss, ambiguous dates, a missing description, or no mode choice.
      const pendingProposals = (normalized.photo_proposals || []).length > 0;
      if (pendingProposals || (normalized.ambiguous_dates || []).length || !text || !cleanModes(normalized.modes).length) {
        status.textContent = "";
        C.setBusy(submit, false);
        submitting = false;
        renderConfirmStep(text, normalized);
        return;
      }

      // Step 3: save the request and go to results, where every field is editable.
      status.textContent = "Saving your request…";
      try {
        const request = await createRequestFrom(text, normalized);
        window.location.href = "/results/" + enc(request.id);
      } catch (err) {
        status.textContent = "";
        C.setBusy(submit, false);
        submitting = false;
        if (err instanceof api.ApiError && err.code === "validation_error") {
          renderConfirmStep(text, normalized);
          showNotice($("confirm-error"), C.errorMessage(err));
        } else if (C.isAuthError(err)) {
          if (err.status === 401) api.setToken(null);
          showNotice(formError, authMessage(err));
        } else {
          showNotice(formError, C.errorMessage(err));
        }
      }
    });

    // ---- confirmation step (before any request is created) ---------------
    const confirmSection = $("confirm");
    $("confirm-reset").addEventListener("click", () => {
      confirmSection.hidden = true;
      C.clear($("confirm-fields")); C.clear($("confirm-proposals"));
      textarea.focus();
    });

    function renderConfirmStep(text, normalized) {
      const fieldsBox = C.clear($("confirm-fields"));
      const proposalsBox = C.clear($("confirm-proposals"));
      const noticesBox = C.clear($("confirm-notices"));
      const badges = C.clear($("confirm-badges"));
      const summary = $("confirm-summary");
      const errorBox = $("confirm-error");
      const findBtn = $("confirm-submit");
      const cform = $("confirm-form");
      showNotice(errorBox, null);
      let creating = false;

      const source = normalized.source || "unknown";
      if (normalized.reference_photo) badges.append(C.badge("Reference photo", "info"));
      if (source === "stub") badges.append(C.fixtureBadge("Stub output, not Gemini"));
      else if (source === "manual") badges.append(C.badge("Manual entry", "warn"));
      else badges.append(C.badge("Proposed by Gemini", "info"));
      noticesBox.append(C.notice("info", C.el("span", {},
        C.el("strong", { text: "Nothing is saved yet. " }),
        "Check the fields below. Anything proposed by the interpreter or your photo is a suggestion until you confirm it; blank means unknown.")));
      const questions = (normalized.follow_up_questions || []).filter(Boolean);
      if (questions.length) {
        noticesBox.append(C.el("div", { className: "notice notice--warn", role: "note" }, C.el("div", {},
          C.el("strong", { text: "Please confirm" }),
          C.el("ul", { style: { margin: 0, paddingLeft: "1.2em" } }, questions.map((q) => C.el("li", { text: String(q) }))))));
      }

      // Description is required (image-only normalization returns "").
      const desc = C.field({ id: "c-text", label: "What you need", type: "textarea", rows: 3, value: text, required: true,
        hint: "Required. A few words about what you need; the search is based on this." });
      const descTodo = C.el("p", { className: "field__todo", id: "c-text-todo" });
      desc.root.append(descTodo);
      desc.control.setAttribute("aria-describedby", desc.control.getAttribute("aria-describedby") + " c-text-todo");

      const values = {
        modes: cleanModes(normalized.modes),
        category: normalized.category || "",
        required_specifications: normalized.required_specifications || {},
        preferred_specifications: normalized.preferred_specifications || {},
        budget_cents: normalized.budget_cents, max_deposit_cents: normalized.max_deposit_cents,
        needed_by: normalized.needed_by, use_start: normalized.use_start, use_end: normalized.use_end,
        area: normalized.area,
        service_duration_minutes: normalized.service_duration_minutes, service_time_windows: normalized.service_time_windows || [],
      };
      const editor = buildInterpretationForm(fieldsBox, values, { modesUnknown: false, requireModes: true, ambiguous: normalized.ambiguous_dates || [] });
      fieldsBox.prepend(desc.root);
      const modesTodo = C.el("p", { className: "field__todo", id: "modes-todo" });
      editor.fields.modes.control.append(modesTodo);

      // Photo proposals: nothing is part of the request until accepted.
      const proposals = (normalized.photo_proposals || []).map((p) => Object.assign({ status: null, row: null }, p));
      const proposalsTodo = C.el("p", { className: "field__todo" });
      function applyProposal(p) {
        if (p.name === "category") {
          const sel = editor.fields.category.control;
          if (!Array.from(sel.options).some((o) => o.value === p.value)) sel.append(C.el("option", { value: p.value, text: String(p.value) }));
          sel.value = p.value;
        } else {
          p.row = editor.fields.preferred_specifications.add(p.name, p.value);
        }
      }
      function undoProposal(p) {
        if (p.name === "category") { if (editor.fields.category.control.value === p.value) editor.fields.category.control.value = ""; }
        else if (p.row) { p.row.remove(); p.row = null; if (!editor.fields.preferred_specifications.control.children.length) editor.fields.preferred_specifications.add(); }
      }
      function renderProposals() {
        C.clear(proposalsBox);
        if (!proposals.length) return;
        const list = C.el("ul", { className: "proposals", "aria-label": "Attributes proposed from your photo" });
        proposals.forEach((p, i) => {
          const where = p.name === "category" ? "the category" : "preferred specifications";
          const statusText = p.status === "accepted" ? "Accepted and added to " + where + "." : p.status === "dismissed" ? "Dismissed; not part of your request." : "Not part of your request until you accept it.";
          const actions = C.el("span", { className: "cluster" });
          if (!p.status) {
            actions.append(
              C.button({ label: "Accept", variant: "leaf", size: "sm", attrs: { "aria-label": "Accept " + p.name + " " + p.value }, onClick: () => { p.status = "accepted"; applyProposal(p); renderProposals(); refresh(); focusProposal(i); } }),
              C.button({ label: "Dismiss", size: "sm", attrs: { "aria-label": "Dismiss " + p.name + " " + p.value }, onClick: () => { p.status = "dismissed"; renderProposals(); refresh(); focusProposal(i); } }));
          } else {
            actions.append(C.button({ label: "Change", variant: "ghost", size: "sm", attrs: { "aria-label": "Change decision for " + p.name }, onClick: () => { if (p.status === "accepted") undoProposal(p); p.status = null; renderProposals(); refresh(); focusProposal(i); } }));
          }
          list.append(C.el("li", { className: "proposal" + (p.status ? " proposal--" + p.status : ""), dataset: { index: String(i) } },
            C.el("span", { className: "proposal__attr" }, C.badge("From photo", "warn"), " ", C.el("strong", { text: String(p.name).replace(/_/g, " ") }), " = ", C.el("span", { text: String(p.value) })),
            C.el("span", { className: "proposal__status muted", text: statusText }),
            actions));
        });
        proposalsBox.append(C.el("fieldset", {},
          C.el("legend", { text: "Proposed from your photo" }),
          C.el("p", { className: "field__hint", text: "Visual guesses only (category, type, color, pattern, style). Accept the ones that are right; they become preferences you can still edit below. Size, price, condition, and dates are never read from a photo." }),
          list,
          C.el("div", { className: "cluster" },
            C.button({ label: "Accept all", size: "sm", onClick: () => { proposals.forEach((p) => { if (!p.status) { p.status = "accepted"; applyProposal(p); } }); renderProposals(); refresh(); } }),
            C.button({ label: "Dismiss all", size: "sm", onClick: () => { proposals.forEach((p) => { if (!p.status) p.status = "dismissed"; }); renderProposals(); refresh(); } })),
          proposalsTodo));
      }
      function focusProposal(i) { const li = proposalsBox.querySelector('.proposal[data-index="' + i + '"] button'); if (li) li.focus(); }

      // Live "what's missing": next to each field and in the summary; the
      // button stays disabled until every required decision is made.
      function refresh() {
        const problems = [];
        const hasText = !!desc.value().trim();
        descTodo.textContent = hasText ? "" : "Add a few words about what you need.";
        if (!hasText) problems.push("a short description");
        const modeCount = fieldsBox.querySelectorAll('input[name="modes"]:checked').length;
        modesTodo.textContent = modeCount ? "" : "Choose buy, borrow, or a service.";
        if (!modeCount) problems.push("buy or borrow");
        const pending = proposals.filter((p) => !p.status).length;
        proposalsTodo.textContent = pending ? pending + " photo proposal" + (pending === 1 ? "" : "s") + " still need" + (pending === 1 ? "s" : "") + " Accept or Dismiss." : "";
        if (pending) problems.push("a decision on " + pending + " photo proposal" + (pending === 1 ? "" : "s"));
        findBtn.disabled = problems.length > 0 || creating;
        summary.textContent = problems.length ? "To find matches, still needed: " + problems.join("; ") + "." : "Ready. Click Find matches when you are done editing.";
        summary.classList.toggle("confirm-summary--ready", !problems.length);
      }
      fieldsBox.addEventListener("input", refresh);
      fieldsBox.addEventListener("change", refresh);
      renderProposals();
      refresh();

      cform.onsubmit = async (event) => {
        event.preventDefault();
        if (creating || findBtn.disabled) return;
        showNotice(errorBox, null);
        const read = editor.read();                 // same validation as text requests
        if (!read.ok) return;
        const v = read.values;
        const descText = desc.value().trim();
        const merged = mergeNormalized(normalized, v, {
          source: source === "stub" ? "manual" : source,
          photo_proposals: proposals.map((p) => ({ name: p.name, value: p.value, status: p.status })),
          original_text: descText,
        });
        creating = true;
        C.setBusy(findBtn, true, "Saving your request");
        try {
          const request = (await postRequest(requestBodyFrom(v, merged, descText))).request;
          window.location.href = "/results/" + enc(request.id);
        } catch (err) {
          creating = false;
          C.setBusy(findBtn, false);
          refresh();
          if (err instanceof api.ApiError && err.code === "validation_error") {
            const leftovers = C.applyFieldErrors(Object.assign({ original_text: desc }, editor.fields), err.fields);
            showNotice(errorBox, leftovers.length ? "Please fix: " + leftovers.join("; ") : "Some fields need attention; see the messages next to them.");
          } else if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); showNotice(errorBox, authMessage(err)); }
          else showNotice(errorBox, C.errorMessage(err));
        }
      };

      confirmSection.hidden = false;
      $("confirm-heading").focus();
      confirmSection.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }

    const kindFilter = C.field({ id: "catalog-kind", label: "Offer type", type: "select",
      options: [{ value: "", label: "All offers" }, { value: "sale", label: "Buy" },
        { value: "borrow", label: "Borrow" }, { value: "service", label: "Services" }] });
    const categoryFilter = C.field({ id: "catalog-category", label: "Category", type: "select",
      options: [{ value: "", label: "All categories" }] });
    $("catalog-filters").append(kindFilter.root, categoryFilter.root);
    function refreshCatalogCategories() {
      const selected = categoryFilter.value();
      const kind = kindFilter.value();
      const options = kind === "service" ? SERVICE_CATEGORIES : kind ? CATEGORIES.slice(1) : CATEGORIES.slice(1).concat(SERVICE_CATEGORIES);
      C.clear(categoryFilter.control);
      categoryFilter.control.append(C.el("option", { value: "", text: "All categories" }));
      options.forEach(([value, label]) => categoryFilter.control.append(C.el("option", { value, text: label })));
      if (options.some(([value]) => value === selected)) categoryFilter.control.value = selected;
    }
    kindFilter.control.addEventListener("change", () => { refreshCatalogCategories(); loadListings(); });
    categoryFilter.control.addEventListener("change", loadListings);
    refreshCatalogCategories();
    loadListings();
  }

  // Turn photo-derived attributes into PENDING proposals. They are removed
  // from the normalized specs/category so nothing from the photo is part of
  // the request until the user accepts it on the confirmation step. Prefers
  // the server's photo_attributes when present (assumed optional response
  // field); otherwise derives from the vision whitelist (category, type,
  // color, pattern, style). A text-derived color would also become a
  // proposal; accepting it is one click, and nothing is lost silently.
  function markPhotoProposals(normalized, text) {
    const n = Object.assign({}, normalized || manualNormalized(text, "The photo analyzer returned nothing. Fill in the fields yourself."));
    const VISUAL = ["type", "color", "pattern", "style"];
    let attrs = n.photo_attributes && typeof n.photo_attributes === "object" ? n.photo_attributes : null;
    if (!attrs) {
      attrs = {};
      if (n.category) attrs.category = n.category;
      VISUAL.forEach((k) => {
        if ((n.required_specifications || {})[k] != null) attrs[k] = n.required_specifications[k];
        else if ((n.preferred_specifications || {})[k] != null) attrs[k] = n.preferred_specifications[k];
      });
    }
    const required = Object.assign({}, n.required_specifications || {});
    const preferred = Object.assign({}, n.preferred_specifications || {});
    const proposals = [];
    Object.entries(attrs).forEach(([name, value]) => {
      if (value == null || value === "") return;
      proposals.push({ name, value, status: null });
      if (name === "category") { if (n.category === value) n.category = null; }
      else { delete required[name]; delete preferred[name]; }
    });
    const followUps = (n.follow_up_questions || []).filter((q) => !/confirm or edit all proposed visual attributes/i.test(String(q)));
    if (!proposals.length) {
      followUps.unshift("The photo was received, but nothing could be proposed from it (analysis unavailable or the item was unclear). Fill in the fields yourself.");
    }
    delete n.photo_attributes;
    return Object.assign(n, {
      reference_photo: true, photo_proposals: proposals,
      required_specifications: required, preferred_specifications: preferred,
      follow_up_questions: followUps, original_text: n.original_text || text || "",
    });
  }

  // Direct creation from an interpretation that already has a mode (text
  // requests that skip the confirmation step).
  const requestRetryKeys = new Map();
  async function postRequest(body) {
    const fingerprint = JSON.stringify(body);
    if (!requestRetryKeys.has(fingerprint)) requestRetryKeys.set(fingerprint, crypto.randomUUID());
    return api.post("/api/requests", body, { headers: { "Idempotency-Key": requestRetryKeys.get(fingerprint) } });
  }

  async function createRequestFrom(text, normalized) {
    const modes = cleanModes(normalized.modes);
    const service = modes.length === 1 && modes[0] === "service";
    const body = {
      original_text: text,
      normalized,
      modes: modes.length ? modes : DEFAULT_MODES.slice(),
      budget_cents: nonNegInt(normalized.budget_cents),
      needed_by: normalized.needed_by || null,
      area: typeof normalized.area === "string" ? normalized.area.slice(0, 80) : null,
    };
    if (service) {
      body.service_duration_minutes = Number.isInteger(normalized.service_duration_minutes) ? normalized.service_duration_minutes : null;
      body.service_time_windows = Array.isArray(normalized.service_time_windows) ? normalized.service_time_windows : [];
      normalized.max_deposit_cents = null;
    } else {
      body.max_deposit_cents = nonNegInt(normalized.max_deposit_cents);
      body.use_start = normalized.use_start || null;
      body.use_end = normalized.use_end || null;
      body.pickup_windows = [];
    }
    return (await postRequest(body)).request;
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
        interpBadges.append(C.badge(source === "gemini" ? "Proposed by Gemini" : "Review details", "info"));
        interpBody.append(C.notice("info", source === "gemini" ? "These are proposals from the interpreter, not facts. Edit anything that is wrong; blank means unknown." : "Review and correct these details. Blank means unknown; no interpreter source was recorded."));
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
        service_duration_minutes: request.service_duration_minutes,
        service_time_windows: request.service_time_windows || [],
      };
      // Only proposals the user ACCEPTED on the confirmation step are marked here.
      const accepted = (n.photo_proposals || []).filter((p) => p && p.status === "accepted");
      const photoAttrs = accepted.length ? Object.fromEntries(accepted.map((p) => [p.name, p.value])) : null;
      if (photoAttrs) {
        interpBody.append(C.notice("info", C.el("span", {},
          C.el("strong", { text: "Reference photo. " }),
          "Fields marked \"From photo (accepted)\" were proposed from your photo and confirmed by you. They are preferences you can still edit. The photo itself is private and was not stored.")));
      }
      const meta = { modesUnknown: !modesKnown, ambiguous, photoAttributes: photoAttrs, photoLabel: "From photo (accepted)", photoVariant: "neutral" };

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
        // The user has reviewed every field, so pending questions are resolved.
        const body = requestBodyFrom(v, mergeNormalized(n, v, { source: source === "stub" ? "manual" : source }));
        if (v.modes.includes("service")) { body.max_deposit_cents = null; body.use_start = null; body.use_end = null; }
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
        confirmedSection.append(C.el("div", { className: "grid catalog-list" }, confirmed.map((e) => matchCard(e, "confirmed"))));
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
          C.el("div", { className: "grid catalog-list" }, needs.map((e) => matchCard(e, "needs"))));
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
      const confirmed = cleanModes(n.modes);
      const modes = confirmed.includes("service") ? confirmed : (request.modes || []);
      const labels = modes.map(modeLabel);
      if (labels.length) chips.push(labels.join(" or "));
      if (n.category) chips.push("Category: " + categoryLabel(n.category));
      Object.entries(n.required_specifications || {}).forEach(([k, v]) => chips.push(k.replace(/_/g, " ") + " = " + String(v) + " (required)"));
      if (request.budget_cents != null) chips.push("Budget up to " + api.formatCents(request.budget_cents));
      if (request.max_deposit_cents != null) chips.push("Deposit up to " + api.formatCents(request.max_deposit_cents));
      if (request.needed_by) chips.push("Needed by " + api.formatTime(request.needed_by));
      if (request.use_start && request.use_end) chips.push("Borrow " + api.formatTime(request.use_start) + " to " + api.formatTime(request.use_end));
      if (Number.isInteger(request.service_duration_minutes)) chips.push("Session " + formatDuration(request.service_duration_minutes));
      if (request.area) chips.push((isServiceRequest(request) ? "Around " : "Pickup around ") + request.area);
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
      const btn = C.button({ label: "Publish request", variant: "leaf", attrs: { id: "publish-btn" } });
      box.append(
        C.el("h3", { text: "Let other members know" }),
        C.el("p", { className: "muted", text: "Publishing shares a sanitized version of this request in the public feed: the item, buy or borrow, the day you need it by, and your campus area. Your exact times, borrowing dates, deposit limit, and contact details stay private. Nothing is published until you confirm." }),
        C.el("div", { className: "cluster" }, btn));
      btn.addEventListener("click", () => openPublishPreview(btn, box));
    }

    // Mirrors the server's public view (docs/contracts.md -> NeedRequest public view).
    function buildPublicPreview(profile) {
      const n = request.normalized || {};
      const fmtSpecs = (obj) => Object.entries(obj || {}).map(([k, v]) => k.replace(/_/g, " ") + " = " + String(v)).join(", ") || "None";
      const modes = request.modes || [];
      const neededDate = request.needed_by ? request.needed_by.slice(0, 10) : null;
      const publicRows = [
        ["Who", profile ? profile.display_name + " (" + profile.badge + ")" : "Your display name and verification badge"],
        ["Item category", n.category ? categoryLabel(n.category) : "Unknown"],
        ["Required details", fmtSpecs(n.required_specifications)],
        ["Preferred details", fmtSpecs(n.preferred_specifications)],
        ["Buy or borrow", modes.length ? modes.map(modeLabel).join(" or ") : "Unknown"],
        ["Budget", request.budget_cents != null ? api.formatCents(request.budget_cents) : "Unknown"],
        ["Needed by", neededDate ? neededDate + " (date only)" : "Unknown"],
        ["Campus area", request.area || "Unknown"],
      ];
      const privateRows = [
        ["Your original wording", request.original_text ? "“" + request.original_text.slice(0, 80) + (request.original_text.length > 80 ? "…" : "") + "”" : "—"],
        ["Exact needed-by time", request.needed_by ? api.formatTime(request.needed_by) : "Unknown"],
        ["Borrowing dates", request.use_start || request.use_end ? api.formatTime(request.use_start) + " to " + api.formatTime(request.use_end) : "Unknown"],
        ["Pickup windows", (request.pickup_windows || []).length ? (request.pickup_windows.length + " window(s)") : "None set"],
        ["Deposit you can afford", request.max_deposit_cents != null ? api.formatCents(request.max_deposit_cents) : "Unknown"],
        ["Email and contact details", "Never shown"],
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
        const specs = (o) => Object.entries(o || {}).map(([k, v]) => k.replace(/_/g, " ") + " = " + String(v)).join(", ") || "None";
        box.append(C.el("p", { className: "muted", style: { margin: "var(--space-3) 0 var(--space-1)" }, text: "Exactly what was published:" }),
          C.el("dl", { className: "privacy-list" }, [
            ["Who", pub.requester ? pub.requester.display_name + " (" + pub.requester.badge + ")" : "Unknown"],
            ["Item category", pub.category ? categoryLabel(pub.category) : "Unknown"],
            ["Required details", specs(pub.required_specifications)],
            ["Preferred details", specs(pub.preferred_specifications)],
            ["Buy or borrow", (pub.modes || []).length ? pub.modes.map(modeLabel).join(" or ") : "Unknown"],
            ["Budget", pub.budget_cents != null ? api.formatCents(pub.budget_cents) : "Unknown"],
            ["Needed by", pub.needed_by_date || "Unknown"],
            ["Campus area", pub.area || "Unknown"],
          ].flatMap(([k, v]) => [C.el("dt", {}, C.el("span", { className: "privacy-list__lock privacy-list__lock--open", "aria-hidden": "true" }), k), C.el("dd", { text: v })])));
      }
    }

    function matchCard(entry, kind) {
      const listing = entry.listing || {};
      const owner = listing.owner || {};
      const allowed = listing.allowed_modes || [];
      const service = isService(listing);
      const mode = service ? "service" : (entry.mode || (allowed.length === 1 ? allowed[0] : null));

      const badges = [];
      if (mode) badges.push(C.modeBadge(mode));
      else allowed.forEach((m) => badges.push(C.modeBadge(m)));
      if (kind === "needs") badges.push(C.badge("Needs confirmation", "warn"));
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));

      // Money: show only what the listing actually offers for the relevant mode(s).
      const money = C.el("div", { className: "stack--tight match-money" });
      const showSale = !service && allowed.includes("sale") && (mode === "sale" || !mode);
      const showBorrow = !service && allowed.includes("borrow") && (mode === "borrow" || !mode);
      if (service) {
        money.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.service_price_cents) }), C.el("span", { className: "muted", text: " per " + formatDuration(listing.service_duration_minutes) + " session" })));
        money.append(C.el("div", { className: "muted", text: "No deposit or collateral for services." }));
      }
      if (showSale) {
        money.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.sale_price_cents) }), C.el("span", { className: "muted", text: " to buy" })));
      }
      if (showBorrow) {
        const fee = listing.rental_fee_cents === 0 ? "Free loan" : api.formatCents(listing.rental_fee_cents) + " rental fee";
        money.append(C.el("div", {}, C.el("span", { className: "price", text: fee })));
        money.append(C.el("div", { className: "muted" }, depositProposalText(listing)));
      }
      if (!service && !showSale && !showBorrow) money.append(C.el("div", { className: "muted", text: "Terms unknown" }));

      const reasons = C.el("ul", { className: "reasons" });
      (entry.reasons || []).forEach((r) => reasons.append(C.el("li", { className: "reason reason--ok", text: String(r) })));
      (entry.unknown_required || []).forEach((u) => reasons.append(C.el("li", { className: "reason reason--unknown", text: "Needs confirmation: " + String(u).replace(/_/g, " ") })));
      (entry.shortcomings || []).forEach((s) => reasons.append(C.el("li", { className: "reason reason--warn", text: String(s) })));
      if (!reasons.children.length) reasons.append(C.el("li", { className: "reason reason--unknown", text: "No explanation was provided." }));

      const specs = service ? [] : Object.entries(listing.specifications || {}).slice(0, 4);
      const specList = specs.length ? C.el("dl", { className: "specs" }, specs.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: String(v) })])) : null;
      const windows = service ? serviceWindowsNode(listing, 2) : null;

      const footer = [
        C.el("span", { className: "cluster" }, C.el("span", { className: "muted", text: owner.display_name || "Owner" }), C.profileBadge(owner)),
        C.el("span", { className: "cluster" },
          typeof entry.score === "number" ? C.badge("Fit " + entry.score.toFixed(2), "neutral") : null,
          // Carry the request along so the detail page can link the exchange
          // to it (source_request_id) and preselect the matched mode.
          C.button({ label: service ? "View service" : "View listing", size: "sm", variant: kind === "confirmed" ? "primary" : "default",
            href: "/listings/" + enc(listing.id || "") + "?from_request=" + enc(requestId) + (mode ? "&mode=" + enc(mode) : "") })),
      ];

      return C.card({
        variant: ["compact"].concat(kind === "needs" ? ["needs"] : []),
        media: cardMedia(listing),
        title: listing.title || "Untitled listing",
        subtitle: service
          ? serviceCategoryLabel(listing.category) + " · " + formatDuration(listing.service_duration_minutes)
          : [categoryLabel(listing.category), "Condition: " + conditionLabel(listing.condition)].filter(Boolean).join(" · "),
        badges,
        body: [money, specList, windows, C.el("h4", { className: "reasons__title", text: kind === "confirmed" ? "Why it matches" : "What still needs checking" }), reasons],
        footer,
      });
    }
  }

  // Available time windows of a service listing (Eastern), optionally capped.
  function serviceWindowsNode(listing, limit) {
    const windows = Array.isArray(listing.service_available_windows) ? listing.service_available_windows : [];
    if (!windows.length) return C.el("p", { className: "muted", text: "No time windows given." });
    const shown = limit ? windows.slice(0, limit) : windows;
    const list = C.el("ul", { className: "spot-list" }, shown.map((w) => C.el("li", { text: api.formatTime(w.start) + " to " + api.formatTime(w.end) })));
    if (limit && windows.length > limit) list.append(C.el("li", { className: "muted", text: "+ " + (windows.length - limit) + " more" }));
    return C.el("div", {}, C.el("div", { className: "muted", style: { fontSize: ".85rem", marginTop: "6px" }, text: "Available windows" }), list);
  }

  // Owner's deposit proposal in dollars and percent. Pure arithmetic on the
  // listing's own fields; "unknown" when either input is missing.
  function depositProposalText(listing) {
    const value = listing.proposed_item_value_cents;
    const pct = listing.collateral_percent;
    if (!Number.isInteger(value) || !Number.isInteger(pct)) return "Deposit proposal unknown (owner has not set value or percent)";
    const deposit = Math.round((value * pct) / 100);
    return "Proposed deposit " + api.formatCents(deposit) + " (" + pct + "% of " + api.formatCents(value) + " agreed value). ";
  }

  // ------------------------------------------------ interpretation form (shared)
  // buildInterpretationForm(container, values, meta) -> {fields, read()}
  // Unknown values show an "unknown" badge; ambiguous dates and an unconfirmed
  // mode show "needs confirmation". read() validates and returns {ok, values}.
  function buildInterpretationForm(container, values, meta) {
    meta = meta || {};
    const F = {};
    const unknownBadge = () => C.badge("Unknown", "neutral");
    const confirmBadge = () => C.badge("Needs confirmation", "warn");
    const markLabel = (fieldApi, badge) => { fieldApi.root.querySelector(".field__label").append(badge); };

    const modesErr = C.el("p", { className: "field__error", id: "modes-error", role: "alert" });
    const modesGroup = C.el("fieldset", {},
      C.el("legend", {}, "What are you looking for? ", meta.modesUnknown ? confirmBadge() : meta.requireModes ? C.badge("Required", "info") : null),
      C.el("p", { className: "field__hint", id: "modes-hint", text: meta.modesUnknown
        ? "The interpreter did not say. Buy and borrow are selected as a search preference; confirm or narrow it."
        : (meta.requireModes ? "Required. " : "") + "Pick at least one. Buy and borrow together is fine as a search preference. Service means help from a person, such as tutoring, repair, or photography." }),
      C.el("div", { className: "choices" },
        choice("modes", "borrow", "Borrow an item", (values.modes || []).includes("borrow")),
        choice("modes", "sale", "Buy an item", (values.modes || []).includes("sale")),
        choice("modes", "service", "A service", (values.modes || []).includes("service"))),
      modesErr);
    F.modes = { control: modesGroup, setError(m) { modesErr.textContent = m || ""; }, clearError() { modesErr.textContent = ""; } };

    F.category = C.field({ id: "f-category", label: "Category", type: "select", value: values.category || "",
      options: CATEGORIES.map(([value, label]) => ({ value, label })) });
    if (values.category && !CATEGORIES.some(([v]) => v === values.category)) {
      F.category.control.append(C.el("option", { value: values.category, text: values.category }));
      F.category.control.value = values.category;
    }
    const photoAttrs = meta.photoAttributes || {};
    const photoLabel = meta.photoLabel || "From photo (accepted)";
    const photoBadge = () => C.badge(photoLabel, meta.photoVariant || "neutral");
    if (!values.category) markLabel(F.category, unknownBadge());
    else if (photoAttrs.category && photoAttrs.category === values.category) markLabel(F.category, photoBadge());

    const flagged = new Set(Object.keys(photoAttrs).filter((k) => k !== "category"));
    const requiredSpecs = kvEditor("Required specifications", "Must match exactly, e.g. jacket_size = 40R. Unknown required details become “needs confirmation”, never a confirmed match.", values.required_specifications || {}, { flagged, flagLabel: photoLabel, flagVariant: meta.photoVariant || "neutral" });
    const preferredSpecs = kvEditor("Preferred specifications", "Nice to have, e.g. color = navy. Used for ranking only.", values.preferred_specifications || {}, { flagged, flagLabel: photoLabel, flagVariant: meta.photoVariant || "neutral" });
    F.required_specifications = requiredSpecs;
    F.preferred_specifications = preferredSpecs;

    F.budget_cents = C.field({ id: "f-budget", label: "Purchase or rental budget", type: "text", prefix: "$", optional: true,
      attrs: { inputmode: "decimal" }, placeholder: "Unknown", value: C.centsToDollars(values.budget_cents),
      hint: "The most you would pay to buy, or as a rental fee." });
    F.max_deposit_cents = C.field({ id: "f-deposit", label: "Deposit you can afford", type: "text", prefix: "$", optional: true,
      attrs: { inputmode: "decimal" }, placeholder: "Unknown", value: C.centsToDollars(values.max_deposit_cents),
      hint: "Separate from your budget. A free loan can still be unaffordable if the deposit is too high." });
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

    const dateReview = (meta.ambiguous || []).length ? C.el("input", { type: "checkbox", id: "f-date-review" }) : null;
    const dateReviewError = C.el("p", { className: "field__error", role: "alert" });
    const dateReviewPanel = dateReview ? C.el("fieldset", {},
      C.el("legend", { text: "Confirm the dates" }),
      C.el("ul", {}, (meta.ambiguous || []).map((a) => C.el("li", { text: String(a.text || "Ambiguous date") + (a.proposed ? " → " + api.formatTime(a.proposed) : " — choose a date or leave it unknown") }))),
      C.el("label", { className: "choice" }, dateReview, C.el("span", { text: "I reviewed and corrected these dates, or left them unknown." })), dateReviewError) : null;
    if (dateReview) {
      [F.needed_by, F.use_start, F.use_end].forEach((f) => f.control.addEventListener("input", () => { dateReview.checked = false; }));
    }

    F.area = C.field({ id: "f-area", label: "Campus area for pickup", type: "text", optional: true, placeholder: "Unknown", value: values.area || "", attrs: { maxlength: 80 } });
    if (!values.area) markLabel(F.area, unknownBadge());

    // Service-only fields (docs/contracts.md -> Service NeedRequest): optional
    // session length and private time windows. Deposit and loan dates do not
    // apply to services and are hidden (and sent as null) in service mode.
    F.service_duration_minutes = C.field({ id: "f-service-duration", label: "Session length (minutes)", type: "number", optional: true,
      value: Number.isInteger(values.service_duration_minutes) ? String(values.service_duration_minutes) : "",
      attrs: { min: 1, max: 1440, step: 5, inputmode: "numeric" }, hint: "How long you need, 1 to 1440 minutes. Blank means unknown." });
    const serviceWindows = timeWindowsEditor({
      title: "Times that work for you", initial: values.service_time_windows || [],
      hint: "Private; never shown publicly. Times are read in your browser's zone and shown in America/New_York. Leave empty if any time works.",
    });
    F.service_time_windows = serviceWindows;
    const serviceOnly = C.el("div", {}, C.el("div", { className: "field-row" }, F.service_duration_minutes.root), serviceWindows.root);

    container.append(
      modesGroup,
      C.el("div", { className: "field-row" }, F.category.root, F.area.root),
      requiredSpecs.root,
      preferredSpecs.root,
      C.el("div", { className: "field-row" }, F.budget_cents.root, F.max_deposit_cents.root),
      C.el("div", { className: "field-row" }, F.needed_by.root, F.use_start.root, F.use_end.root),
      dateReviewPanel,
      serviceOnly,
    );

    // Service is exclusive with buy/borrow; the category list follows the kind.
    const modeInputs = Array.from(modesGroup.querySelectorAll('input[name="modes"]'));
    const isServiceMode = () => modeInputs.some((i) => i.value === "service" && i.checked);
    function setCategoryOptions(list, placeholderLabel) {
      const sel = F.category.control;
      const current = sel.value;
      C.clear(sel);
      sel.append(C.el("option", { value: "", text: placeholderLabel }));
      list.forEach(([value, label]) => { if (value) sel.append(C.el("option", { value, text: label })); });
      if (current && list.some(([v]) => v === current)) sel.value = current;
      else if (current && !isServiceMode()) { sel.append(C.el("option", { value: current, text: current })); sel.value = current; }
    }
    function syncKind(event) {
      if (event && event.target.value === "service" && event.target.checked) modeInputs.forEach((i) => { if (i.value !== "service") i.checked = false; });
      if (event && event.target.value !== "service" && event.target.checked) modeInputs.forEach((i) => { if (i.value === "service") i.checked = false; });
      const service = isServiceMode();
      F.max_deposit_cents.root.hidden = service;
      F.use_start.root.hidden = service;
      F.use_end.root.hidden = service;
      serviceOnly.hidden = !service;
      F.budget_cents.root.querySelector(".field__label span").textContent = service ? "Budget for the service" : "Purchase or rental budget";
      F.area.root.querySelector(".field__label span").textContent = service ? "Campus area" : "Campus area for pickup";
      setCategoryOptions(service ? SERVICE_CATEGORIES : CATEGORIES, service ? "Choose a service category" : "Unknown / not sure");
    }
    modeInputs.forEach((i) => i.addEventListener("change", syncKind));
    syncKind();

    function read() {
      Object.values(F).forEach((f) => f.clearError && f.clearError());
      const modes = Array.from(container.querySelectorAll('input[name="modes"]:checked')).map((i) => i.value);
      const service = modes.includes("service");
      let bad = false;
      dateReviewError.textContent = "";
      if (dateReview && !dateReview.checked) {
        dateReviewError.textContent = "Review the dates, then confirm them.";
        dateReview.setAttribute("aria-invalid", "true");
        bad = true;
      } else if (dateReview) dateReview.removeAttribute("aria-invalid");
      if (!modes.length) { F.modes.setError("Choose buy, borrow, or a service."); bad = true; }
      if (service && modes.length > 1) { F.modes.setError("A service cannot be combined with buy or borrow."); bad = true; }
      if (service && !isServiceCategory(F.category.value())) { F.category.setError("Choose a supported service category."); bad = true; }
      const budget = C.dollarsToCents(F.budget_cents.value());
      if (budget.error) { F.budget_cents.setError(budget.error); bad = true; }
      const deposit = service ? { cents: null } : C.dollarsToCents(F.max_deposit_cents.value());
      if (deposit.error) { F.max_deposit_cents.setError(deposit.error); bad = true; }
      const dates = {};
      for (const key of ["needed_by", "use_start", "use_end"]) {
        if (service && key !== "needed_by") { dates[key] = null; continue; }
        const iso = C.localToIso(F[key].value());
        if (iso === undefined) { F[key].setError("Enter a valid date and time."); bad = true; }
        dates[key] = iso || null;
      }
      if (dates.use_start && dates.use_end && dates.use_end <= dates.use_start) { F.use_end.setError("Must be after the start."); bad = true; }
      if (modes.length && !modes.includes("borrow") && (dates.use_start || dates.use_end)) {
        F.use_start.setError("Borrowing dates only apply when borrowing is selected."); bad = true;
      }
      let duration = null;
      let windows = { ok: true, values: [] };
      if (service) {
        const raw = F.service_duration_minutes.value().trim();
        if (raw) {
          duration = parseInt(raw, 10);
          if (Number.isNaN(duration) || duration < 1 || duration > 1440) { F.service_duration_minutes.setError("Enter a length from 1 to 1440 minutes."); bad = true; duration = null; }
        }
        windows = serviceWindows.read();
        if (!windows.ok) bad = true;
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
          service_duration_minutes: service ? duration : null,
          service_time_windows: service ? windows.values : [],
        },
      };
    }

    return { fields: F, read };
  }

  // Merge confirmed form values into a normalized object and build the
  // POST/PATCH body for /api/requests. Services omit deposit, loan dates, and
  // pickup windows (the server rejects them) and add duration/time windows.
  function mergeNormalized(base, v, extra) {
    const service = v.modes.includes("service");
    return Object.assign({}, base, {
      modes: v.modes,
      category: v.category || null,
      required_specifications: v.required_specifications,
      preferred_specifications: v.preferred_specifications,
      budget_cents: v.budget_cents,
      max_deposit_cents: service ? null : v.max_deposit_cents,
      needed_by: v.needed_by,
      use_start: service ? null : v.use_start,
      use_end: service ? null : v.use_end,
      area: v.area,
      service_duration_minutes: service ? v.service_duration_minutes : null,
      service_time_windows: service ? (v.service_time_windows || []) : [],
      ambiguous_dates: [], follow_up_questions: [],
    }, extra || {});
  }
  function requestBodyFrom(v, normalized, originalText) {
    const service = v.modes.includes("service");
    const body = { modes: v.modes, normalized, budget_cents: v.budget_cents, needed_by: v.needed_by, area: v.area };
    if (originalText !== undefined) body.original_text = originalText;
    if (service) {
      body.service_duration_minutes = v.service_duration_minutes;
      body.service_time_windows = v.service_time_windows || [];
    } else {
      body.max_deposit_cents = v.max_deposit_cents;
      body.use_start = v.use_start;
      body.use_end = v.use_end;
      if (originalText !== undefined) body.pickup_windows = [];
    }
    return body;
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
    let unsaved = false;
    let draftId = null;
    let resumeSpots = [];
    const listingCreationKey = crypto.randomUUID();
    async function publishDraft(body) {
      const draft = draftId ? (await api.patch("/api/listings/" + enc(draftId), body)).listing : (await api.post("/api/listings", body,{headers:{"Idempotency-Key":listingCreationKey}})).listing;
      draftId = draft.id;
      status.textContent = "Uploading and publishing…";
      const result = await api.upload("/api/listings/" + enc(draftId) + "/publish", "photo", F.photo.control.files[0]);
      unsaved = false;
      window.location.href = "/listings/" + enc(result.listing.id) + "?created=1";
    }
    form.addEventListener("input", () => { unsaved = true; });
    form.addEventListener("change", () => { unsaved = true; });
    window.addEventListener("beforeunload", (event) => {
      if (unsaved && !submitting) { event.preventDefault(); event.returnValue = ""; }
    });

    function refreshGate() {
      const signedIn = !!api.getToken();
      authGate.hidden = signedIn;
      submit.disabled = !signedIn;
    }
    document.addEventListener("campus:auth-changed", refreshGate);
    refreshGate();

    // ---- basics
    const F = {};
    F.title = C.field({ id: "l-title", label: "Title (required)", required: true, placeholder: "e.g. Navy suit, 40R", attrs: { maxlength: 120 } });
    F.category = C.field({ id: "l-category", label: "Category (required)", type: "select", required: true,
      options: CATEGORIES.map(([value, label]) => ({ value, label: value ? label : "Choose a category" })) });
    F.description = C.field({ id: "l-description", label: "Description (required)", type: "textarea", required: true, rows: 3, attrs: { maxlength: 4000 },
      placeholder: "What it is, how it has been used, anything a borrower or buyer should know." });
    F.condition = C.field({ id: "l-condition", label: "Condition", type: "select", options: CONDITIONS.map(([value, label]) => ({ value, label })), hint: "Leave as unknown if you are not sure." });
    const specs = kvEditor("Specifications", "Size, model, dimensions, color: anything a matcher should check exactly (e.g. jacket_size = 40R).", {}, { badge: false });
    F.specifications = specs;
    F.accessories = C.field({ id: "l-accessories", label: "Included accessories", type: "textarea", optional: true, rows: 2, placeholder: "One per line, e.g. garment bag", hint: "One per line." });
    F.known_defects = C.field({ id: "l-defects", label: "Known defects", type: "textarea", optional: true, rows: 2, placeholder: "One per line, e.g. missing one cuff button", hint: "One per line. Be honest; condition is confirmed at handoff." });

    // ---- photo
    F.photo = C.field({ id: "l-photo", label: "Photo (required)", type: "file", required: true, attrs: { accept: "image/jpeg,image/png,image/webp" },
      hint: "JPEG, PNG, or WebP up to 5 MB. Your listing stays private until this succeeds." });
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

    // ---- modes (sale / borrow for items; service is exclusive)
    const modesErr = C.el("p", { className: "field__error", id: "l-modes-error", role: "alert" });
    const modeSale = choiceInput("allowed_modes", "sale", "For sale", false, "l-modes-hint l-modes-error");
    const modeBorrow = choiceInput("allowed_modes", "borrow", "To borrow", true, "l-modes-hint l-modes-error");
    const modeService = choiceInput("allowed_modes", "service", "Service", false, "l-modes-hint l-modes-error");
    const modesGroup = C.el("fieldset", {},
      C.el("legend", { text: "What are you offering?" }),
      C.el("p", { className: "field__hint", id: "l-modes-hint", text: "Choose sale, borrowing, or both for an item. Services have separate session terms and no deposit." }),
      C.el("div", { className: "choices" }, modeSale.label, modeBorrow.label, modeService.label),
      modesErr);
    F.allowed_modes = { control: modesGroup, setError(m) { modesErr.textContent = m || ""; }, clearError() { modesErr.textContent = ""; } };

    // ---- service terms (assumed shape; see SERVICES block at the top)
    F.service_category = C.field({ id: "l-service-category", label: "Service category (required)", type: "select", required: true,
      options: [{ value: "", label: "Choose a category" }].concat(SERVICE_CATEGORIES.map(([value, label]) => ({ value, label }))) });
    F.service_price_cents = C.field({ id: "l-service-price", label: "Price per session (required)", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "e.g. 25", hint: "$0 is allowed for a free service." });
    F.service_duration_minutes = C.field({ id: "l-service-duration", label: "Session length (minutes)", type: "number", value: "60", attrs: { min: 1, max: 1440, step: 1, inputmode: "numeric" }, hint: "Required. 1 to 1440 minutes." });
    const windowsEditor = timeWindowsEditor();
    F.service_available_windows = windowsEditor;
    const serviceGroup = C.el("fieldset", { id: "l-service-group" },
      C.el("legend", { text: "Service terms" }),
      F.service_category.root,
      C.el("div", { className: "field-row" }, F.service_price_cents.root, F.service_duration_minutes.root),
      windowsEditor.root);

    // ---- sale terms
    F.sale_price_cents = C.field({ id: "l-sale-price", label: "Asking sale price", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "e.g. 90", hint: "Required for sale." });
    const saleGroup = C.el("fieldset", { id: "l-sale-group" }, C.el("legend", { text: "Sale terms" }), F.sale_price_cents.root);

    // ---- borrow terms
    F.rental_fee_cents = C.field({ id: "l-rental-fee", label: "Rental fee", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "0", value: "0",
      hint: "Payment for use; $0 is a free loan." });
    F.proposed_item_value_cents = C.field({ id: "l-item-value", label: "Proposed item value (required)", prefix: "$", attrs: { inputmode: "decimal" }, placeholder: "e.g. 200",
      hint: "The value you propose for borrowing; agreed terms are set in the offer." });
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
      C.el("details", { className: "listing-disclosure" },
        C.el("summary", { text: "Availability (optional)" }),
        C.el("div", { className: "field-row" }, F.available_from.root, F.available_until.root),
        F.availability_notes.root));

    // ---- meeting spots
    const spotsBox = C.el("div", { id: "l-spots" });
    const spotsErr = C.el("p", { className: "field__error", role: "alert" });
    const spotsGroup = C.el("fieldset", {},
      C.el("legend", { text: "Preferred public meeting spots" }),
      C.el("p", { className: "field__hint", text: "Optional. Choose from the campus catalog. Access notes are recorded information; no location is guaranteed safe." }),
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
          choiceInput("meeting_spot_ids", s.id, s.label + " (" + s.public_area + ")", resumeSpots.includes(s.id)).label)));
      } catch (err) {
        C.state.error(spotsBox, err, { title: "Could not load meeting spots", retry: loadSpots });
      }
    }

    const itemOnly = C.el("div", { className: "listing-item-fields" },
      F.condition.root, specs.root,
      C.el("details", { className: "listing-disclosure", id: "listing-optional-details" },
        C.el("summary", { text: "Accessories and defects (optional)" }),
        F.accessories.root, F.known_defects.root));
    const photosSection = C.el("details", { className: "listing-disclosure listing-photo-section" },
      C.el("summary", { text: "Photo (required)" }), F.photo.root);
    const previewBox = C.el("div", { id: "l-service-preview" });
    fieldsBox.append(
      modesGroup,
      C.el("div", { className: "listing-editor-layout" },
        C.el("section", { className: "listing-details-pane", "aria-label": "Listing details" },
          C.el("h2", { text: "Basics" }),
          C.el("div", { className: "field-row" }, F.title.root, F.category.root),
          F.description.root, itemOnly, photosSection),
        C.el("section", { className: "listing-terms-pane", "aria-label": "Terms and availability" },
          C.el("h2", { text: "Terms" }),
          saleGroup, borrowGroup, serviceGroup, spotsGroup, previewBox)));

    // ---- live behavior
    const isServiceMode = () => modeService.input.checked;
    function syncModes(event) {
      // Service is exclusive: picking it clears sale/borrow and vice versa.
      if (event && event.target === modeService.input && modeService.input.checked) { modeSale.input.checked = false; modeBorrow.input.checked = false; }
      if (event && event.target !== modeService.input && event.target.checked) modeService.input.checked = false;
      const service = isServiceMode();
      saleGroup.hidden = service || !modeSale.input.checked;
      borrowGroup.hidden = service || !modeBorrow.input.checked;
      serviceGroup.hidden = !service;
      spotsGroup.hidden = service;        // meeting_spot_ids is rejected for services
      // Description and image are required for every mode.
      F.description.root.querySelector(".field__label span").textContent = "Description (required)";
      itemOnly.hidden = service;          // condition, photo, specs, accessories, defects
      photosSection.hidden = false;
      F.category.root.hidden = service;   // item category is replaced by the service category
      // Hidden fields keep their draft values but are never sent for this kind.
      [itemOnly, photosSection, saleGroup, borrowGroup, serviceGroup, spotsGroup, F.category.root].forEach((group) => {
        group.querySelectorAll("input, textarea, select").forEach((input) => {
          input.disabled = group.hidden;
          if (group.hidden) input.removeAttribute("aria-invalid");
        });
      });
      F.title.control.placeholder = service ? "e.g. STOR 155 tutoring" : "e.g. Navy suit, 40R";
      if (service || modeSale.input.checked || modeBorrow.input.checked) F.allowed_modes.clearError();
      if (!service) C.clear(previewBox);
    }
    modeSale.input.addEventListener("change", syncModes);
    modeBorrow.input.addEventListener("change", syncModes);
    modeService.input.addEventListener("change", syncModes);
    syncModes();

    // ---- prefill from a public request (/listings/new?from_request=<id>),
    // reached from "Post a listing for this" on the feed. Only what the
    // request publicly says about the kind of thing wanted is copied: the
    // modes, the category, and a title seed. Everything that describes the
    // owner's own item (condition, specs, prices, photo) stays blank, so
    // nothing about the listing is invented from the request.
    const fromRequestId = new URLSearchParams(window.location.search).get("from_request");
    if (fromRequestId) prefillFromRequest(fromRequestId);
    async function prefillFromRequest(id) {
      const box = C.el("div", { id: "l-from-request" });
      fieldsBox.prepend(box);
      C.state.loading(box, "Loading the request you are answering…");
      try {
        const request = (await api.get("/api/requests/" + enc(id))).request;
        const service = isServiceRequest(request);
        const modes = cleanModes(request.modes);
        const category = request.category || (request.normalized && request.normalized.category) || null;
        modeService.input.checked = service;
        modeSale.input.checked = !service && modes.includes("sale");
        modeBorrow.input.checked = !service && modes.includes("borrow");
        if (service) {
          if (isServiceCategory(category)) F.service_category.control.value = category;
        } else if (category) {
          const sel = F.category.control;
          if (!Array.from(sel.options).some((o) => o.value === category)) sel.append(C.el("option", { value: category, text: capitalize(category) }));
          sel.value = category;
        }
        if (category && !F.title.value()) F.title.control.value = service ? serviceCategoryLabel(category) : capitalize(category);
        syncModes();
        const specs = Object.entries(request.required_specifications || {});
        const wants = [service ? serviceCategoryLabel(category) : (category ? capitalize(category) : "an item")]
          .concat(specs.map(([k, v]) => k.replace(/_/g, " ") + " " + String(v)))
          .concat(request.needed_by_date ? ["needed by " + formatDateOnly(request.needed_by_date)] : [])
          .concat(request.area ? ["near " + request.area] : []);
        C.clear(box);
        box.append(C.notice("info", C.el("span", {},
          C.el("strong", { text: "Answering a public request. " }),
          "Someone needs " + wants.join(", ") + (service ? "" : modes.length ? " (" + modes.map((m) => m === "sale" ? "to buy" : "to borrow").join(" or ") + ")" : "") + ". ",
          "We prefilled what you offer and the category; describe your own " + (service ? "service" : "item") + " exactly as it is. ",
          "The requester finds your listing through matching and starts the exchange; nothing is sent to them directly.")));
        F.title.control.focus();
        F.title.control.select();
      } catch (err) {
        C.clear(box);
        box.append(C.notice("warn", C.el("span", {}, C.el("strong", { text: "Could not load that request. " }),
          err instanceof api.ApiError && err.status === 404 ? "It may have been closed or was never public." : C.errorMessage(err),
          " You can still post a listing from scratch; matching will find the requester if it fits.")));
      }
    }

    function updateDeposit() {
      const value = C.dollarsToCents(F.proposed_item_value_cents.value());
      let pct = parseInt(F.collateral_percent.value(), 10);
      if (Number.isNaN(pct)) pct = null;
      C.clear(depositCalc);
      if (value.cents == null || pct == null || pct < 0 || pct > 100) {
        depositCalc.append(C.el("p", { className: "muted", text: "Enter a value and percentage to see the proposed deposit." }));
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

    const resumeId = new URLSearchParams(location.search).get("draft");
    if (resumeId) {
      submitting = true; C.setBusy(submit,true,"Loading draft");
      api.get("/api/listings/"+enc(resumeId)).then(({listing:l})=>{
        if (l.status!=="draft") throw new Error("This listing is no longer a draft.");
        draftId=l.id;resumeSpots=l.meeting_spot_ids||[];
        for (const key of ["title","description","condition","category","service_duration_minutes","collateral_percent"])
          if(F[key])F[key].control.value=l[key]??"";
        for(const key of ["sale_price_cents","rental_fee_cents","proposed_item_value_cents","service_price_cents"])
          F[key].control.value=l[key]==null?"":l[key]/100;
        F.service_category.control.value=l.category;
        modeSale.input.checked=l.allowed_modes.includes("sale");modeBorrow.input.checked=l.allowed_modes.includes("borrow");modeService.input.checked=l.allowed_modes.includes("service");syncModes();
        specs.setValues(l.specifications||{});windowsEditor.setValues(l.service_available_windows||[]);
        F.accessories.control.value=(l.accessories||[]).join("\n");F.known_defects.control.value=(l.known_defects||[]).join("\n");
        F.available_from.control.value=C.isoToLocal((l.availability||{}).available_from)||"";
        F.available_until.control.value=C.isoToLocal((l.availability||{}).available_until)||"";
        F.availability_notes.control.value=(l.availability||{}).notes||"";
        spotsBox.querySelectorAll("input").forEach(i=>{i.checked=resumeSpots.includes(i.value);});
        status.textContent="Private draft restored. Choose an image to publish.";
      }).catch(err=>showNotice(errorBox,C.errorMessage(err))).finally(()=>{submitting=false;C.setBusy(submit,false);refreshGate();});
    }

    // ---- submit
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (submitting) return;
      showNotice(errorBox, null);
      Object.values(F).forEach((f) => f.clearError && f.clearError());

      let bad = false;
      if (!F.description.value().trim()) { F.description.setError("Add a description."); bad = true; }
      if (!F.photo.control.files[0]) { F.photo.setError("Choose an image before publishing."); photosSection.open = true; bad = true; }
      const title = F.title.value().trim();
      if (!title) { F.title.setError(isServiceMode() ? "Give the service a title." : "Give the item a title."); bad = true; }

      // ---- service branch (assumed shape; see SERVICES block)
      if (isServiceMode()) {
        const sCategory = F.service_category.value();
        if (!sCategory) { F.service_category.setError("Choose a service category."); bad = true; }
        const price = C.dollarsToCents(F.service_price_cents.value());
        if (price.error) { F.service_price_cents.setError(price.error); bad = true; }
        else if (price.cents == null) { F.service_price_cents.setError("Enter a price (0 for free)."); bad = true; }
        const duration = Number(F.service_duration_minutes.value());
        if (!Number.isInteger(duration) || duration < 1 || duration > 1440) { F.service_duration_minutes.setError("Enter a whole number from 1 to 1440 minutes."); bad = true; }
        if (!F.description.value().trim()) { F.description.setError("A description is required for a service."); bad = true; }
        const windows = windowsEditor.read();
        if (!windows.ok) bad = true;
        else if (!windows.values.length) { windowsEditor.setError("Add at least one time window when you can provide the service."); bad = true; }
        else if (!Number.isNaN(duration) && !windows.values.some((w) => (new Date(w.end) - new Date(w.start)) / 60000 >= duration)) {
          windowsEditor.setError("At least one window must be long enough for a " + duration + "-minute session."); bad = true;
        }
        if (bad) {
          showNotice(errorBox, "Some fields need attention; see the messages next to them.");
          const first = form.querySelector('[aria-invalid="true"]');
          if (first) first.focus();
          return;
        }
        const serviceBody = {
          allowed_modes: ["service"], title,
          description: F.description.value().trim(),
          category: sCategory, service_price_cents: price.cents, service_duration_minutes: duration, service_available_windows: windows.values,
        };
        submitting = true;
        C.setBusy(submit, true, "Saving service");
        status.textContent = "Saving service…";
        try {
          await publishDraft(serviceBody);
        } catch (err) {
          submitting = false; C.setBusy(submit, false); status.textContent = "";
          if (err instanceof api.ApiError && err.code === "validation_error") {
            const leftovers = C.applyFieldErrors({ title: F.title, description: F.description, category: F.service_category, service_price_cents: F.service_price_cents, service_duration_minutes: F.service_duration_minutes, service_available_windows: windowsEditor }, err.fields);
            showNotice(errorBox, leftovers.length ? "Please fix: " + leftovers.join("; ") : "Some fields need attention; see the messages next to them.");
          } else if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); showNotice(errorBox, authMessage(err)); }
          else showNotice(errorBox, C.errorMessage(err));
        }
        return;
      }

      const category = F.category.value();
      if (!category) { F.category.setError("Choose a category."); bad = true; }
      const modes = [modeSale.input.checked ? "sale" : null, modeBorrow.input.checked ? "borrow" : null].filter(Boolean);
      if (!modes.length) { F.allowed_modes.setError("Pick sale, borrowing, both, or service."); bad = true; }

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
        if (first) {
          let disclosure = first.closest("details");
          while (disclosure) { disclosure.open = true; disclosure = disclosure.parentElement.closest("details"); }
        }
        if (first) first.focus(); // after the banner so the first invalid field keeps focus
        return;
      }

      submitting = true;
      C.setBusy(submit, true, "Saving listing");
      status.textContent = "Saving listing…";
      let listing;
      try {
        await publishDraft(body);
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

    });

    function lines(text) { return String(text || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean); }
  }

  // Rows of start/end datetime-local inputs -> [{start, end}] in UTC.
  function timeWindowsEditor(opts) {
    opts = opts || {};
    const rows = C.el("div", { className: "kv-rows" });
    const error = C.el("p", { className: "field__error", role: "alert" });
    const addRow = (start, end) => {
      const s = C.el("input", { type: "datetime-local", "aria-label": "Window start" });
      const e = C.el("input", { type: "datetime-local", "aria-label": "Window end" });
      if (start) s.value = C.isoToLocal(start);
      if (end) e.value = C.isoToLocal(end);
      const row = C.el("div", { className: "kv-row" }, s, e, C.button({ label: "Remove", size: "sm", attrs: { "aria-label": "Remove this time window" }, onClick: () => { row.remove(); if (!rows.children.length) addRow(); } }));
      rows.append(row);
      return row;
    };
    const initial = Array.isArray(opts.initial) ? opts.initial.filter((w) => w && w.start && w.end) : [];
    if (initial.length) initial.forEach((w) => addRow(w.start, w.end)); else addRow();
    const add = C.button({ label: "+ Add a window", size: "sm", onClick: () => { addRow().querySelector("input").focus(); } });
    const root = C.el("fieldset", {}, C.el("legend", { text: opts.title || "Available time windows" }),
      C.el("p", { className: "field__hint", text: opts.hint || "When you can provide the service. Required: at least one window, and one must be long enough for a session. Times are read in your browser's zone and shown in America/New_York." }),
      rows, C.el("div", { style: { marginTop: "8px" } }, add), error);
    const editor = {
      root, control: rows,
      setValues(windows) { rows.replaceChildren();if(windows.length)windows.forEach(w=>addRow(w.start,w.end));else addRow(); },
      read() {
        editor.clearError();
        const values = [];
        let bad = false;
        rows.querySelectorAll(".kv-row").forEach((row) => {
          const [s, e] = row.querySelectorAll("input");
          const start = C.localToIso(s.value), end = C.localToIso(e.value);
          if (!s.value && !e.value) return;
          if (start === undefined || end === undefined || !start || !end) { bad = true; editor.setError("Each window needs a valid start and end."); return; }
          if (end <= start) { bad = true; editor.setError("A window must end after it starts."); return; }
          values.push({ start, end });
        });
        return bad ? { ok: false } : { ok: true, values };
      },
      setError(m) { error.textContent = m || ""; },
      clearError() { error.textContent = ""; },
    };
    return editor;
  }

  // Compact summary card for a service listing (used for the form preview).
  function serviceSummaryCard(listing) {
    const owner = listing.owner || {};
    return C.card({
      variant: ["compact", "sky"],
      title: listing.title || "Untitled service",
      subtitle: serviceCategoryLabel(listing.category) + " · " + formatDuration(listing.service_duration_minutes),
      badges: [C.modeBadge("service")],
      body: [
        listing.description ? C.el("p", { style: { whiteSpace: "pre-line", overflowWrap: "anywhere" }, text: listing.description }) : null,
        C.el("dl", { className: "kv-list" },
          C.el("dt", { text: "Price per session" }), C.el("dd", { text: api.formatCents(listing.service_price_cents) }),
          C.el("dt", { text: "Session length" }), C.el("dd", { text: formatDuration(listing.service_duration_minutes) }),
          C.el("dt", { text: "Deposit" }), C.el("dd", { text: "None (services have no collateral)" })),
        serviceWindowsNode(listing),
      ],
      footer: owner.display_name ? [C.el("span", { className: "muted", text: owner.display_name }), C.profileBadge(owner)] : null,
    });
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
        // Identity comes from /api/me (the token), never from the page. Keep
        // the failure so "signed out" and "signed in but not verified" differ.
        const [{ listing }, spotsRes, meRes] = await Promise.all([
          api.get("/api/listings/" + enc(listingId)),
          api.get("/api/meeting-spots").catch(() => null),
          api.getToken()
            ? api.get("/api/me").then((r) => ({ profile: r.profile, error: null })).catch((err) => ({ profile: null, error: err }))
            : Promise.resolve({ profile: null, error: null }),
        ]);
        root.removeAttribute("aria-busy");
        const auth = { signedIn: !!api.getToken(), me: meRes.profile, error: meRes.error };
        if (isService(listing)) renderService(listing, auth);
        else render(listing, spotsRes ? spotsRes.meeting_spots : null, auth);
      } catch (err) {
        root.removeAttribute("aria-busy");
        if (err instanceof api.ApiError && err.status === 404) {
          C.state.error(root, { message: "It may have been removed, or the link is wrong." }, { title: "Listing not found", action: C.button({ label: "Browse listings", variant: "primary", size: "sm", href: "/" }) });
        } else {
          C.state.error(root, err, { title: "Could not load this listing", retry: load });
        }
      }
    }

    function render(listing, spots, auth) {
      C.clear(root);
      document.title = listing.title + " · Campus Current";
      const owner = listing.owner || {};
      const me = auth.me;
      const isMine = me && me.id === listing.owner_id;
      const allowed = listing.allowed_modes || [];

      if (params.get("created") === "1") root.append(C.notice("leaf", C.el("span", {}, C.el("strong", { text: "Listing published. " }), "It now appears in search results and on the home page.")));
      if (params.get("photo") === "failed") root.append(C.notice("warn", "The listing was saved, but the photo upload failed. You can add one below with Add photo."));

      // ---- header
      const badges = [];
      allowed.forEach((m) => badges.push(C.modeBadge(m)));
      badges.push(C.statusBadge(listing.status));
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));
      if (isMine) badges.push(C.badge("Your listing", "info"));

      const media = C.el("div", { className: "detail-media" + (listing.public_photo_url ? "" : " detail-media--empty") });
      if (listing.public_photo_url) media.append(C.el("img", { src: listing.public_photo_url, alt: "Photo of " + listing.title }));
      else media.append(C.mediaPlaceholder({ category: listing.category, label: isMine ? "No photo yet. Add one so people can see what you are offering." : "No photo provided" }));
      // Owner: add or replace the photo here; the server swaps the file and
      // the page reloads from the returned listing.
      let photoActions = null;
      if (isMine && !["reserved","sold","draft"].includes(listing.status)) {
        const btn = C.button({ label: listing.public_photo_url ? "Replace photo" : "Add photo", size: "sm", variant: listing.public_photo_url ? "default" : "primary" });
        btn.addEventListener("click", () => openPhotoDialog(listing, btn, () => load()));
        photoActions = C.el("div", { className: "detail-photo-actions" }, btn,
          C.el("span", { className: "muted", text: "Only photos you upload are shown; nothing is filled in automatically." }));
      }

      const facts = C.el("div", { className: "stack" },
        C.el("div", { className: "cluster" }, badges),
        C.el("h1", { style: { marginBottom: "4px" }, text: listing.title }),
        C.el("div", { className: "meta" }, C.el("span", { text: categoryLabel(listing.category) }), C.el("span", { text: "Condition: " + conditionLabel(listing.condition) })),
        listing.description ? C.el("p", { style: { whiteSpace: "pre-line", overflowWrap: "anywhere" }, text: listing.description }) : C.el("p", { className: "muted", text: "No description provided." }),
        section("Specifications", kv(listing.specifications, "No specifications listed.")),
        section("Included accessories", stringList(listing.accessories, "None listed.")),
        section("Known defects", stringList(listing.known_defects, "None listed.")));

      // ---- terms: every amount on its own row, never derived from each other
      const terms = C.el("dl", { className: "kv-list" });
      const row = (k, v, cls) => terms.append(C.el("dt", { text: k }), C.el("dd", { className: cls || "" }, v));
      if (allowed.includes("sale")) row("Sale price", api.formatCents(listing.sale_price_cents));
      if (allowed.includes("borrow")) {
        row("Rental fee", listing.rental_fee_cents === 0 ? "Free loan ($0.00)" : api.formatCents(listing.rental_fee_cents));
        row("Proposed item value", api.formatCents(listing.proposed_item_value_cents));
        const value = listing.proposed_item_value_cents, pct = listing.collateral_percent;
        if (Number.isInteger(value) && Number.isInteger(pct)) {
          const deposit = Math.round((value * pct) / 100);
          const uncovered = Math.max(value - deposit, 0);
          row("Deposit proposed (simulated)", api.formatCents(deposit) + " (" + pct + "% of value)");
          row("Not covered by deposit", api.formatCents(uncovered), uncovered > 0 ? "kv-list__warn" : "");
        } else {
          row("Deposit proposed (simulated)", "Unknown");
        }
        const av = listing.availability || {};
        row("Available", (av.available_from || av.available_until)
          ? (av.available_from ? "From " + api.formatTime(av.available_from) : "") + (av.available_until ? (av.available_from ? " until " : "Until ") + api.formatTime(av.available_until) : "")
          : "No fixed dates");
        if (av.notes) row("Availability notes", av.notes);
      }
      if (!allowed.length) row("Terms", "Unknown");

      // ---- meeting spots
      const spotIds = new Set(listing.meeting_spot_ids || []);
      let spotsNode;
      if (!spotIds.size) spotsNode = C.el("p", { className: "muted", text: "No preferred spots listed; agree one in the exchange." });
      else if (!spots) spotsNode = C.el("p", { className: "muted", text: spotIds.size + " preferred spot(s); details could not be loaded." });
      else {
        const chosen = spots.filter((s) => spotIds.has(s.id));
        spotsNode = C.el("ul", { className: "spot-list" }, chosen.map((s) => C.el("li", {}, C.el("strong", { text: s.label }), C.el("span", { className: "muted", text: " · " + s.public_area + (s.access_notes ? " · " + s.access_notes : "") }))));
      }

      const side = C.el("div", { className: "stack" },
        C.el("section", { className: "card card--sky", "aria-labelledby": "terms-heading" },
          C.el("h2", { id: "terms-heading", text: "Terms" }), terms,
          null),
        C.el("section", { className: "card", "aria-labelledby": "spots-heading" },
          C.el("h2", { id: "spots-heading", text: "Meeting spots" }), spotsNode),
        C.el("section", { className: "card card--leaf", "aria-labelledby": "owner-heading" },
          C.el("h2", { id: "owner-heading", text: "Owner" }),
          C.el("div", { className: "cluster" }, C.el("strong", { text: owner.display_name || "Unknown" }), C.profileBadge(owner)),
          C.el("p", { className: "muted", style: { marginTop: "8px" }, text: "A verification badge only confirms a UNC email; it is not proof of student status or trustworthiness." }),
          exchangeEntry(listing, auth, { label: "Start exchange", noun: "item" })));

      root.append(C.el("div", { className: "detail-grid" },
        C.el("div", { className: "card" }, media, photoActions, facts),
        side));
      const h1 = root.querySelector("h1"); h1.setAttribute("tabindex", "-1"); h1.focus();
    }

    // Service detail: category, price, duration, time windows. No deposit section.
    function renderService(listing, auth) {
      C.clear(root);
      document.title = listing.title + " · Campus Current";
      const owner = listing.owner || {};
      const me = auth.me;
      const isMine = me && me.id === listing.owner_id;
      if (params.get("created") === "1") root.append(C.notice("leaf", C.el("span", {}, C.el("strong", { text: "Service published. " }), "It now appears in search results and on the home page.")));

      const badges = [C.modeBadge("service"), C.statusBadge(listing.status)];
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));
      if (isMine) badges.push(C.badge("Your listing", "info"));

      const media = listing.public_photo_url
        ? C.el("div", { className: "detail-media" }, C.el("img", { src: listing.public_photo_url, alt: "Reference scene for " + listing.title }))
        : null;

      const facts = C.el("div", { className: "stack" },
        C.el("div", { className: "cluster" }, badges),
        C.el("h1", { style: { marginBottom: "4px" }, text: listing.title }),
        C.el("div", { className: "meta" }, C.el("span", { text: serviceCategoryLabel(listing.category) }), C.el("span", { text: "Session: " + formatDuration(listing.service_duration_minutes) })),
        listing.description ? C.el("p", { style: { whiteSpace: "pre-line", overflowWrap: "anywhere" }, text: listing.description }) : C.el("p", { className: "muted", text: "No description provided." }),
        section("Available time windows", serviceWindowsNode(listing)));

      const terms = C.el("dl", { className: "kv-list" },
        C.el("dt", { text: "Price per session" }), C.el("dd", { text: api.formatCents(listing.service_price_cents) }),
        C.el("dt", { text: "Session length" }), C.el("dd", { text: formatDuration(listing.service_duration_minutes) }),
        C.el("dt", { text: "Category" }), C.el("dd", { text: serviceCategoryLabel(listing.category) }));

      const side = C.el("div", { className: "stack" },
        C.el("section", { className: "card card--sky", "aria-labelledby": "terms-heading" },
          C.el("h2", { id: "terms-heading", text: "Terms" }), terms,
          C.el("p", { className: "muted", style: { marginTop: "var(--space-3)" }, text: "Services have no deposit, collateral, or agreed item value." }),
          null),
        C.el("section", { className: "card card--leaf", "aria-labelledby": "owner-heading" },
          C.el("h2", { id: "owner-heading", text: "Provider" }),
          C.el("div", { className: "cluster" }, C.el("strong", { text: owner.display_name || "Unknown" }), C.profileBadge(owner)),
          exchangeEntry(listing, auth, { label: "Request this service", noun: "service" })));

      root.append(C.el("div", { className: "detail-grid" }, C.el("div", { className: "card" }, media, facts), side));
      const h1 = root.querySelector("h1"); h1.setAttribute("tabindex", "-1"); h1.focus();
    }

    // Entry point into the exchange flow (POST /api/exchanges, then
    // /exchanges/{id}). Shown as a live button only to a signed-in user whose
    // identity the server confirmed (/api/me 200), who is not the owner, on an
    // available listing; every other case explains itself in the hint.
    // ?from_request=<id> (set by the results page) links the exchange to the
    // user's own request; ?mode=<sale|borrow> preselects a mode.
    function exchangeEntry(listing, auth, opts) {
      const MODE_LABEL = { sale: "Buy it", borrow: "Borrow it", service: "Book a session" };
      const allowed = (listing.allowed_modes || []).filter((m) => MODE_LABEL[m]);
      const isMine = auth.me && auth.me.id === listing.owner_id;
      const exchangeCreationKey=crypto.randomUUID();
      const box = C.el("div", { className: "start-exchange stack--tight" });
      const hint = (text) => C.el("p", { className: "muted", id: "start-hint", text });

      if (isMine) {
        box.append(hint("This is your own listing. Only another member can start an exchange for it; manage it from My listings."));
        return box;
      }
      if (listing.status !== "available") {
        box.append(hint("This " + opts.noun + " is " + String(listing.status).replace(/_/g, " ") + " right now, so a new exchange cannot be started."));
        return box;
      }
      if (!allowed.length) {
        box.append(hint("This listing has no exchange terms yet."));
        return box;
      }
      if (!auth.signedIn) {
        box.append(C.button({ label: "Sign in to start an exchange", variant: "primary", href: "/sign-in" }),
          hint("Browsing is open to everyone. Starting an exchange needs a confirmed UNC email."));
        return box;
      }
      if (!auth.me) {
        // A token exists but the server did not accept it (401) or the account
        // is not a verified, allowed-domain user (403).
        box.append(C.notice("warn", C.el("span", {},
          C.el("strong", { text: "Cannot start an exchange yet. " }), C.errorMessage(auth.error), " ",
          C.el("a", { href: "/sign-in", text: "Sign in" }), ".")));
        return box;
      }

      // ---- live button
      let sourceId = params.get("from_request") || null;
      let mode = allowed.length === 1 ? allowed[0] : (allowed.includes(params.get("mode")) ? params.get("mode") : null);
      let starting = false;
      const btn = C.button({ label: opts.label, variant: "primary", attrs: { "aria-describedby": "start-hint start-todo start-error" } });
      const todo = C.el("p", { className: "field__todo", id: "start-todo" });
      const errorBox = C.el("div", { className: "notice notice--error", role: "alert", id: "start-error", hidden: true });
      const statusLine = C.el("span", { className: "muted", "aria-live": "polite" });

      let picker = null;
      if (allowed.length > 1) {
        const choices = C.el("div", { className: "choices", role: "radiogroup", "aria-labelledby": "start-mode-legend" });
        allowed.forEach((m) => {
          const input = C.el("input", { type: "radio", name: "exchange_mode", value: m });
          input.checked = m === mode;
          input.addEventListener("change", () => { if (input.checked) { mode = m; refresh(); } });
          choices.append(C.el("label", { className: "choice" }, input, C.el("span", { text: MODE_LABEL[m] })));
        });
        picker = C.el("fieldset", { className: "start-exchange__modes" },
          C.el("legend", { id: "start-mode-legend", text: "How do you want it?" }),
          C.el("p", { className: "field__hint", text: "This listing offers more than one way. Pick one; the terms for that way start the offer." }),
          choices);
      }

      const intro = sourceId
        ? hint("Opens a private exchange with the owner, linked to your request. Terms start from the listing; both of you must accept them.")
        : hint("Opens a private exchange with the owner where you agree the terms. Both of you must accept before anything is reserved.");

      function refresh() {
        todo.textContent = mode ? "" : "Choose one way first.";
        btn.disabled = !mode || starting;
      }
      refresh();

      function fail(content, action) {
        starting = false;
        C.setBusy(btn, false);
        refresh();
        statusLine.textContent = "";
        C.clear(errorBox);
        errorBox.append(C.el("div", {}, content, action ? C.el("div", { style: { marginTop: "8px" } }, action) : null));
        errorBox.hidden = false;
        errorBox.setAttribute("tabindex", "-1");
        errorBox.focus();
      }
      const reloadBtn = () => C.button({ label: "Reload listing", size: "sm", onClick: load });
      const dropSourceBtn = () => C.button({ label: "Start without linking the request", size: "sm", onClick: () => { sourceId = null; errorBox.hidden = true; start(); } });

      async function start() {
        if (starting || !mode) return;
        starting = true;
        errorBox.hidden = true;
        C.setBusy(btn, true, "Starting exchange");
        statusLine.textContent = "Starting exchange…";
        const body = { listing_id: listing.id, mode };
        if (sourceId) body.source_request_id = sourceId;
        try {
          const res = await api.post("/api/exchanges",body,{headers:{"Idempotency-Key":exchangeCreationKey}});
          const id = res && res.exchange && res.exchange.id;
          if (!id) { fail("The server did not return an exchange id. Check My exchanges before trying again.", C.button({ label: "My exchanges", size: "sm", href: "/exchanges" })); return; }
          statusLine.textContent = "Opening your exchange…";
          window.location.href = "/exchanges/" + enc(id);
        } catch (err) {
          if (!(err instanceof api.ApiError)) { fail(C.errorMessage(err)); return; }
          const aboutSource = err.code === "request_closed"
            || (err.code === "validation_error" && err.fields && err.fields.source_request_id)
            || (err.status === 404 && /request/i.test(err.message || ""));
          if (aboutSource && sourceId) {
            fail(C.el("span", {}, C.el("strong", { text: "Your request could not be linked. " }),
              err.code === "request_closed" ? "That request is closed." : (err.fields && err.fields.source_request_id) || err.message || "It was not found.",
              " You can still start the exchange on its own."), dropSourceBtn());
          } else if (err.code === "forbidden") {
            // Owner on their own listing (or similar permission rule); not a sign-in problem.
            fail(err.message || "You cannot start an exchange for this listing.");
          } else if (err.status === 401 || err.code === "email_not_confirmed" || err.code === "domain_not_allowed" || err.code === "auth_required" || err.code === "invalid_token") {
            fail(C.el("span", {}, C.errorMessage(err), " ", C.el("a", { href: "/sign-in", text: "Sign in" }), "."));
          } else if (err.code === "reservation_conflict" || err.code === "listing_unavailable") {
            fail(C.el("span", {}, C.el("strong", { text: "No longer available. " }),
              "Someone else reserved this " + opts.noun + ", or it was withdrawn, since you opened this page. No funds were charged."), reloadBtn());
          } else if (err.status === 404) {
            fail("This listing no longer exists.", C.button({ label: "Browse listings", size: "sm", href: "/" }));
          } else if (err.code === "validation_error") {
            const fields = err.fields || {};
            if (fields.mode) fail(C.el("span", {}, C.el("strong", { text: "That way is not offered. " }), "The listing's terms changed; reload to see the current ones."), reloadBtn());
            else fail("Please fix: " + (Object.entries(fields).map(([k, v]) => k.replace(/_/g, " ") + ": " + v).join("; ") || err.message || "the request was invalid."));
          } else {
            fail(C.errorMessage(err), err.status === 409 ? reloadBtn() : null);
          }
        }
      }
      btn.addEventListener("click", start);

      if (picker) box.append(picker);
      box.append(todo, C.el("div", { className: "cluster", style: { marginTop: "var(--space-2)" } }, btn, statusLine), errorBox, intro);
      return box;
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

  // ============================================================ MY LISTINGS
  function initMyListings(root) {
    document.title = "My Listings · Campus Current";
    document.body.dataset.page = "my-listings";
    let me = null;
    let listings = [];
    let tab = "active";
    let kind = "all";                               // all | items | services
    // Listing status is available | reserved | sold | withdrawn for every kind
    // (docs/contracts.md). A loan keeps an item `reserved`; a booked session
    // keeps a service `reserved` and completion releases it to `available`.
    // "Scheduled" and "completed" are exchange statuses, not listing ones.
    const ACTIVE = ["available", "reserved"];
    const PAST = ["sold", "withdrawn"];
    const KINDS = [["all", "All"], ["items", "Items"], ["services", "Services"]];
    const ofKind = (l) => kind === "all" || (kind === "services" ? isService(l) : !isService(l));
    const withdrawing = new Set();                  // ids with a withdraw in flight

    document.addEventListener("campus:auth-changed", load);
    load();

    async function load() {
      if (!api.getToken()) { window.location.replace("/sign-in"); return; }
      root.setAttribute("aria-busy", "true");
      C.state.loading(root, "Loading your listings…");
      try {
        me = (await api.get("/api/me")).profile;                      // identity from the token, never the page
        listings = (await api.get("/api/listings?owner_id=" + enc(me.id) + "&status=all")).listings || [];
        listings = listings.filter((l) => l.owner_id === me.id);    // defensive: never show someone else's
        root.removeAttribute("aria-busy");
        render();
      } catch (err) {
        root.removeAttribute("aria-busy");
        if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); window.location.replace("/sign-in"); return; }
        C.state.error(root, err, { title: "Could not load your listings", retry: load });
      }
    }

    function render() {
      C.clear(root);
      const inKind = listings.filter(ofKind);
      const counts = { active: inKind.filter((l) => ACTIVE.includes(l.status)).length, past: inKind.filter((l) => PAST.includes(l.status)).length };
      const tabs = C.el("div", { className: "tabs", role: "tablist", "aria-label": "Listing status" },
        tabButton("active", "Active", counts.active), tabButton("past", "Past", counts.past));
      const kindFilter = C.el("div", { className: "cluster mine-kind", role: "group", "aria-label": "Show items or services" },
        C.el("span", { className: "muted", id: "mine-kind-label", text: "Show" }),
        KINDS.map(([key, label]) => {
          const n = key === "all" ? listings.length : listings.filter((l) => (key === "services" ? isService(l) : !isService(l))).length;
          return C.el("button", {
            type: "button", className: "btn btn--sm" + (kind === key ? " btn--primary" : ""), "aria-pressed": kind === key ? "true" : "false",
            onClick: () => { kind = key; render(); root.querySelector('.mine-kind [aria-pressed="true"]').focus(); },
          }, label + " ", C.badge(String(n), kind === key ? "info" : "neutral"));
        }));
      root.append(
        C.el("section", { className: "card" },
          C.el("div", { className: "section__head" },
            C.el("h1", { id: "mine-heading", tabindex: "-1", style: { margin: 0 }, text: "My Listings" }),
            C.button({ label: "Post a new listing", variant: "primary", size: "sm", href: "/listings/new" })),
          C.el("p", { className: "lede", text: "Manage your items and services. Only available listings can be withdrawn; a completed session releases its service listing." }),
          kindFilter, tabs),
        C.el("div", { id: "mine-grid", className: "grid catalog-list", role: "tabpanel", "aria-live": "polite" }));
      renderGrid();
      if (!root.dataset.focused) { root.dataset.focused = "1"; $("mine-heading").focus(); }
    }

    // Status wording for a service listing: a reserved service is a scheduled
    // session (reserve_listing runs when both accept); nothing is invented.
    function mineStatusBadge(listing) {
      if (isService(listing) && listing.status === "reserved") return C.badge("Scheduled", "info");
      return C.statusBadge(listing.status);
    }

    function tabButton(key, label, count) {
      const selected = tab === key;
      return C.el("button", {
        type: "button", role: "tab", className: "tab" + (selected ? " tab--selected" : ""), "aria-selected": selected ? "true" : "false",
        onClick: () => { tab = key; render(); root.querySelector('.tab[aria-selected="true"]').focus(); },
        onKeydown: (e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { tab = tab === "active" ? "past" : "active"; render(); root.querySelector('.tab[aria-selected="true"]').focus(); } },
      }, label + " ", C.badge(String(count), selected ? "info" : "neutral"));
    }

    function renderGrid() {
      const grid = $("mine-grid");
      C.clear(grid);
      if (!listings.length) {
        C.state.empty(grid, { title: "You haven't posted anything yet", message: "List an item for sale or to borrow, or offer a service.",
          action: C.button({ label: "Post a new listing", variant: "primary", size: "sm", href: "/listings/new" }) });
        return;
      }
      const shown = listings.filter(ofKind).filter((l) => (tab === "active" ? ACTIVE : PAST).includes(l.status));
      if (!shown.length) {
        const noun = kind === "services" ? "services" : kind === "items" ? "items" : "listings";
        C.state.empty(grid, { title: tab === "active" ? "No active " + noun : "No past " + noun,
          message: tab === "active" ? "Withdrawn and sold " + noun + " are under Past." : "Sold and withdrawn " + noun + " will appear here.",
          action: kind !== "all" ? C.button({ label: "Show all", size: "sm", onClick: () => { kind = "all"; render(); root.querySelector('.mine-kind [aria-pressed="true"]').focus(); } }) : undefined });
        return;
      }
      shown.forEach((l) => grid.append(mineCard(l)));
    }

    function mineCard(listing) {
      const service = isService(listing);
      const badges = service ? [C.modeBadge("service")] : (listing.allowed_modes || []).map((m) => C.modeBadge(m));
      badges.push(mineStatusBadge(listing));
      if (listing.status === "reserved" && listing.active_exchange_id) badges.push(C.badge("In an exchange", "info"));

      const price = C.el("div", { className: "stack--tight" });
      if (service) price.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.service_price_cents) }), C.el("span", { className: "muted", text: " per " + formatDuration(listing.service_duration_minutes) + " session" })));
      if (!service && (listing.allowed_modes || []).includes("sale")) price.append(C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.sale_price_cents) }), C.el("span", { className: "muted", text: " to buy" })));
      if (!service && (listing.allowed_modes || []).includes("borrow")) price.append(C.el("div", {}, C.el("span", { className: "price", text: listing.rental_fee_cents === 0 ? "Free loan" : api.formatCents(listing.rental_fee_cents) + " fee" }), C.el("span", { className: "muted", text: " · value " + api.formatCents(listing.proposed_item_value_cents) })));

      const actions = C.el("span", { className: "cluster" });
      actions.append(C.button({ label: listing.status === "draft" ? "Finish publishing" : "View", size: "sm", href: listing.status === "draft" ? "/listings/new?draft="+enc(listing.id) : "/listings/" + enc(listing.id) }));
      // Photo: items only (services show their category icon). Add from the
      // placeholder, replace from the actions; both open the same dialog.
      const media = cardMedia(listing);
      const onUploaded = (updated) => {
        listings = listings.map((l) => (l.id === updated.id ? updated : l));
        render();
        const next = root.querySelector('[data-photo-for="' + updated.id + '"]');
        if (next) next.focus();
      };
      if (!["reserved", "sold", "draft"].includes(listing.status) && listing.public_photo_url) {
        const btn = C.button({ label: "Replace photo", size: "sm", attrs: { "data-photo-for": listing.id } });
        btn.addEventListener("click", () => openPhotoDialog(listing, btn, onUploaded));
        actions.append(btn);
      } else if (!["reserved", "sold", "draft"].includes(listing.status)) {
        const add = C.button({ label: "Add photo", size: "sm", variant: "primary", attrs: { className: "btn btn--sm btn--primary media-action", "data-photo-for": listing.id, "aria-label": "Add a photo to " + listing.title } });
        add.addEventListener("click", () => openPhotoDialog(listing, add, onUploaded));
        media.placeholder.action = add;
      }
      if (listing.status === "available") {
        const btn = C.button({ label: "Withdraw", size: "sm", variant: "danger", attrs: { "aria-describedby": "withdraw-hint" } });
        btn.addEventListener("click", () => confirmWithdraw(listing, btn));
        actions.append(btn);
      } else if (listing.status === "reserved") {
        actions.append(C.el("span", { className: "muted", text: service ? "Session scheduled; manage it in the exchange." : "Reserved or on loan; manage it in the exchange." }));
      } else if (listing.status === "withdrawn") {
        const btn = C.button({ label: "Relist", size: "sm", variant: "leaf" });
        btn.addEventListener("click", () => relist(listing, btn));
        actions.append(btn);
      }

      return C.card({
        variant: ["compact"],
        media,
        title: C.el("a", { href: "/listings/" + enc(listing.id), text: listing.title }),
        subtitle: categoryLabel(listing.category),
        badges,
        body: [price, C.el("p", { className: "muted", style: { fontSize: ".85rem" }, text: "Updated " + api.formatTime(listing.updated_at) })],
        footer: [C.el("span", { className: "visually-hidden", id: "withdraw-hint", text: "Withdrawing hides the listing; you will be asked to confirm." }), actions],
      });
    }

    // Owners may set status back to "available" (docs/contracts.md, PATCH /api/listings/{id}).
    async function relist(listing, btn) {
      if (withdrawing.has(listing.id)) return;
      withdrawing.add(listing.id);
      C.setBusy(btn, true, "Relisting");
      try {
        const data = await api.patch("/api/listings/" + enc(listing.id), { status: "available" });
        listings = listings.map((l) => (l.id === listing.id ? data.listing : l));
        C.toast("Listing is available again.", "leaf");
        tab = "active";
        render();
        root.querySelector('.tab[aria-selected="true"]').focus();
      } catch (err) {
        C.setBusy(btn, false);
        C.toast(C.errorMessage(err), "error", 6000);
      } finally {
        withdrawing.delete(listing.id);
      }
    }

    function confirmWithdraw(listing, opener) {
      if (withdrawing.has(listing.id)) return;
      const errorBox = C.el("div", { className: "notice notice--error", role: "alert", hidden: true });
      const cancel = C.button({ label: "Keep it listed", onClick: () => dlg.close("cancel") });
      const confirm = C.button({ label: "Withdraw listing", variant: "danger" });
      const dlg = C.dialog({
        title: "Withdraw this listing?",
        body: C.el("div", {}, errorBox,
          C.el("p", {}, C.el("strong", { text: listing.title }), " will no longer appear in search or on the home page. You can relist it later from the Past tab."),
          C.el("p", { className: "muted", text: "Nothing is charged or refunded; there is no exchange attached to an available listing." })),
        actions: [cancel, confirm],
      });
      dlg.open(opener);
      confirm.focus();
      confirm.addEventListener("click", async () => {
        if (withdrawing.has(listing.id)) return;          // double-click guard
        withdrawing.add(listing.id);
        C.setBusy(confirm, true, "Withdrawing");
        cancel.disabled = true;
        try {
          const data = await api.patch("/api/listings/" + enc(listing.id), { status: "withdrawn" });
          listings = listings.map((l) => (l.id === listing.id ? data.listing : l));
          dlg.close("done");
          C.toast("Listing withdrawn.", "leaf");
          tab = "past";
          render();
          root.querySelector('.tab[aria-selected="true"]').focus();
        } catch (err) {
          C.setBusy(confirm, false);
          cancel.disabled = false;
          if (err instanceof api.ApiError && err.code === "listing_locked") showNotice(errorBox, "This listing is reserved or sold and belongs to an exchange, so it cannot be withdrawn.");
          else if (err instanceof api.ApiError && err.code === "forbidden") showNotice(errorBox, "Only the owner can withdraw a listing.");
          else if (C.isAuthError(err)) { if (err.status === 401) api.setToken(null); showNotice(errorBox, authMessage(err)); }
          else showNotice(errorBox, C.errorMessage(err));
        } finally {
          withdrawing.delete(listing.id);
        }
      });
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
        (!mode || (mode === "service" ? isServiceRequest(r) : (r.modes || []).includes(mode))) &&
        (!area || (area === "__none__" ? !r.area : r.area === area)));
      C.clear(grid);
      if (!requests.length) {
        count.textContent = "";
        C.state.empty(grid, { title: "No open requests right now", message: "When someone publishes a request, it will appear here.",
          action: C.button({ label: "Post a request", variant: "primary", size: "sm", href: "/" }) });
        return;
      }
      count.textContent = (shown.length === requests.length
        ? requests.length + (requests.length === 1 ? " open request" : " open requests")
        : shown.length + " of " + requests.length + " open requests match");
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
      const service = isServiceRequest(r);
      const modes = r.modes || [];
      const badges = service
        ? [C.badge("Needs a service", "service")]
        : modes.map((m) => C.badge(m === "sale" ? "Wants to buy" : "Wants to borrow", m === "sale" ? "sale" : "borrow"));
      if (mine) badges.push(C.badge("Your request", "info"));
      if (requester.is_demo) badges.push(C.badge("Demo account", "fixture"));

      const specs = Object.entries(r.required_specifications || {});
      const prefs = Object.entries(r.preferred_specifications || {});
      const item = C.el("div", { className: "stack--tight" },
        C.el("div", { className: "req-item", text: r.category ? categoryLabel(r.category) : (service ? "Service not specified" : "Item not specified") }),
        specs.length ? C.el("dl", { className: "specs" }, specs.flatMap(([k, v]) => [C.el("dt", { text: k.replace(/_/g, " ") }), C.el("dd", { text: String(v) })])) : C.el("p", { className: "muted", text: "No required details given." }),
        prefs.length ? C.el("p", { className: "muted", text: "Prefers " + prefs.map(([k, v]) => k.replace(/_/g, " ") + " " + String(v)).join(", ") }) : null);

      const facts = C.el("dl", { className: "kv-list kv-list--plain" },
        C.el("dt", { text: "Needed by" }), C.el("dd", { text: formatDateOnly(r.needed_by_date) }),
        C.el("dt", { text: "Campus area" }), C.el("dd", { text: r.area || "Not given" }),
        C.el("dt", { text: "Budget" }), C.el("dd", { text: r.budget_cents != null ? "Up to " + api.formatCents(r.budget_cents) : "Not given" }),
        service ? C.el("dt", { text: "Session" }) : null, service ? C.el("dd", { text: formatDuration(r.service_duration_minutes) }) : null);

      // Only the requester can start an exchange, so an owner responds by
      // posting a listing; matching brings it to the requester.
      let action;
      let respondNote = null;
      if (mine) {
        action = C.button({ label: "View matches", size: "sm", href: "/results/" + enc(r.id) });
      } else if (me) {
        action = C.button({ label: service ? "Offer this service" : "Post a listing for this", variant: "leaf", size: "sm",
          href: "/listings/new?from_request=" + enc(r.id), attrs: { "aria-describedby": "respond-note-" + r.id } });
        respondNote = C.el("p", { className: "muted feed-respond", id: "respond-note-" + r.id,
          text: "Have one? Post it as a listing; the requester finds it through matching and starts the exchange." });
      } else {
        action = C.button({ label: "Sign in to respond", size: "sm", href: "/sign-in" });
      }

      return C.card({
        variant: ["compact"],
        badges,
        body: [item, facts, respondNote],
        footer: [
          C.el("span", { className: "cluster" }, C.el("span", { className: "muted", text: requester.display_name || "Member" }), C.profileBadge(requester),
            C.el("span", { className: "muted", text: "Posted " + api.formatTime(r.created_at) })),
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
      const flag = opts.flagged && key != null && opts.flagged.has(String(key).toLowerCase()) ? C.badge(opts.flagLabel || "Please confirm", opts.flagVariant || "warn") : null;
      if (flag) v.setAttribute("aria-description", opts.flagLabel || "please confirm");
      const row = C.el("div", { className: "kv-row" + (flag ? " kv-row--flag" : "") }, k, v, flag,
        C.button({ label: "Remove", size: "sm", attrs: { "aria-label": "Remove this " + title.toLowerCase() + " row" }, onClick: () => { row.remove(); if (!rows.children.length) addRow(); } }));
      rows.append(row);
      return row;
    };
    const entries = Object.entries(initial || {});
    if (entries.length) entries.forEach(([k, v]) => addRow(k, v)); else addRow();
    const add = C.button({ label: "+ Add another", size: "sm", onClick: () => { const r = addRow(); r.querySelector("input").focus(); } });
    const legend = C.el("legend", {}, title + " ", (entries.length || opts.badge === false) ? null : C.badge("None known", "neutral"));
    const summary = C.el("summary", {text:title});
    const root = C.el("details", {className:"spec-disclosure"}, summary,
      C.el("fieldset", {}, legend, C.el("p", { className: "field__hint", text: hint }), rows, add, error));
    function updateSummary() {
      const pairs = Array.from(rows.querySelectorAll(".kv-row")).map(r => {
        const [k,v] = r.querySelectorAll("input");return k.value.trim() && v.value.trim() ? k.value.trim()+": "+v.value.trim() : "";
      }).filter(Boolean);
      summary.textContent = title + (pairs.length ? " — " + pairs.slice(0,2).join(", ") + (pairs.length>2?" +"+(pairs.length-2):"") : " (optional)");
    }
    root.addEventListener("input",updateSummary);root.addEventListener("click",()=>queueMicrotask(updateSummary));updateSummary();
    return {
      root,
      control: rows,
      setValues(values) { rows.replaceChildren();const entries=Object.entries(values);if(entries.length)entries.forEach(([k,v])=>addRow(k,v));else addRow();updateSummary(); },
      add(key, value) {
        // Fill the first empty row if there is one, else append.
        const empty = Array.from(rows.querySelectorAll(".kv-row")).find((r) => { const [k, v] = r.querySelectorAll("input"); return !k.value && !v.value; });
        if (empty && key != null) { const [k, v] = empty.querySelectorAll("input"); k.value = key; v.value = String(value); return empty; }
        return addRow(key, value);
      },
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
      setError(m) { error.textContent = m || ""; if(m) root.open=true; },
      clearError() { error.textContent = ""; },
    };
  }

  // ------------------------------------------------------------ listings grid
  async function loadListings() {
    const grid = $("listings");
    if (!grid) return;
    grid.setAttribute("aria-busy", "true");
    C.state.loading(grid, "Loading available listings…");
    const version = ++listingLoadVersion;
    try {
      const query = new URLSearchParams();
      if ($("catalog-kind") && $("catalog-kind").value) query.set("mode", $("catalog-kind").value);
      if ($("catalog-category") && $("catalog-category").value) query.set("category", $("catalog-category").value);
      const { listings } = await api.get("/api/listings" + (query.size ? "?" + query.toString() : ""));
      if (version !== listingLoadVersion) return;
      grid.removeAttribute("aria-busy");
      if (!listings || !listings.length) {
        C.state.empty(grid, {
          title: query.size ? "No listings match these filters" : "Nothing listed yet",
          message: query.size ? "Try another offer type or category." : "Be the first to offer an item or service.",
          action: C.button({ label: "New Listing", variant: "primary", size: "sm", href: "/listings/new" }),
        });
        return;
      }
      C.clear(grid);
      listings.forEach((listing) => grid.append(listingCard(listing)));
    } catch (err) {
      if (version !== listingLoadVersion) return;
      grid.removeAttribute("aria-busy");
      C.state.error(grid, err, { title: "Could not load listings", retry: loadListings });
    }
  }

  // ---------------------------------------------------------- LISTING PHOTOS
  // Only photos the owner uploaded (listing.public_photo_url) are ever shown;
  // nothing is fetched from the web or generated. Cards without one get the
  // category placeholder from components.mediaPlaceholder.
  function photoLimitBytes() {
    return Math.min(Number((window.CAMPUS_CONFIG || {}).max_upload_bytes) || Infinity, 5 * 1024 * 1024);
  }
  function cardMedia(listing) {
    if (listing.public_photo_url) return { src: listing.public_photo_url, alt: (isService(listing) ? "Reference scene for " : "Photo of ") + (listing.title || "listing") };
    return isService(listing)
      ? { placeholder: { category: listing.category, kind: "service", label: serviceCategoryLabel(listing.category) } }
      : { placeholder: { category: listing.category } };
  }

  // Add or replace a listing's photo through POST /api/listings/{id}/photo
  // (owner only; the server swaps the file and returns the updated listing).
  // onUploaded(listing) receives the server's listing.
  function openPhotoDialog(listing, opener, onUploaded) {
    const limit = photoLimitBytes();
    const limitMb = Math.round(limit / (1024 * 1024));
    const hasPhoto = !!listing.public_photo_url;
    const field = C.field({ id: C.nextId("photo"), label: hasPhoto ? "New photo" : "Photo", type: "file", required: true,
      attrs: { accept: "image/jpeg,image/png,image/webp" },
      hint: "JPEG, PNG, or WebP up to " + limitMb + " MB. It is shown publicly on the listing. Only photos you upload are ever shown; nothing is filled in for you." });
    const preview = C.el("div", { className: "photo-preview", hidden: true }, C.el("img", { alt: "Preview of the chosen photo" }));
    const errorBox = C.el("div", { className: "notice notice--error", role: "alert", hidden: true });
    const current = hasPhoto
      ? C.el("div", { className: "cluster" }, C.el("div", { className: "photo-preview", style: { marginTop: 0, width: "120px" } }, C.el("img", { src: listing.public_photo_url, alt: "Current photo of " + listing.title })),
          C.el("span", { className: "muted", text: "Current photo. The new one replaces it." }))
      : null;
    let objectUrl = null;
    let uploading = false;
    let file = null;
    const cancel = C.button({ label: "Cancel", onClick: () => dlg.close("cancel") });
    const submit = C.button({ label: hasPhoto ? "Replace photo" : "Add photo", variant: "leaf", attrs: { disabled: true } });

    function clearPreview() {
      if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
      preview.hidden = true;
      file = null;
      submit.disabled = true;
    }
    field.control.addEventListener("change", () => {
      field.clearError();
      showNotice(errorBox, null);
      const chosen = field.control.files[0];
      clearPreview();
      if (!chosen) return;
      if (!/^image\/(jpeg|png|webp)$/.test(chosen.type)) { field.setError("Choose a JPEG, PNG, or WebP image."); field.control.value = ""; return; }
      if (chosen.size > limit) { field.setError("That photo is over " + limitMb + " MB. Choose a smaller one."); field.control.value = ""; return; }
      file = chosen;
      objectUrl = URL.createObjectURL(chosen);
      preview.querySelector("img").src = objectUrl;
      preview.hidden = false;
      submit.disabled = false;
    });

    const dlg = C.dialog({
      title: hasPhoto ? "Replace the photo" : "Add a photo",
      body: C.el("div", { className: "stack--tight" },
        C.el("p", {}, C.el("strong", { text: listing.title })),
        current, field.root, preview, errorBox),
      actions: [cancel, submit],
      onClose: () => { if (objectUrl) URL.revokeObjectURL(objectUrl); dlg.root.remove(); },
    });
    submit.addEventListener("click", async () => {
      if (uploading || !file) return;
      uploading = true;
      C.setBusy(submit, true, "Uploading photo");
      cancel.disabled = true;
      showNotice(errorBox, null);
      try {
        const data = await api.upload("/api/listings/" + enc(listing.id) + "/photo", "photo", file);
        dlg.close("done");
        C.toast(hasPhoto ? "Photo replaced." : "Photo added.", "leaf");
        if (onUploaded) onUploaded(data.listing);
      } catch (err) {
        uploading = false;
        C.setBusy(submit, false);
        cancel.disabled = false;
        if (err instanceof api.ApiError && (err.code === "unsupported_image" || err.code === "payload_too_large")) {
          field.setError((err.fields && err.fields.photo) || err.message || "That file could not be used.");
          field.control.focus();
        } else if (err instanceof api.ApiError && err.code === "validation_error") {
          field.setError((err.fields && err.fields.photo) || err.message);
        } else if (err instanceof api.ApiError && err.code === "forbidden") {
          showNotice(errorBox, "Only the owner can change this listing's photo.");
        } else if (err instanceof api.ApiError && err.status === 404) {
          showNotice(errorBox, "This listing no longer exists.");
        } else if (C.isAuthError(err)) {
          if (err.status === 401) api.setToken(null);
          showNotice(errorBox, authMessage(err));
        } else {
          showNotice(errorBox, C.errorMessage(err));
        }
      }
    });
    dlg.open(opener);
    field.control.focus();
    return dlg;
  }

  function listingCard(listing) {
    const owner = listing.owner || {};
    if (isService(listing)) {
      const badges = [C.modeBadge("service")];
      if (listing.status !== "available") badges.push(C.statusBadge(listing.status));
      if (owner.is_demo) badges.push(C.badge("Demo account", "fixture"));
      return C.card({
        variant: ["compact"], interactive: true,
        media: cardMedia(listing),
        title: C.el("a", { className: "card__link", href: "/listings/" + enc(listing.id), text: listing.title }),
        badges,
        body: [
          C.el("div", { className: "meta" }, C.el("span", { text: serviceCategoryLabel(listing.category) }), C.el("span", { text: "Session: " + formatDuration(listing.service_duration_minutes) })),
          C.el("div", {}, C.el("span", { className: "price", text: api.formatCents(listing.service_price_cents) }), C.el("span", { className: "muted", text: " per session · no deposit" })),
          serviceWindowsNode(listing, 2),
        ],
        footer: [C.el("span", { className: "muted", text: owner.display_name || "Provider" }), C.profileBadge(owner)],
      });
    }
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
      C.el("span", { text: categoryLabel(listing.category) }),
      listing.condition ? C.el("span", { text: "Condition: " + conditionLabel(listing.condition) }) : C.el("span", { text: "Condition unknown" }),
      listing.known_defects && listing.known_defects.length ? C.el("span", { text: listing.known_defects.length + " known defect" + (listing.known_defects.length > 1 ? "s" : "") }) : null);

    const title = C.el("a", { className: "card__link", href: "/listings/" + enc(listing.id), text: listing.title });

    return C.card({
      variant: ["compact"], interactive: true,
      media: cardMedia(listing),
      title, badges,
      body: [meta, money, specList],
      footer: [C.el("span", { className: "muted", text: owner.display_name || "Owner" }), C.profileBadge(owner)],
    });
  }
})();
