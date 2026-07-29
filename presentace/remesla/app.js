const DEMO_FOLDERS = {
  1: 'remesla-instalater',
  2: 'remesla-elektrikar',
  3: 'remesla-rekonstrukce',
};
const DEMO_LIVE_URLS = {
};

const host = window.location.hostname;
const isLocal = host === 'localhost' || host === '127.0.0.1';
const API_BASE = isLocal
  ? `http://${host}:8000/api`
  : 'https://api.ulovklienty.cz/api';

function salonDemoUrl(demoId, page) {
  if (!isLocal && DEMO_LIVE_URLS[demoId]) {
    const base = DEMO_LIVE_URLS[demoId].replace(/\/$/, '');
    return page === 'web' ? `${base}/` : `${base}/rezervace.html`;
  }
  const folder = DEMO_FOLDERS[demoId];
  if (!folder) return '#';
  if (!isLocal) {
    const base = `/${folder}`;
    return page === 'web' ? `${base}/` : `${base}/rezervace.html`;
  }
  const base = `../../${folder}`;
  return page === 'web' ? `${base}/index.html` : `${base}/rezervace.html`;
}

document.querySelectorAll('[data-demo]').forEach((link) => {
  const demoId = Number(link.dataset.demo);
  const page = link.dataset.page || 'web';
  if (DEMO_FOLDERS[demoId] || DEMO_LIVE_URLS[demoId]) {
    link.href = salonDemoUrl(demoId, page);
    link.target = '_blank';
    link.rel = 'noopener';
  }
});

document.querySelectorAll('a[data-package]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const select = document.getElementById('p-balicek');
    const value = btn.dataset.package;
    if (select && value) {
      const option = Array.from(select.options).find((o) => o.value === value);
      if (option) select.value = value;
    }
  });
});

const form = document.getElementById('poptavka-form');
const msg = document.getElementById('form-msg');
const STORAGE_PREFIX = 'poptavkaCaptcha_';
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
  const img = document.getElementById('pCaptchaImg');
  if (img && picked.img) img.src = picked.img;
  const captchaInput = document.getElementById('p-captcha');
  if (captchaInput) {
    captchaInput.value = '';
    if (shouldFocus !== false) captchaInput.focus();
  }
}

function initPoptavkaCaptcha() {
  if (!form) return;
  const optionsJson = form.getAttribute('data-captcha-options');
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

  const lockHours = parseInt(form.getAttribute('data-captcha-lock-hours'), 10) || 4;
  const until = getStored('lockedUntil');
  if (until && Date.now() < until) {
    form.classList.add('is-locked');
    if (msg) {
      msg.textContent =
        `Formulář je dočasně uzavřen (ochrana proti robotům). Zkuste to za ${lockHours} h, nebo napište na info@ulovklienty.cz.`;
      msg.className = 'form-msg error';
    }
  } else if (until) {
    setStored('lockedUntil', null);
    setStored('attempts', 0);
  }

  document.getElementById('pCaptchaRefresh')?.addEventListener('click', () => {
    pickNewCaptcha(currentCaptchaAnswer);
  });
}

