/**
 * Interní stránka podkladů: CAPTCHA (jako form-lp), podmíněné pole formuláře, doplňkové služby, FormSubmit.
 */
(function () {
  var form = document.getElementById("briefKlientForm");
  var statusEl = document.getElementById("briefKlientFormStatus");
  var detailRow = document.getElementById("briefFormularDetailRow");
  var detailTa = document.getElementById("briefFormularDetail");
  var REDIRECT_URL = "dekujeme.html";
  var STORAGE_PREFIX = "briefPodklady_";

  var DOPLNKY_LABELS = {
    qr_kod: "QR kód na web (zdarma)",
    nfc_karta: "NFC karta (100–200 Kč)",
    nfc_stojanek: "NFC stojánek (250 Kč)",
    vizitky: "Klasické vizitky",
    reklamni_predmety: "Reklamní předměty",
    jine_it: "Jiné IT / software (po domluvě)",
  };

  if (!form) return;

  var lockHours = parseInt(form.getAttribute("data-captcha-lock-hours"), 10) || 4;
  var maxAttempts = 3;
  var currentCaptchaAnswer = null;
  var captchaOptions = [];

  function pickNewCaptcha(avoidAnswer, shouldFocus) {
    if (captchaOptions.length === 0) return;
    var pool = captchaOptions;
    if (avoidAnswer != null && captchaOptions.length > 1) {
      pool = captchaOptions.filter(function (o) {
        return String(o.answer) !== String(avoidAnswer);
      });
    }
    if (pool.length === 0) pool = captchaOptions;
    var picked = pool[Math.floor(Math.random() * pool.length)];
    currentCaptchaAnswer = String(picked.answer);
    var img = form.querySelector("#briefCaptchaImg");
    if (img && picked.img) img.src = picked.img;
    var captchaInput = form.querySelector("#brief-captcha");
    if (captchaInput) {
      captchaInput.value = "";
      if (shouldFocus !== false) captchaInput.focus();
    }
  }

  (function initCaptcha() {
    var optionsJson = form.getAttribute("data-captcha-options");
    if (optionsJson) {
      try {
        var options = JSON.parse(optionsJson);
        if (options && options.length > 0) {
          captchaOptions = options;
          pickNewCaptcha(null, false);
        }
      } catch (e) {}
    }
  })();
  var hasCaptcha = currentCaptchaAnswer !== null;

  function setStatus(text, ok) {
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.style.color = ok ? "var(--navy)" : "tomato";
  }

  function trim(s) {
    return (s || "").toString().trim();
  }

  function getStored(key) {
    try {
      var v = localStorage.getItem(STORAGE_PREFIX + key);
      return v === null ? null : JSON.parse(v);
    } catch (e) {
      return null;
    }
  }
  function setStored(key, value) {
    try {
      localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
    } catch (e) {}
  }

  function isLocked() {
    var until = getStored("lockedUntil");
    if (!until) return false;
    if (Date.now() < until) return true;
    setStored("lockedUntil", null);
    setStored("attempts", 0);
    return false;
  }

  function lockForm() {
    form.classList.add("is-locked");
    var msg =
      "Kvůli opakovanému špatnému zadání je formulář dočasně uzavřen. Zkuste to prosím za " +
      lockHours +
      " hodin, nebo napište na info@ulovklienty.cz.";
    setStatus(msg);
  }

  if (hasCaptcha) {
    if (isLocked()) {
      form.classList.add("is-locked");
      setStatus(
        "Formulář je dočasně uzavřen (ochrana proti robotům). Zkuste to za " +
          lockHours +
          " h, nebo napište na info@ulovklienty.cz."
      );
    }
    var refreshBtn = form.querySelector("#briefCaptchaRefresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        pickNewCaptcha(currentCaptchaAnswer);
      });
    }
  }

  function syncFormularDetail() {
    var checked = form.querySelector('input[name="formular_chci"]:checked');
    var show = checked && checked.value === "ano";
    if (detailRow) {
      detailRow.hidden = !show;
      detailRow.setAttribute("aria-hidden", show ? "false" : "true");
    }
    if (!show && detailTa) detailTa.value = "";
  }

  form.querySelectorAll('input[name="formular_chci"]').forEach(function (r) {
    r.addEventListener("change", syncFormularDetail);
  });
  syncFormularDetail();

  var doplnkyNone = document.getElementById("briefDoplnkyNone");
  var doplnkyOpts = form.querySelectorAll(".brief-doplnky-opt");

  function setDoplnkyOthersDisabled(disabled) {
    doplnkyOpts.forEach(function (cb) {
      cb.disabled = !!disabled;
    });
  }

  function syncDoplnkyNone() {
    if (!doplnkyNone) return;
    if (doplnkyNone.checked) {
      doplnkyOpts.forEach(function (cb) {
        cb.checked = false;
      });
      setDoplnkyOthersDisabled(true);
    } else {
      setDoplnkyOthersDisabled(false);
    }
  }

  function onDoplnkyOptChange() {
    if (!doplnkyNone) return;
    var any = false;
    doplnkyOpts.forEach(function (cb) {
      if (cb.checked) any = true;
    });
    if (any) {
      doplnkyNone.checked = false;
      setDoplnkyOthersDisabled(false);
    }
  }

  if (doplnkyNone) {
    doplnkyNone.addEventListener("change", syncDoplnkyNone);
  }
  doplnkyOpts.forEach(function (cb) {
    cb.addEventListener("change", onDoplnkyOptChange);
  });
  syncDoplnkyNone();

  function validateEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trim(v));
  }

  function collectDoplnkyText() {
    if (doplnkyNone && doplnkyNone.checked) {
      return "Zatím nemám zájem";
    }
    var parts = [];
    doplnkyOpts.forEach(function (cb) {
      if (cb.checked) {
        parts.push(DOPLNKY_LABELS[cb.value] || cb.value);
      }
    });
    return parts.join("; ");
  }

  function doplnkyValid() {
    if (doplnkyNone && doplnkyNone.checked) return true;
    for (var i = 0; i < doplnkyOpts.length; i++) {
      if (doplnkyOpts[i].checked) return true;
    }
    return false;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    setStatus("");

    if (hasCaptcha && form.classList.contains("is-locked")) return;

    var hp = form.querySelector('input[name="_gotcha"]');
    if (hp && trim(hp.value) !== "") return;

    var prijmeni = trim(form.querySelector('[name="prijmeni"]').value);
    var email = trim(form.querySelector('[name="email"]').value);

    if (prijmeni.length < 2) {
      setStatus("Vyplňte prosím příjmení.");
      form.querySelector('[name="prijmeni"]').focus();
      return;
    }
    if (!validateEmail(email)) {
      setStatus("Zadejte platný e-mail.");
      form.querySelector('[name="email"]').focus();
      return;
    }

    var formularChci = (form.querySelector('input[name="formular_chci"]:checked') || {}).value || "";
    if (!formularChci) {
      setStatus("Vyberte prosím, zda chcete na webu formulář (Ano / Ne).");
      return;
    }

    var fotky = (form.querySelector('input[name="fotky_zpusob"]:checked') || {}).value || "";
    if (!fotky) {
      setStatus("Vyberte prosím způsob dodání fotek.");
      return;
    }

    if (!doplnkyValid()) {
      setStatus("Vyberte prosím doplňkové služby, nebo zaškrtněte „Zatím nemám zájem“.");
      if (doplnkyNone) doplnkyNone.focus();
      return;
    }

    if (hasCaptcha) {
      var captchaInput = form.querySelector("#brief-captcha");
      var userAnswer = captchaInput ? trim(captchaInput.value) : "";
      if (userAnswer !== currentCaptchaAnswer) {
        var attempts = (getStored("attempts") || 0) + 1;
        setStored("attempts", attempts);
        if (attempts >= maxAttempts) {
          setStored("lockedUntil", Date.now() + lockHours * 60 * 60 * 1000);
          lockForm();
          return;
        }
        pickNewCaptcha(currentCaptchaAnswer);
        var left = maxAttempts - attempts;
        setStatus(
          "Špatné číslo. Zbývají vám " +
            left +
            " " +
            (left === 1 ? "pokus" : left < 5 ? "pokusy" : "pokusů") +
            "."
        );
        return;
      }
      setStored("attempts", 0);
    }

    setStatus("Odesílám…", true);

    var host = window.location.hostname;
    var isLocal = host === "localhost" || host === "127.0.0.1";
    var apiBase = isLocal
      ? "http://" + host + ":8000/api"
      : "https://api.ulovklienty.cz/api";

    var lines = [
      "=== PODKLADY PRO WEB ===",
      "",
      "Barvy:",
      trim(form.querySelector('[name="barvy"]').value) || "—",
      "",
      "Logo:",
      trim(form.querySelector('[name="logo"]').value) || "—",
      "",
      "O nás:",
      trim(form.querySelector('[name="o_nas"]').value) || "—",
      "",
      "Produkty a služby:",
      trim(form.querySelector('[name="produkty_sluzby"]').value) || "—",
      "",
      "Formulář na webu: " + (formularChci === "ano" ? "Ano, chci" : "Ne, nechci"),
      "Jaký formulář: " +
        (formularChci === "ano"
          ? trim(form.querySelector('[name="formular_jaky"]').value) || "—"
          : "—"),
      "",
      "Sociální sítě:",
      trim(form.querySelector('[name="socialni_site"]').value) || "—",
      "",
      "Online katalogy:",
      trim(form.querySelector('[name="online_katalogy"]').value) || "—",
      "",
      "Doména: " + (trim(form.querySelector('[name="domena"]').value) || "—"),
      "Fotky: " + fotky,
      "",
      "Vlastní přání:",
      trim((form.querySelector('[name="vlastni_prani"]') || {}).value || "") || "—",
      "",
      "Doplňkové služby: " + collectDoplnkyText(),
    ];

    var payload = {
      jmeno: prijmeni,
      email: email,
      telefon: "",
      salon_nazev: trim(form.querySelector('[name="domena"]').value) || "",
      zprava: lines.join("\n"),
      souhlas: true,
    };

    fetch(apiBase + "/poptavka/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) throw new Error(data.detail || "fail");
          return data;
        });
      })
      .then(function () {
        window.location.href = REDIRECT_URL;
      })
      .catch(function () {
        setStatus("Odeslání se nezdařilo. Napište prosím na info@ulovklienty.cz nebo zavolejte +420 797 756 746.");
      });
  });
})();
