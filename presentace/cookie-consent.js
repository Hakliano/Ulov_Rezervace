/**
 * ULOV KLIENTY — vlastní Cookie Consent (bez Cookiebot / OneTrust apod.)
 *
 * Konfigurace před načtením:
 *   window.ULOV_COOKIE_CONSENT = { gaMeasurementId: "G-XXXXXXXX" };
 *
 * Veřejné API:
 *   UlovCookieConsent.openSettings()
 *   UlovCookieConsent.hasAnalytics()
 *   UlovCookieConsent.reset()  // test / debug
 */
(function (global) {
  "use strict";

  var COOKIE_CONSENT = "cookie_consent";
  var COOKIE_ANALYTICS = "analytics";
  var MAX_AGE = 365 * 24 * 60 * 60; // 12 měsíců
  var PATH = "/";

  var defaults = {
    gaMeasurementId: "",
    privacyUrl: "gdpr.html",
    categories: [
      {
        id: "necessary",
        label: "Nezbytné cookies",
        description:
          "Tyto cookies jsou nezbytné pro správné fungování webových stránek a nelze je vypnout.",
        required: true,
        available: true,
      },
      {
        id: "analytics",
        label: "Analytické cookies",
        description:
          "Pomáhají nám anonymně měřit návštěvnost webu prostřednictvím služby Google Analytics 4. Díky tomu můžeme zlepšovat obsah a funkčnost webových stránek.",
        required: false,
        available: true,
        defaultEnabled: false,
      },
      {
        id: "functional",
        label: "Funkční cookies",
        description: "Momentálně nepoužíváme.",
        required: false,
        available: false,
        defaultEnabled: false,
      },
      {
        id: "marketing",
        label: "Marketingové cookies",
        description: "Momentálně nepoužíváme.",
        required: false,
        available: false,
        defaultEnabled: false,
      },
    ],
    /**
     * Handlery po udělení kategorie — rozšiřitelné bez změny jádra.
     * Klíč = category.id
     */
    loaders: {},
  };

  var cfg = mergeConfig(defaults, global.ULOV_COOKIE_CONSENT || {});

  // Vestavěný loader pro GA4
  if (!cfg.loaders.analytics) {
    cfg.loaders.analytics = function () {
      loadGoogleAnalytics(cfg.gaMeasurementId);
    };
  }

  var state = {
    bannerEl: null,
    modalEl: null,
    gaLoaded: false,
  };

  function mergeConfig(base, over) {
    var out = {};
    var k;
    for (k in base) {
      if (Object.prototype.hasOwnProperty.call(base, k)) out[k] = base[k];
    }
    for (k in over) {
      if (Object.prototype.hasOwnProperty.call(over, k)) {
        if (k === "categories" && Array.isArray(over.categories)) {
          out.categories = over.categories;
        } else if (k === "loaders" && over.loaders && typeof over.loaders === "object") {
          out.loaders = Object.assign({}, base.loaders || {}, over.loaders);
        } else {
          out[k] = over[k];
        }
      }
    }
    return out;
  }

  function getCookie(name) {
    var parts = ("; " + document.cookie).split("; " + name + "=");
    if (parts.length === 2) {
      return decodeURIComponent(parts.pop().split(";").shift());
    }
    return null;
  }

  function setCookie(name, value, maxAge) {
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie =
      name +
      "=" +
      encodeURIComponent(value) +
      "; Path=" +
      PATH +
      "; Max-Age=" +
      maxAge +
      "; SameSite=Lax" +
      secure;
  }

  function readConsent() {
    var consent = getCookie(COOKIE_CONSENT);
    if (!consent) return null;
    var analytics = getCookie(COOKIE_ANALYTICS);
    return {
      consent: consent,
      analytics: analytics === "true" || consent === "all",
    };
  }

  function writeConsent(consent, analyticsOn) {
    setCookie(COOKIE_CONSENT, consent, MAX_AGE);
    setCookie(COOKIE_ANALYTICS, analyticsOn ? "true" : "false", MAX_AGE);
  }

  function hasAnalytics() {
    var c = readConsent();
    if (!c) return false;
    return c.consent === "all" || c.analytics === true;
  }

  function loadGoogleAnalytics(measurementId) {
    if (state.gaLoaded) return;
    if (!measurementId || !/^G-[A-Z0-9]+$/i.test(measurementId)) return;
    if (!hasAnalytics()) return;

    global.dataLayer = global.dataLayer || [];
    function gtag() {
      global.dataLayer.push(arguments);
    }
    global.gtag = gtag;
    gtag("js", new Date());
    gtag("config", measurementId, { anonymize_ip: true });

    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
    document.head.appendChild(s);
    state.gaLoaded = true;
  }

  function runLoaders(enabledIds) {
    cfg.categories.forEach(function (cat) {
      if (!cat.available || cat.required) return;
      if (enabledIds.indexOf(cat.id) === -1) return;
      var fn = cfg.loaders[cat.id];
      if (typeof fn === "function") {
        try {
          fn();
        } catch (e) {
          /* ignore loader errors */
        }
      }
    });
  }

  function applyConsent(consent, analyticsOn) {
    var wasAnalytics = hasAnalytics() && state.gaLoaded;
    writeConsent(consent, analyticsOn);
    hideBanner();
    closeModal();
    if (analyticsOn) {
      runLoaders(["analytics"]);
    } else if (wasAnalytics) {
      // Odvolání analytiky — obnovit stránku bez GA skriptů
      location.reload();
    }
  }

  function acceptAll() {
    applyConsent("all", true);
  }

  function acceptNecessary() {
    applyConsent("necessary", false);
  }

  function saveCustomFromModal() {
    var analyticsToggle = state.modalEl && state.modalEl.querySelector("#ulov-cc-analytics");
    var analyticsOn = !!(analyticsToggle && analyticsToggle.checked);
    applyConsent("custom", analyticsOn);
  }

  function el(tag, className, attrs) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "text") node.textContent = attrs[key];
        else if (key === "html") node.innerHTML = attrs[key];
        else node.setAttribute(key, attrs[key]);
      });
    }
    return node;
  }

  function buildBanner() {
    var wrap = el("div", "ulov-cc-banner", {
      role: "dialog",
      "aria-modal": "false",
      "aria-labelledby": "ulov-cc-banner-title",
    });

    var inner = el("div", "ulov-cc-banner__inner");
    var copy = el("div", "ulov-cc-banner__copy");
    copy.appendChild(el("h2", "ulov-cc-banner__title", { id: "ulov-cc-banner-title", text: "Respektujeme vaše soukromí" }));
    copy.appendChild(
      el("p", "ulov-cc-banner__text", {
        text:
          "Používáme nezbytné cookies pro správné fungování webu. S vaším souhlasem používáme také analytické cookies (Google Analytics), které nám pomáhají zlepšovat naše služby a obsah webu. Nepoužíváme marketingové cookies ani neprodáváme vaše údaje třetím stranám.",
      })
    );
    if (cfg.privacyUrl) {
      var more = el("p", "ulov-cc-banner__more");
      var a = el("a", null, { href: cfg.privacyUrl, text: "Zásady ochrany osobních údajů" });
      more.appendChild(a);
      copy.appendChild(more);
    }

    var actions = el("div", "ulov-cc-banner__actions");
    var btnAll = el("button", "ulov-cc-btn ulov-cc-btn--primary", { type: "button", text: "Přijmout vše" });
    var btnNec = el("button", "ulov-cc-btn ulov-cc-btn--secondary", { type: "button", text: "Pouze nezbytné" });
    var btnSet = el("button", "ulov-cc-btn ulov-cc-btn--ghost", { type: "button", text: "Nastavení" });
    btnAll.addEventListener("click", acceptAll);
    btnNec.addEventListener("click", acceptNecessary);
    btnSet.addEventListener("click", openSettings);
    actions.appendChild(btnAll);
    actions.appendChild(btnNec);
    actions.appendChild(btnSet);

    inner.appendChild(copy);
    inner.appendChild(actions);
    wrap.appendChild(inner);
    document.body.appendChild(wrap);
    state.bannerEl = wrap;
  }

  function hideBanner() {
    if (state.bannerEl) {
      state.bannerEl.classList.add("ulov-cc-banner--hidden");
      state.bannerEl.setAttribute("aria-hidden", "true");
    }
  }

  function showBanner() {
    if (!state.bannerEl) buildBanner();
    state.bannerEl.classList.remove("ulov-cc-banner--hidden");
    state.bannerEl.removeAttribute("aria-hidden");
  }

  function buildModal() {
    var overlay = el("div", "ulov-cc-modal", {
      role: "dialog",
      "aria-modal": "true",
      "aria-labelledby": "ulov-cc-modal-title",
      hidden: "hidden",
    });

    var panel = el("div", "ulov-cc-modal__panel");
    panel.appendChild(el("h2", "ulov-cc-modal__title", { id: "ulov-cc-modal-title", text: "Nastavení cookies" }));
    panel.appendChild(
      el("p", "ulov-cc-modal__desc", {
        text: "Sami si můžete zvolit, které typy cookies nám dovolíte používat.",
      })
    );

    var list = el("div", "ulov-cc-cats");
    var consent = readConsent();

    cfg.categories.forEach(function (cat) {
      var row = el("div", "ulov-cc-cat" + (!cat.available && !cat.required ? " ulov-cc-cat--disabled" : ""));
      var head = el("div", "ulov-cc-cat__head");
      head.appendChild(el("h3", "ulov-cc-cat__label", { text: cat.label }));

      var toggleWrap = el("label", "ulov-cc-switch");
      var input = el("input", null, {
        type: "checkbox",
        id: "ulov-cc-" + cat.id,
      });

      if (cat.required || !cat.available) {
        input.disabled = true;
      }
      if (cat.required) {
        input.checked = true;
      } else if (cat.available) {
        if (consent) {
          input.checked = cat.id === "analytics" ? !!consent.analytics : !!cat.defaultEnabled;
        } else {
          input.checked = !!cat.defaultEnabled;
        }
      } else {
        input.checked = false;
      }

      toggleWrap.appendChild(input);
      toggleWrap.appendChild(el("span", "ulov-cc-switch__ui"));
      head.appendChild(toggleWrap);
      row.appendChild(head);
      row.appendChild(el("p", "ulov-cc-cat__text", { text: cat.description }));
      list.appendChild(row);
    });

    panel.appendChild(list);

    var actions = el("div", "ulov-cc-modal__actions");
    var btnSave = el("button", "ulov-cc-btn ulov-cc-btn--primary", { type: "button", text: "Uložit nastavení" });
    var btnCancel = el("button", "ulov-cc-btn ulov-cc-btn--secondary", { type: "button", text: "Zrušit" });
    btnSave.addEventListener("click", saveCustomFromModal);
    btnCancel.addEventListener("click", closeModal);
    actions.appendChild(btnSave);
    actions.appendChild(btnCancel);
    panel.appendChild(actions);

    overlay.appendChild(panel);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) closeModal();
    });
    document.body.appendChild(overlay);
    state.modalEl = overlay;
  }

  function syncModalToggles() {
    if (!state.modalEl) return;
    var consent = readConsent();
    var analytics = state.modalEl.querySelector("#ulov-cc-analytics");
    if (analytics && !analytics.disabled) {
      analytics.checked = consent ? !!consent.analytics : false;
    }
  }

  function openSettings() {
    if (!state.modalEl) buildModal();
    else syncModalToggles();
    state.modalEl.removeAttribute("hidden");
    document.body.classList.add("ulov-cc-lock");
    var first = state.modalEl.querySelector("button, input:not([disabled])");
    if (first) first.focus();
  }

  function closeModal() {
    if (!state.modalEl) return;
    state.modalEl.setAttribute("hidden", "hidden");
    document.body.classList.remove("ulov-cc-lock");
  }

  function bindFooterLinks() {
    document.querySelectorAll("[data-ulov-cookie-settings], a[href='#cookies']").forEach(function (node) {
      node.addEventListener("click", function (ev) {
        ev.preventDefault();
        openSettings();
      });
    });
  }

  function init() {
    var consent = readConsent();
    if (!consent) {
      showBanner();
    } else if (consent.analytics) {
      runLoaders(["analytics"]);
    }
    bindFooterLinks();
  }

  var api = {
    openSettings: openSettings,
    closeModal: closeModal,
    hasAnalytics: hasAnalytics,
    acceptAll: acceptAll,
    acceptNecessary: acceptNecessary,
    getConsent: readConsent,
    reset: function () {
      setCookie(COOKIE_CONSENT, "", 0);
      setCookie(COOKIE_ANALYTICS, "", 0);
      state.gaLoaded = false;
      showBanner();
    },
    config: cfg,
  };

  global.UlovCookieConsent = api;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