initPoptavkaCaptcha();

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!msg) return;

  if (form.classList.contains('is-locked')) return;

  const hp = form.querySelector('input[name="_gotcha"]');
  if (hp && hp.value.trim() !== '') return;

  msg.textContent = '';
  msg.className = 'form-msg';

  const jmeno = document.getElementById('p-jmeno').value.trim();
  const email = document.getElementById('p-email').value.trim();
  if (jmeno.length < 2) {
    msg.textContent = 'Vyplňte prosím jméno.';
    msg.className = 'form-msg error';
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    msg.textContent = 'Zadejte platný e-mail.';
    msg.className = 'form-msg error';
    return;
  }
  if (!document.getElementById('p-souhlas').checked) {
    msg.textContent = 'Potvrďte prosím souhlas se zpracováním údajů.';
    msg.className = 'form-msg error';
    return;
  }

  if (currentCaptchaAnswer !== null) {
    const userAnswer = (document.getElementById('p-captcha')?.value || '').trim();
    if (userAnswer !== currentCaptchaAnswer) {
      const lockHours = parseInt(form.getAttribute('data-captcha-lock-hours'), 10) || 4;
      const attempts = (getStored('attempts') || 0) + 1;
      setStored('attempts', attempts);
      if (attempts >= maxAttempts) {
        setStored('lockedUntil', Date.now() + lockHours * 60 * 60 * 1000);
        form.classList.add('is-locked');
        msg.textContent =
          `Kvůli opakovanému špatnému zadání je formulář dočasně uzavřen. Zkuste to prosím za ${lockHours} hodin, nebo napište na info@ulovklienty.cz.`;
        msg.className = 'form-msg error';
        return;
      }
      pickNewCaptcha(currentCaptchaAnswer);
      const left = maxAttempts - attempts;
      const word = left === 1 ? 'pokus' : left < 5 ? 'pokusy' : 'pokusů';
      msg.textContent = `Špatné číslo. Zbývají vám ${left} ${word}.`;
      msg.className = 'form-msg error';
      return;
    }
    setStored('attempts', 0);
  }

  msg.textContent = 'Odesílám…';
  msg.className = 'form-msg';

  const payload = {
    jmeno,
    email,
    telefon: document.getElementById('p-telefon').value.trim(),
    salon_nazev: document.getElementById('p-salon').value.trim(),
    zprava: document.getElementById('p-zprava').value.trim(),
    balicek: document.getElementById('p-balicek')?.value.trim() || '',
    souhlas: true,
  };

  const zpravaParts = [payload.zprava];
  if (payload.balicek) zpravaParts.unshift(`Balíček: ${payload.balicek}`);
  payload.zprava = zpravaParts.filter(Boolean).join('\n\n');
  delete payload.balicek;

  try {
    const res = await fetch(`${API_BASE}/poptavka/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Odeslání se nepodařilo.');
    msg.textContent = data.message || 'Děkujeme — ozveme se vám co nejdříve.';
    msg.className = 'form-msg success';
    form.reset();
    pickNewCaptcha(null, false);
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'form-msg error';
  }
});

(() => {
  const block = document.getElementById('srovnani');
  const btn = document.getElementById('compareToggle');
  if (!block || !btn) return;

  const labelExpand = 'Porovnat všechny funkce';
  const labelCollapse = 'Skrýt srovnání';

  btn.addEventListener('click', () => {
    const expanded = block.classList.toggle('is-expanded');
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    btn.textContent = expanded ? labelCollapse : labelExpand;
    if (!expanded) {
      block.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
})();

(() => {
  const btn = document.getElementById('growthBoardToggle');
  const board = document.getElementById('program-rustu-prehled');
  const link = document.getElementById('highlightGrowthPhoto');
  if (!board) return;

  const labelOpen = 'Program růstu — celý přehled';
  const labelClose = 'Skrýt přehled Programu růstu';

  function setOpen(open, { pulse = false, scroll = false } = {}) {
    if (open) {
      board.removeAttribute('hidden');
      if (btn) {
        btn.setAttribute('aria-expanded', 'true');
        btn.textContent = labelClose;
      }
      if (pulse) {
        board.classList.add('is-pulse');
        window.setTimeout(() => board.classList.remove('is-pulse'), 1800);
      }
      if (scroll) {
        board.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } else {
      board.setAttribute('hidden', '');
      board.classList.remove('is-pulse');
      if (btn) {
        btn.setAttribute('aria-expanded', 'false');
        btn.textContent = labelOpen;
      }
    }
  }

  btn?.addEventListener('click', () => {
    const open = board.hasAttribute('hidden');
    setOpen(open, { scroll: open });
  });

  link?.addEventListener('click', (e) => {
    e.preventDefault();
    setOpen(true, { pulse: true, scroll: true });
  });

  link?.addEventListener('mouseenter', () => {
    if (!board.hasAttribute('hidden')) board.classList.add('is-pulse');
  });
  link?.addEventListener('mouseleave', () => board.classList.remove('is-pulse'));

  if (window.location.hash === '#program-rustu' || window.location.hash === '#program-rustu-prehled') {
    setOpen(true);
  }
})();

(() => {
  const btn = document.getElementById('growthMoreToggle');
  const panel = document.getElementById('growthMorePanel');
  if (!btn || !panel) return;

  btn.addEventListener('click', () => {
    const open = panel.hasAttribute('hidden');
    if (open) {
      panel.removeAttribute('hidden');
      btn.setAttribute('aria-expanded', 'true');
      btn.textContent = 'Ukázat méně';
    } else {
      panel.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = 'Přečíst více';
      btn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
})();