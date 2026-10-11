// Campus Current shared UI components (Person 3). Documented in docs/design.md.
//
// Exposes window.components with builders for the six shared components
// (button, field, card, dialog, badge, offerSummary) plus loading / empty /
// error state helpers that Person 4 reuses on the exchange screens.
//
// Rules baked in here:
//  - Every string from the server is rendered with textContent, never innerHTML.
//  - Money is integer cents; display goes through api.formatCents. Unknown
//    (null/undefined) renders as "unknown", never as $0.00.
//  - The offer summary shows the server's uncovered_value_cents and never
//    recomputes or invents money, acceptance, or verification facts.
//  - Deposit/payment language is always labeled simulated.

(function () {
  "use strict";

  const SIMULATION_LABEL = "Simulated: no real funds are reserved or charged.";

  // ------------------------------------------------------------------ el()
  // el("div", {className: "x", text: "hi", dataset: {id: 1}, onClick: fn}, child, ...)
  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value === null || value === undefined || value === false) continue;
        if (key === "className") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value; // trusted, static markup only
        else if (key === "dataset") Object.assign(node.dataset, value);
        else if (key === "style") Object.assign(node.style, value);
        else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
        else if (value === true) node.setAttribute(key, "");
        else node.setAttribute(key, String(value));
      }
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  let uid = 0;
  const nextId = (prefix) => `${prefix || "cc"}-${++uid}`;

  // --------------------------------------------------------------- 1. button
  // button({label, variant: "primary"|"leaf"|"ghost"|"danger"|"default", size: "sm",
  //         type, block, onClick, attrs})
  function button(opts) {
    opts = opts || {};
    const classes = ["btn"];
    if (opts.variant && opts.variant !== "default") classes.push("btn--" + opts.variant);
    if (opts.size === "sm") classes.push("btn--sm");
    if (opts.block) classes.push("btn--block");
    if (opts.icon) classes.push("btn--icon");
    if (opts.href) {
      // Link styled as a button.
      return el("a", Object.assign({ className: classes.join(" "), href: opts.href, text: opts.label }, opts.attrs || {}));
    }
    return el("button", Object.assign({
      className: classes.join(" "),
      type: opts.type || "button",
      text: opts.label,
      onClick: opts.onClick,
    }, opts.attrs || {}));
  }

  // Toggle a busy spinner on any .btn; keeps the label for screen readers.
  function setBusy(btn, busy, busyLabel) {
    if (!btn) return;
    if (busy) {
      btn.dataset.idleLabel = btn.textContent;
      btn.setAttribute("aria-busy", "true");
      btn.disabled = true;
      if (busyLabel) btn.setAttribute("aria-label", busyLabel);
    } else {
      btn.removeAttribute("aria-busy");
      btn.disabled = false;
      btn.removeAttribute("aria-label");
      if (btn.dataset.idleLabel !== undefined) { btn.textContent = btn.dataset.idleLabel; delete btn.dataset.idleLabel; }
    }
  }

  // ---------------------------------------------------------------- 2. field
  // field({id, name, label, type, hint, placeholder, value, required, optional,
  //        options: [{value,label}], prefix: "$", attrs})
  // Returns {root, control, setError(msg), clearError(), value()}.
  function field(opts) {
    opts = opts || {};
    const id = opts.id || nextId("field");
    const hintId = id + "-hint";
    const errorId = id + "-error";
    const type = opts.type || "text";

    let control;
    if (type === "textarea") {
      control = el("textarea", { id, name: opts.name || id, placeholder: opts.placeholder, rows: opts.rows || 4 });
      if (opts.value != null) control.value = opts.value;
    } else if (type === "select") {
      control = el("select", { id, name: opts.name || id });
      (opts.options || []).forEach((o) => control.append(el("option", { value: o.value, text: o.label })));
      if (opts.value != null) control.value = opts.value;
    } else {
      control = el("input", Object.assign({ id, name: opts.name || id, type, placeholder: opts.placeholder }, opts.attrs || {}));
      if (opts.value != null) control.value = opts.value;
    }
    if (opts.required) control.required = true;
    if (opts.autocomplete) control.setAttribute("autocomplete", opts.autocomplete);

    const label = el("label", { className: "field__label", for: id },
      el("span", { text: opts.label }),
      opts.optional ? el("span", { className: "field__optional", text: "Optional" }) : null);
    const hint = opts.hint ? el("p", { className: "field__hint", id: hintId, text: opts.hint }) : null;
    const error = el("p", { className: "field__error", id: errorId, role: "alert" });

    const describedBy = [hint ? hintId : null, errorId].filter(Boolean).join(" ");
    control.setAttribute("aria-describedby", describedBy);

    let controlWrap = control;
    if (opts.prefix) controlWrap = el("div", { className: "field__prefix", "data-prefix": opts.prefix }, control);

    const root = el("div", { className: "field" }, label, hint, controlWrap, error);

    const api = {
      root, control,
      setError(message) {
        error.textContent = message || "";
        if (message) control.setAttribute("aria-invalid", "true");
        else control.removeAttribute("aria-invalid");
      },
      clearError() { api.setError(""); },
      value() { return control.value; },
    };
    control.addEventListener("input", () => { if (error.textContent) api.clearError(); });
    return api;
  }

  // Apply a server {fields: {name: message}} map onto a {name: fieldApi} map.
  // Returns the messages that had no matching field so the caller can show them.
  function applyFieldErrors(fieldMap, fields) {
    const leftovers = [];
    Object.values(fieldMap).forEach((f) => f && f.clearError && f.clearError());
    for (const [name, message] of Object.entries(fields || {})) {
      const base = name.split("[")[0].split(".")[0];
      const target = fieldMap[name] || fieldMap[base];
      if (target && target.setError) target.setError(message);
      else leftovers.push(`${name}: ${message}`);
    }
    const first = Object.values(fieldMap).find((f) => f && f.control && f.control.getAttribute("aria-invalid") === "true");
    if (first) {
      let disclosure = first.control.closest("details");
      while (disclosure) { disclosure.open = true; disclosure = disclosure.parentElement.closest("details"); }
      first.control.focus();
    }
    return leftovers;
  }

  // ----------------------------------------------------------------- 3. card
  // card({title, subtitle, badges: [node], body: node|node[], footer: node|node[],
  //       variant: "leaf"|"sky"|"glass"|"compact"|"hero", interactive, media: {src, alt}})
  function card(opts) {
    opts = opts || {};
    const classes = ["card"];
    [].concat(opts.variant || []).forEach((v) => classes.push("card--" + v));
    if (opts.interactive) classes.push("card--interactive");
    const root = el(opts.tag || "article", { className: classes.join(" ") });

    if (opts.media !== undefined) {
      // media: {src, alt} shows the owner's uploaded photo; without src the
      // area keeps the same 4:3 box and shows a category placeholder
      // ({placeholder: {category, kind, label, action}}). Photos are never
      // fetched from anywhere but the listing's own public_photo_url.
      const ph = (opts.media && opts.media.placeholder) || {};
      const media = el("div", { className: "card__media" + (opts.media && opts.media.src ? "" : " card__media--empty" + (ph.kind === "service" ? " card__media--service" : "")) });
      if (opts.media && opts.media.src) media.append(el("img", { src: opts.media.src, alt: opts.media.alt || "", loading: "lazy" }));
      else media.append(mediaPlaceholder(ph));
      root.append(media);
    }
    if (opts.title || opts.badges) {
      const titleWrap = el("div", {},
        opts.title ? el(opts.titleTag || "h3", { className: "card__title" }, opts.title) : null,
        opts.subtitle ? el("p", { className: "card__subtitle", text: opts.subtitle }) : null);
      const header = el("div", { className: "card__header" }, titleWrap,
        opts.badges ? el("div", { className: "cluster" }, opts.badges) : null);
      root.append(header);
    }
    if (opts.body) root.append(el("div", { className: "card__body" }, opts.body));
    if (opts.footer) root.append(el("div", { className: "card__footer" }, opts.footer));
    return root;
  }

  // --------------------------------------------------------------- 4. dialog
  // dialog({title, body, actions: [button], onClose, dismissLabel})
  // Returns {root, open(opener?), close(returnValue?), setBody(node)}.
  // Uses native <dialog>.showModal() for focus trapping and Escape.
  function dialog(opts) {
    return buildDialog(opts);
  }

  // Category icons for photo placeholders: simple strokes inside a glossy
  // Frutiger Aero bubble. Keys are a fixed whitelist; anything else gets the
  // generic box. Static markup only (never built from server strings).
  const ICON_PATHS = {
    formalwear: '<path d="M9 3h6l-1.5 4L15 18l-3 3-3-3 1.5-11z"/><path d="M9 3l3 4 3-4"/>',
    clothing: '<path d="M8 4l4 2 4-2 4 3-2 4-2-1v11H8V10l-2 1-2-4z"/>',
    electronics: '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19h20"/>',
    textbooks: '<path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z"/><path d="M4 19a2 2 0 0 1 2-2h12"/>',
    calculators: '<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M9 7h6"/><path d="M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h.01M9 18h6"/>',
    furniture: '<path d="M5 11V7a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v4"/><path d="M4 11h16v7H4z"/><path d="M6 18v2M18 18v2"/>',
    appliances: '<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M6 10h12"/><path d="M9 6v2M9 13v3"/>',
    sports: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3v18"/><path d="M5.6 5.6c3.5 3.5 3.5 9.3 0 12.8M18.4 5.6c-3.5 3.5-3.5 9.3 0 12.8"/>',
    tools: '<path d="M14.5 3.5a5 5 0 0 0-5.3 6.8L3 16.5 7.5 21l6.2-6.2a5 5 0 0 0 6.8-5.3l-3 3-3-1-1-3z"/>',
    kitchen: '<path d="M5 9h14v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z"/><path d="M2 11h3M19 11h3M9 9V6M15 9V6"/>',
    tutoring: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/><path d="M22 9v6"/>',
    proofreading: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M9.5 15l2 2 3.5-4"/>',
    "moving help": '<rect x="9" y="4" width="10" height="8" rx="1"/><path d="M3 4h2l3 12h11"/><circle cx="10" cy="19" r="2"/><circle cx="17" cy="19" r="2"/>',
    other: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
  };
  function categoryIcon(category) {
    const key = Object.prototype.hasOwnProperty.call(ICON_PATHS, category) ? category : "other";
    return el("span", { className: "media-icon", "aria-hidden": "true",
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + ICON_PATHS[key] + "</svg>" });
  }

  // mediaPlaceholder({category, kind: "item"|"service", label, action})
  // The friendly "no photo" box: icon, a short label, and an optional owner
  // action (e.g. an Add photo button).
  function mediaPlaceholder(opts) {
    opts = opts || {};
    return el("div", { className: "media-placeholder" },
      categoryIcon(opts.category),
      el("span", { className: "media-label", text: opts.label || (opts.kind === "service" ? "Service" : "No photo yet") }),
      opts.action || null);
  }

  function buildDialog(opts) {
    opts = opts || {};
    const titleId = nextId("dialog-title");
    const body = el("div", { className: "dialog__body" }, opts.body);
    const closeBtn = el("button", { className: "btn btn--ghost btn--sm", type: "button", "aria-label": opts.dismissLabel || "Close dialog", text: "✕" });
    const root = el("dialog", { className: "dialog", "aria-labelledby": titleId },
      el("div", { className: "dialog__header" }, el("h2", { className: "dialog__title", id: titleId, text: opts.title || "" }), closeBtn),
      body,
      opts.actions && opts.actions.length ? el("div", { className: "dialog__footer" }, opts.actions) : null);
    let opener = null;
    const api = {
      root,
      open(fromElement) {
        opener = fromElement || document.activeElement;
        if (!root.isConnected) document.body.append(root);
        if (typeof root.showModal === "function") root.showModal(); else root.setAttribute("open", "");
      },
      close(returnValue) {
        if (root.open) root.close(returnValue);
        else root.removeAttribute("open");
      },
      setBody(node) { clear(body).append(node); },
    };
    closeBtn.addEventListener("click", () => api.close("dismiss"));
    root.addEventListener("click", (event) => { if (event.target === root) api.close("dismiss"); });
    root.addEventListener("close", () => {
      if (opts.onClose) opts.onClose(root.returnValue);
      if (opener && typeof opener.focus === "function") opener.focus();
    });
    return api;
  }

  // ---------------------------------------------------------------- 5. badge
  // badge(text, variant) — variant: undefined (verified green), "warn", "info",
  // "neutral", "error", "fixture", "sim", "sale", "borrow".
  function badge(text, variant) {
    return el("span", { className: "badge" + (variant ? " badge--" + variant : ""), text });
  }

  // A profile badge uses the server's badge text verbatim. Green only when the
  // server says verification_source === "supabase" (same rule as auth.js).
  function profileBadge(profile) {
    if (!profile || !profile.badge) return badge("Unknown identity", "neutral");
    if (profile.verification_source === "supabase") return badge(profile.badge);
    if (profile.verification_source === "sandbox") return badge(profile.badge, "warn");
    return badge(profile.badge, "fixture"); // e.g. "sample": never green, never sandbox-yellow
  }

  function modeBadge(mode) {
    if (mode === "sale") return badge("For sale", "sale");
    if (mode === "borrow") return badge("To borrow", "borrow");
    if (mode === "service") return badge("Service", "service");
    return badge(String(mode), "neutral");
  }

  function fixtureBadge(text) { return badge(text || "Fixture data", "fixture"); }

  const STATUS_LABELS = {
    available: ["Available", "borrow"], reserved: ["Reserved", "info"], sold: ["Sold", "neutral"], withdrawn: ["Withdrawn", "neutral"],
    draft: ["Draft", "neutral"], open: ["Open", "borrow"], fulfilled: ["Fulfilled", "neutral"], cancelled: ["Cancelled", "neutral"], expired: ["Expired", "neutral"],
    negotiating: ["Negotiating", "info"], scheduled: ["Scheduled", "info"], on_loan: ["On loan", "borrow"], return_pending: ["Return pending", "warn"],
    completed: ["Completed", undefined], disputed: ["Disputed", "error"],
  };
  function statusBadge(status) {
    const [label, variant] = STATUS_LABELS[status] || [String(status || "Unknown"), "neutral"];
    return badge(label, variant);
  }

  // Translate application enums only. Unrecognized/user-written values stay intact.
  function conditionLabel(value) {
    const labels = { new: "New", like_new: "Like new", good: "Good", fair: "Fair", worn: "Worn" };
    return Object.hasOwn(labels, value) ? labels[value] : (value ? String(value) : "Unknown");
  }

  // -------------------------------------------------------- 6. offer summary
  // offerSummary(offer, {mode: "sale"|"borrow", listingTitle, meetingSpots: [MeetingSpot],
  //                      depositStatus: {state,label}, participants: {owner, requester}})
  // Renders fee / value / deposit / uncovered as four separate rows for loans,
  // sale price only for sales, revision + acceptances, lower-deposit
  // acknowledgment state, and the simulation label. Never recomputes money.
  function offerSummary(offer, opts) {
    offer = offer || {};
    opts = opts || {};
    const fmt = (c) => (c == null ? "Unknown" : window.api ? api.formatCents(c) : String(c));
    const time = (t) => (t == null ? "Unknown" : window.api ? api.formatTime(t) : String(t));
    const mode = opts.mode || (offer.sale_price_cents != null && offer.agreed_item_value_cents == null ? "sale" : "borrow");
    const spots = new Map((opts.meetingSpots || []).map((s) => [s.id, s]));
    const spotLabel = (id) => (id ? (spots.get(id) ? spots.get(id).label : "Meeting spot " + id) : "Not chosen yet");

    const dl = el("dl");
    const row = (label, valueNode, cls) => {
      dl.append(el("dt", { className: cls || "" , text: label }), el("dd", { className: cls || "" }, valueNode));
    };
    const group = (label) => dl.append(el("div", { className: "offer-summary__group", text: label }));

    group("Money (integer cents, shown in USD)");
    if (mode === "sale") {
      row("Sale price", fmt(offer.sale_price_cents));
    } else {
      row("Rental fee", offer.rental_fee_cents === 0 ? el("span", {}, fmt(0), el("small", { text: "Explicit free loan" })) : fmt(offer.rental_fee_cents));
      row("Agreed item value", el("span", {}, fmt(offer.agreed_item_value_cents), el("small", { text: "Reference for non-return, not a market guarantee" })));
      let depositNode = fmt(offer.deposit_cents);
      if (offer.deposit_cents != null && offer.agreed_item_value_cents) {
        const pct = Math.round((offer.deposit_cents / offer.agreed_item_value_cents) * 100);
        depositNode = el("span", {}, fmt(offer.deposit_cents), el("small", { text: pct + "% of agreed value" }));
      }
      row("Deposit (simulated)", depositNode);
      const uncovered = offer.uncovered_value_cents;
      row("Amount not covered by deposit", el("span", {}, fmt(uncovered),
        uncovered > 0 ? el("small", { text: "Risk stays with the lender; reimbursement is not guaranteed." }) : null),
        uncovered > 0 ? "offer-summary__row--uncovered" : "");
    }

    group("Meeting");
    row("Pickup", el("span", {}, spotLabel(offer.pickup_meeting_spot_id), el("small", { text: time(offer.pickup_at) })));
    if (mode !== "sale") {
      row("Return", el("span", {}, spotLabel(offer.return_meeting_spot_id), el("small", { text: "By " + time(offer.return_deadline) })));
    }

    const snap = offer.condition_snapshot || {};
    group("Condition agreed");
    row("Condition", conditionLabel(snap.condition));
    row("Accessories", (snap.accessories && snap.accessories.length) ? snap.accessories.join(", ") : "None listed");
    row("Known defects", (snap.known_defects && snap.known_defects.length) ? snap.known_defects.join(", ") : "None listed");

    const acks = el("div", { className: "offer-summary__acks" });
    const ackRow = (who, at) => acks.append(el("div", { className: "offer-summary__ack" },
      el("span", { text: who }),
      at ? badge("Accepted " + time(at)) : badge("Not yet accepted", "neutral")));
    const owner = opts.participants && opts.participants.owner;
    const requester = opts.participants && opts.participants.requester;
    ackRow(owner && owner.display_name ? owner.display_name + " (owner)" : "Owner", offer.owner_accepted_at);
    ackRow(requester && requester.display_name ? requester.display_name + " (requester)" : "Requester", offer.requester_accepted_at);
    if (mode !== "sale" && offer.deposit_cents != null && offer.agreed_item_value_cents != null && offer.deposit_cents < offer.agreed_item_value_cents) {
      acks.append(el("div", { className: "offer-summary__ack" },
        el("span", { text: "Lender acknowledgment of lower deposit" }),
        offer.lower_deposit_acknowledged ? badge("Acknowledged") : badge("Required before owner acceptance counts", "warn")));
    }

    const head = el("div", { className: "offer-summary__head" },
      el("h3", { className: "offer-summary__title" }, opts.listingTitle ? "Offer for " + opts.listingTitle : "Current offer"),
      el("div", { className: "cluster" },
        modeBadge(mode),
        badge("Revision " + (offer.version != null ? offer.version : "?"), "info"),
        opts.fixture || (offer.id && String(offer.id).startsWith("fixture-")) ? fixtureBadge() : null));

    const depositStatus = opts.depositStatus;
    const foot = el("div", { className: "offer-summary__foot" },
      el("div", { className: "notice notice--warn", role: "note" },
        el("div", {},
          el("strong", { text: depositStatus && depositStatus.state ? "Deposit status: " + String(depositStatus.state).replace(/_/g, " ") + ". " : "" }),
          (depositStatus && depositStatus.label) || SIMULATION_LABEL)));

    return el("section", { className: "offer-summary", "aria-label": "Offer summary" }, head, dl, acks, foot);
  }

  // ----------------------------------------------------------------- states
  function stateBlock(kind, opts) {
    opts = opts || {};
    const root = el("div", { className: "state" + (kind === "error" ? " state--error" : ""), role: kind === "error" ? "alert" : "status" });
    if (kind === "loading") root.append(el("div", { className: "spinner", "aria-hidden": "true" }));
    else root.append(el("div", { className: "state__icon", "aria-hidden": "true", text: kind === "error" ? "!" : "·" }));
    if (opts.title) root.append(el("h3", { text: opts.title }));
    if (opts.message) root.append(el("p", { text: opts.message }));
    if (opts.action) root.append(opts.action);
    return root;
  }

  const state = {
    loading(container, message) { clear(container).append(stateBlock("loading", { message: message || "Loading…" })); },
    empty(container, opts) { clear(container).append(stateBlock("empty", Object.assign({ title: "Nothing here yet" }, opts || {}))); },
    error(container, err, opts) {
      opts = opts || {};
      const action = opts.retry ? button({ label: opts.retryLabel || "Try again", variant: "primary", size: "sm", onClick: opts.retry }) : opts.action;
      clear(container).append(stateBlock("error", { title: opts.title || "Something went wrong", message: errorMessage(err), action }));
    },
    clear(container) { clear(container); },
    block: stateBlock,
  };

  // Human-readable message for an api.ApiError or anything else. Never leaks
  // raw server JSON; keeps the server's message when it is user-facing.
  function errorMessage(err) {
    if (!err) return "Unknown error.";
    if (window.api && err instanceof api.ApiError) {
      switch (err.code) {
        case "auth_required": return "Sign in with a confirmed UNC email to do this.";
        case "invalid_token": return "Your session is no longer valid. Please sign in again.";
        case "email_not_confirmed": return "Your email is not confirmed yet. Check your inbox for the confirmation link.";
        case "domain_not_allowed": return "Only confirmed @unc.edu emails can post or transact.";
        case "auth_unavailable": return "Sign-in service is unavailable right now. Try again shortly.";
        case "validation_error": return err.message || "Some fields need attention.";
        case "not_found": return "That record no longer exists.";
        case "forbidden": return err.message || "You do not have permission to do that.";
        default: return err.message || `Request failed (${err.status}).`;
      }
    }
    if (err instanceof TypeError) return "Could not reach the server. Check your connection and try again.";
    return err.message || String(err);
  }

  function isAuthError(err) {
    return window.api && err instanceof api.ApiError && (err.status === 401 || err.status === 403);
  }

  // Inline notice: notice(kind, content[, opts]) — kind: info|warn|error|leaf|fixture|sim
  function notice(kind, content, opts) {
    opts = opts || {};
    const role = kind === "error" ? "alert" : (kind === "sim" || kind === "warn" || kind === "fixture") ? "note" : "status";
    const className = "notice notice--" + (kind === "sim" ? "warn" : kind);
    return el("div", { className, role }, el("div", {}, content));
  }

  function simulationNotice(label) { return notice("sim", el("span", {}, el("strong", { text: "Simulated. " }), label || SIMULATION_LABEL)); }


  // Toasts (brief, non-blocking confirmations)
  let toastRegion = null;
  function toast(message, variant, ms) {
    if (!toastRegion) {
      toastRegion = el("div", { className: "toast-region", role: "status", "aria-live": "polite" });
      document.body.append(toastRegion);
    }
    const node = el("div", { className: "toast" + (variant ? " toast--" + variant : ""), text: message });
    toastRegion.append(node);
    setTimeout(() => node.remove(), ms || 4000);
    return node;
  }

  // ------------------------------------------------------------- money utils
  // "15" | "15.50" | "$15.50" | "" -> {cents: 1550} | {cents: null} | {error}
  function dollarsToCents(raw) {
    const text = String(raw == null ? "" : raw).trim().replace(/^\$/, "").replace(/,/g, "");
    if (text === "") return { cents: null };
    if (!/^\d+(\.\d{1,2})?$/.test(text)) return { cents: null, error: "Enter dollars like 45 or 45.50 (no negatives)." };
    return { cents: Math.round(parseFloat(text) * 100) };
  }
  function centsToDollars(cents) {
    if (cents === null || cents === undefined) return "";
    return (cents / 100).toFixed(2).replace(/\.00$/, "");
  }

  // datetime-local value (browser local time) -> ISO UTC with Z, or null.
  function localToIso(value) {
    if (!value) return null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return undefined;
    return d.toISOString();
  }
  // ISO UTC -> value for <input type="datetime-local"> in the browser's zone.
  function isoToLocal(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  // ----------------------------------------------------- circulation scene
  // circulation({label, autoplay, replayButton, size}) -> {root, play(), stop()}
  // A short (2.6 s, plays once) CSS/SVG animation: a glossy bubble carries an
  // item from one person to another and settles with a shimmer. Under
  // prefers-reduced-motion the still end state is shown (CSS handles it).
  // Any element with [data-circulation] is mounted automatically on load, so
  // Person 4 can write <div data-circulation data-autoplay="true"></div> on
  // the "exchange completed" screen, or call components.circulation() and
  // append .root, then .play() when the completion arrives.
  const CIRCULATION_SVG =
    '<svg viewBox="0 0 200 84" xmlns="http://www.w3.org/2000/svg" focusable="false">' +
    '<defs>' +
    '<linearGradient id="circ-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fd6ff"/><stop offset="1" stop-color="#0b6fb8"/></linearGradient>' +
    '<linearGradient id="circ-leaf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9be4a5"/><stop offset="1" stop-color="#2e8b3f"/></linearGradient>' +
    '<radialGradient id="circ-bubble" cx="0.35" cy="0.3" r="0.75"><stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/><stop offset="0.45" stop-color="#ffffff" stop-opacity="0.25"/><stop offset="1" stop-color="#8fd6ff" stop-opacity="0.55"/></radialGradient>' +
    '<linearGradient id="circ-shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff" stop-opacity="0.9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>' +
    '</defs>' +
    '<path class="circ__path" d="M34 46 C 70 10, 130 10, 166 46" fill="none" stroke="#bfe7ff" stroke-width="2" stroke-dasharray="4 5"/>' +
    '<g class="circ__person circ__person--a"><circle cx="30" cy="40" r="9" fill="url(#circ-sky)"/><path d="M12 72 c0 -14 36 -14 36 0 z" fill="url(#circ-sky)"/><circle cx="27" cy="37" r="3" fill="#fff" opacity="0.8"/></g>' +
    '<g class="circ__person circ__person--b"><circle cx="170" cy="40" r="9" fill="url(#circ-leaf)"/><path d="M152 72 c0 -14 36 -14 36 0 z" fill="url(#circ-leaf)"/><circle cx="167" cy="37" r="3" fill="#fff" opacity="0.8"/></g>' +
    '<g class="circ__carrier">' +
    '<circle class="circ__bubble" cx="34" cy="44" r="15" fill="url(#circ-bubble)" stroke="#fff" stroke-opacity="0.9" stroke-width="1.5"/>' +
    '<g class="circ__item"><rect x="27" y="38" width="14" height="12" rx="2.5" fill="url(#circ-leaf)" stroke="#1d5f2a" stroke-width="1"/><path d="M27 43 h14" stroke="#e9f9ea" stroke-width="1.5"/><path d="M34 38 v12" stroke="#e9f9ea" stroke-width="1.5"/></g>' +
    '<circle class="circ__ring" cx="34" cy="44" r="15" fill="none" stroke="#fff" stroke-width="2"/>' +
    '</g>' +
    '<rect class="circ__shine" x="148" y="24" width="18" height="52" fill="url(#circ-shine)" transform="skewX(-18)"/>' +
    '<g class="circ__sparkle"><path d="M184 18 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 z" fill="#fff"/><path d="M14 20 l1.5 3.5 3.5 1.5 -3.5 1.5 -1.5 3.5 -1.5 -3.5 -3.5 -1.5 3.5 -1.5 z" fill="#fff"/></g>' +
    '</svg>';

  function circulation(opts) {
    opts = opts || {};
    const label = opts.label || "An item passing from one person to another";
    const root = el("div", { className: "circ" + (opts.size === "sm" ? " circ--sm" : opts.size === "lg" ? " circ--lg" : ""), role: "img", "aria-label": label });
    // Static, trusted markup; gradient ids are made unique per instance so
    // several scenes can share one page without duplicate ids.
    const prefix = nextId("circ");
    root.innerHTML = CIRCULATION_SVG.replace(/circ-(sky|leaf|bubble|shine)/g, prefix + "-$1");
    const api = {
      root,
      play() {
        root.classList.remove("circ--play");
        void root.offsetWidth; // restart the CSS animations
        root.classList.add("circ--play");
      },
      stop() { root.classList.remove("circ--play"); },
    };
    if (opts.replayButton) {
      const btn = el("button", { className: "btn btn--ghost btn--sm circ__replay", type: "button", text: opts.replayLabel || "Replay" , onClick: api.play });
      const wrap = el("div", { className: "circ-wrap" }, root, btn);
      api.wrap = wrap;
    }
    // Deferred so the caller can attach the element first. setTimeout rather
    // than requestAnimationFrame: rAF never fires in hidden/non-painting tabs.
    if (opts.autoplay !== false) setTimeout(api.play, 0);
    return api;
  }

  function mountCirculations() {
    document.querySelectorAll("[data-circulation]").forEach((host) => {
      if (host.dataset.mounted) return;
      host.dataset.mounted = "true";
      const c = circulation({
        label: host.getAttribute("aria-label") || host.dataset.label,
        autoplay: host.dataset.autoplay !== "false",
        replayButton: host.dataset.replay === "true",
        size: host.dataset.size,
      });
      host.removeAttribute("aria-label");
      host.append(c.wrap || c.root);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountCirculations);
  else mountCirculations();

  // Input modality for focus styling: headings that get programmatic focus
  // (page load, "Update results") show a ring only after keyboard use.
  // Pointer users never see a box on a heading they did not click.
  document.addEventListener("keydown", (e) => { if (!e.metaKey && !e.ctrlKey && !e.altKey) document.documentElement.dataset.input = "keyboard"; }, true);
  document.addEventListener("pointerdown", () => { document.documentElement.dataset.input = "pointer"; }, true);

  // Circulation mark for completed exchanges (static under reduced motion via CSS).
  function circulationMark(spin) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true"); svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "2.2"); svg.setAttribute("stroke-linecap", "round"); svg.setAttribute("stroke-linejoin", "round");
    svg.innerHTML = '<path d="M4 12a8 8 0 0 1 13.6-5.7"/><path d="M17 3v4h-4"/><path d="M20 12a8 8 0 0 1-13.6 5.7"/><path d="M7 21v-4h4"/>';
    return el("span", { className: "circulate" + (spin ? " circulate--spin" : ""), title: "Item circulated" }, svg);
  }

  window.components = {
    SIMULATION_LABEL,
    el, clear, nextId,
    button, setBusy,
    field, applyFieldErrors,
    card,
    dialog,
    badge, profileBadge, modeBadge, fixtureBadge, statusBadge, conditionLabel,
    offerSummary,
    state, notice, simulationNotice, toast,
    errorMessage, isAuthError,
    categoryIcon, mediaPlaceholder,
    dollarsToCents, centsToDollars, localToIso, isoToLocal,
    circulation, mountCirculations, circulationMark,
  };
})();
