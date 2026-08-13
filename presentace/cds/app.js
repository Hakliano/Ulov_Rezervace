(function () {
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  const isStaging = host.includes("staging");
  const API_BASE = isLocal
    ? `http://${host}:8000/api`
    : isStaging
      ? "https://api-staging.ulovklienty.cz/api"
      : "https://api.ulovklienty.cz/api";
  const POPTAVKA_SOURCE = "Custom Digital Services (CDS)";
  const CONTACT_EMAIL = "info@ulovklienty.cz";

  /* ── Zlaté 0/1 proletávající při scrollu ── */
  (function initBinaryField() {
    const canvas = document.getElementById("cdsBinary");
    if (!canvas || !canvas.getContext) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      canvas.remove();
      return;
    }

    const ctx = canvas.getContext("2d", { alpha: true });
    const GOLD = [
      "rgba(232, 210, 138, 0.95)",
      "rgba(212, 183, 106, 0.85)",
      "rgba(201, 166, 74, 0.7)",
      "rgba(168, 135, 42, 0.55)",
    ];
    const BITS = ["0", "1"];
    let particles = [];
    let w = 0;
    let h = 0;
    let dpr = 1;
    let lastScrollY = window.scrollY || 0;
    let scrollBoost = 0;
    let raf = 0;
    let lastTs = 0;

    function countForViewport() {
      const area = w * h;
      const base = Math.round(area / 14000);
      return Math.max(28, Math.min(90, base));
    }

    function spawn(partial) {
      const depth = Math.random();
      return {
        x: Math.random() * w,
        y: partial ? Math.random() * h : Math.random() < 0.5 ? -40 : h + 40,
        z: depth,
        vx: (Math.random() - 0.5) * (0.06 + depth * 0.22),
        vy: (0.04 + depth * 0.35) * (Math.random() < 0.5 ? 1 : -1),
        bit: BITS[(Math.random() * 2) | 0],
        size: 10 + depth * 22,
        color: GOLD[(Math.random() * GOLD.length) | 0],
        rot: (Math.random() - 0.5) * 0.4,
        spin: (Math.random() - 0.5) * 0.004,
      };
    }

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const target = countForViewport();
      if (particles.length === 0) {
        particles = Array.from({ length: target }, () => spawn(true));
      } else if (particles.length < target) {
        while (particles.length < target) particles.push(spawn(true));
      } else if (particles.length > target) {
        particles.length = target;
      }
    }

    function onScroll() {
      const y = window.scrollY || 0;
      const dy = y - lastScrollY;
      lastScrollY = y;
      scrollBoost += dy * 0.018;
      scrollBoost = Math.max(-2.5, Math.min(2.5, scrollBoost));
    }

    function wrap(p) {
      const m = 48;
      if (p.x < -m) p.x = w + m;
      if (p.x > w + m) p.x = -m;
      if (p.y < -m) p.y = h + m;
      if (p.y > h + m) p.y = -m;
    }

    function tick(ts) {
      raf = requestAnimationFrame(tick);
      const dt = lastTs ? Math.min(32, ts - lastTs) : 16;
      lastTs = ts;
      const t = dt / 16.67;

      scrollBoost *= Math.pow(0.94, t);

      ctx.clearRect(0, 0, w, h);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = '600 16px "JetBrains Mono", ui-monospace, monospace';

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const speed = (0.12 + p.z * 0.45) * t;
        p.x += p.vx * speed * 10 + scrollBoost * p.z * 0.7;
        p.y += p.vy * speed * 6 + scrollBoost * (0.35 + p.z) * 0.9;
        p.rot += p.spin * t * 5;
        wrap(p);

        if (Math.random() < 0.0015 * t) {
          p.bit = BITS[(Math.random() * 2) | 0];
        }

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.globalAlpha = 0.25 + p.z * 0.7;
        ctx.fillStyle = p.color;
        ctx.shadowColor = "rgba(201, 166, 74, 0.55)";
        ctx.shadowBlur = 6 + p.z * 10;
        ctx.font = `600 ${p.size}px "JetBrains Mono", ui-monospace, monospace`;
        ctx.fillText(p.bit, 0, 0);
        ctx.restore();
      }
    }

    resize();
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    raf = requestAnimationFrame(tick);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        lastTs = 0;
      } else {
        lastScrollY = window.scrollY || 0;
        raf = requestAnimationFrame(tick);
      }
    });
  })();

  const form = document.getElementById("poptavka-form");
  const msg = document.getElementById("form-msg");
  const STORAGE_PREFIX = "cdsCaptcha_";
  const maxAttempts = 3;
  let currentCaptchaAnswer = null;
  let captchaOptions = [];

  function getStored(key) {
    try {
      const v = localStorage.getItem(STORAGE_PREFIX + key);
      return v === null ? null : JSON.parse(v);
    } catch {
      return null;
    }
  }

  function setStored(key, value) {
    try {
      localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  }

  function pickNewCaptcha(avoidAnswer, shouldFocus) {
    if (!captchaOptions.length) return;
    let pool = captchaOptions;
    if (avoidAnswer != null && captchaOptions.length > 1) {
      pool = captchaOptions.filter((o) => String(o.answer) !== String(avoidAnswer));
    }
    if (!pool.length) pool = captchaOptions;
    const picked = pool[Math.floor(Math.random() * pool.length)];
    currentCaptchaAnswer = String(picked.answer);
    const img = document.getElementById("pCaptchaImg");
    if (img && picked.img) img.src = picked.img;
    const captchaInput = document.getElementById("p-captcha");
    if (captchaInput) {
      captchaInput.value = "";
      if (shouldFocus !== false) captchaInput.focus();
    }
  }

  function initPoptavkaCaptcha() {
    if (!form) return;
    const optionsJson = form.getAttribute("data-captcha-options");
    if (!optionsJson) return;
    try {
      const options = JSON.parse(optionsJson);
      if (options?.length) {
        captchaOptions = options;
        pickNewCaptcha(null, false);
      }
    } catch {
      /* ignore */
    }

    const lockHours = parseInt(form.getAttribute("data-captcha-lock-hours"), 10) || 4;
    const until = getStored("lockedUntil");
    if (until && Date.now() < until) {
      form.classList.add("is-locked");
      if (msg) {
        msg.textContent = `Formulář je dočasně uzavřen (ochrana proti robotům). Zkuste to za ${lockHours} h, nebo napište na ${CONTACT_EMAIL}.`;
        msg.className = "form-msg error";
      }
    } else if (until) {
      setStored("lockedUntil", null);
      setStored("attempts", 0);
    }

    document.getElementById("pCaptchaRefresh")?.addEventListener("click", () => {
      pickNewCaptcha(currentCaptchaAnswer);
    });
  }

  initPoptavkaCaptcha();

  document.querySelectorAll("a[data-package]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const select = document.getElementById("p-balicek");
      const value = btn.dataset.package;
      if (select && value) {
        const option = Array.from(select.options).find((o) => o.value === value);
        if (option) select.value = value;
      }
    });
  });

  const mods = document.querySelectorAll(".cds-mod");
  if (mods.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.style.transitionDelay = `${Math.min(entry.target.dataset.i || 0, 8) * 40}ms`;
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    mods.forEach((el, i) => {
      el.dataset.i = String(i % 9);
      el.style.opacity = "0";
      el.style.transform = "translateY(10px)";
      el.style.transition = "opacity 0.45s ease, transform 0.45s ease, background 0.2s ease, padding-left 0.2s ease";
      io.observe(el);
    });
    const style = document.createElement("style");
    style.textContent = ".cds-mod.is-in{opacity:1!important;transform:none!important}";
    document.head.appendChild(style);
  }

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!msg) return;
    if (form.classList.contains("is-locked")) return;

    const hp = form.querySelector('input[name="_gotcha"]');
    if (hp && hp.value.trim() !== "") return;

    msg.textContent = "";
    msg.className = "form-msg";

    const jmeno = document.getElementById("p-jmeno").value.trim();
    const email = document.getElementById("p-email").value.trim();
    if (jmeno.length < 2) {
      msg.textContent = "Vyplňte prosím jméno.";
      msg.className = "form-msg error";
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      msg.textContent = "Zadejte platný e-mail.";
      msg.className = "form-msg error";
      return;
    }
    if (!document.getElementById("p-souhlas").checked) {
      msg.textContent = "Potvrďte prosím souhlas se zpracováním údajů.";
      msg.className = "form-msg error";
      return;
    }

    if (currentCaptchaAnswer !== null) {
      const userAnswer = (document.getElementById("p-captcha")?.value || "").trim();
      if (userAnswer !== currentCaptchaAnswer) {
        const lockHours = parseInt(form.getAttribute("data-captcha-lock-hours"), 10) || 4;
        const attempts = (getStored("attempts") || 0) + 1;
        setStored("attempts", attempts);
        if (attempts >= maxAttempts) {
          setStored("lockedUntil", Date.now() + lockHours * 60 * 60 * 1000);
          form.classList.add("is-locked");
          msg.textContent = `Kvůli opakovanému špatnému zadání je formulář dočasně uzavřen. Zkuste to prosím za ${lockHours} hodin, nebo napište na ${CONTACT_EMAIL}.`;
          msg.className = "form-msg error";
          return;
        }
        pickNewCaptcha(currentCaptchaAnswer);
        const rem = maxAttempts - attempts;
        const word = rem === 1 ? "pokus" : rem < 5 ? "pokusy" : "pokusů";
        msg.textContent = `Špatné číslo. Zbývají vám ${rem} ${word}.`;
        msg.className = "form-msg error";
        return;
      }
      setStored("attempts", 0);
    }

    msg.textContent = "Odesílám…";
    msg.className = "form-msg";

    const payload = {
      jmeno,
      email,
      telefon: document.getElementById("p-telefon").value.trim(),
      salon_nazev: document.getElementById("p-salon").value.trim(),
      zprava: document.getElementById("p-zprava").value.trim(),
      balicek: document.getElementById("p-balicek")?.value.trim() || "",
      souhlas: true,
    };

    const zpravaParts = [`Zdroj: ${POPTAVKA_SOURCE}`, payload.zprava];
    if (payload.balicek) zpravaParts.unshift(`Zájem: ${payload.balicek}`);
    payload.zprava = zpravaParts.filter(Boolean).join("\n\n");
    delete payload.balicek;

    try {
      const res = await fetch(`${API_BASE}/poptavka/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Odeslání se nepodařilo.");
      msg.textContent = data.message || "Děkujeme — ozveme se vám co nejdříve.";
      msg.className = "form-msg success";
      form.reset();
      pickNewCaptcha(null, false);
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "form-msg error";
    }
  });
})();
