(function () {
  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1';
  const isModernik = host.includes('modernik');
  const isStaging = host.includes('staging');
  const API_BASE = isLocal
    ? `http://${host}:8000/api`
    : (isStaging
      ? 'https://api-staging.ulovklienty.cz/api'
      : 'https://api.ulovklienty.cz/api');
  const POPTAVKA_SOURCE = isModernik ? 'Moderník (modernik.cz)' : 'ULOV KLIENTY (ulovklienty.cz)';
  const CONTACT_EMAIL = isModernik ? 'info@modernik.cz' : 'info@ulovklienty.cz';
  const ARCHIVNIK_PREZENTACE = isStaging
    ? 'https://www.staging.ulovklienty.cz/archivnik-prezentace/'
    : 'https://www.ulovklienty.cz/archivnik-prezentace/';

  document.querySelectorAll('[data-archivnik-prezentace]').forEach((a) => {
    a.setAttribute('href', ARCHIVNIK_PREZENTACE);
  });

  const tiles = document.querySelectorAll('.tile[data-tile]');
  const tabs = document.querySelectorAll('.portfolio-tabs .tab');
  const items = document.querySelectorAll('.portfolio-item');

  function setProbeLabel(btn, open) {
    if (!btn) return;
    const label = btn.querySelector('.tile-probe-label') || btn;
    if (btn.querySelector('.tile-probe-label')) {
      label.textContent = open ? 'Zavřít' : 'Prozkoumat';
    } else {
      // keep SVG, replace text node
      const texts = [...btn.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE);
      texts.forEach((n) => n.remove());
      btn.append(` ${open ? 'Zavřít' : 'Prozkoumat'}`);
    }
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.setAttribute('aria-label', open ? 'Zavřít detail' : 'Prozkoumat detail');
  }

  function closeAllTiles(except) {
    tiles.forEach((tile) => {
      if (tile === except) return;
      tile.classList.remove('is-open');
      setProbeLabel(tile.querySelector('.tile-probe'), false);
    });
  }

  tiles.forEach((tile) => {
    const probe = tile.querySelector('.tile-probe');
    probe?.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = tile.classList.contains('is-open');
      closeAllTiles();
      if (!open) {
        tile.classList.add('is-open');
        setProbeLabel(probe, true);
        tile.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        setProbeLabel(probe, false);
      }
    });
  });

  const lightbox = document.getElementById('tile-lightbox');
  const lightboxImg = document.getElementById('tile-lightbox-img');
  const lightboxClose = document.getElementById('tile-lightbox-close');

  function openTileLightbox(img) {
    if (!lightbox || !lightboxImg || !img) return;
    lightboxImg.src = img.currentSrc || img.src;
    lightboxImg.alt = img.alt || '';
    if (typeof lightbox.showModal === 'function') lightbox.showModal();
  }

  function closeTileLightbox() {
    if (lightbox?.open) lightbox.close();
  }

  document.querySelectorAll('.tile-shot-open').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openTileLightbox(btn.querySelector('img'));
    });
  });
  lightboxClose?.addEventListener('click', closeTileLightbox);
  lightbox?.addEventListener('click', (event) => {
    if (event.target === lightbox) closeTileLightbox();
  });

  const PROBLEMS = {
    telefon: {
      title: 'Zvoní vám telefon, když pracujete?',
      problem: 'Zákaznice chce termín. Vy máte právě někoho na křesle. Telefon zvoní. Pokud ho nevezmete, možná zavolá jinam. Pokud ho vezmete, přerušíte svoji práci.',
      solution: 'Zákaznice si na vašem webu sama vybere službu, pracovníka, datum a volný čas. Rezervaci může vytvořit klidně ve tři ráno. Vy ráno pouze vidíte: „Nová rezervace – pátek 14:30.“',
      img: 'https://haklweb.b-cdn.net/ULOV_KLIENTA/ui_flow1.webp',
      imgAlt: 'FLOW — přehled dne a nová rezervace',
    },
    web: {
      title: 'Web máte. Ale opravdu pro vás pracuje?',
      problem: 'Stránka existuje, ale zákazník na ní neudělá další krok. Volá, píše, nebo odejde jinam.',
      solution: 'Web na míru ukazuje, kdo jste, a vede rovnou k rezervaci. Není to vizitka někde na internetu — je to začátek cesty zákazníka.',
      img: 'https://haklweb.b-cdn.net/webs/salon-19/hero/5efa416ca0e04d0c94933cd4d18f533c.webp',
      imgAlt: 'Ukázka webu partnera Moderníka',
    },
    hlava: {
      title: 'Nosíte informace o zákaznících v hlavě?',
      problem: 'Barva, alergie, poznámka z minula. Když nejste u křesla vy, kolega to neví. Když onemocníte, informace odejde s vámi.',
      solution: 'Archivník drží zákazníka, jeho karty a historii na jednom místě. Bezpečně, přehledně, i když zrovna obsluhujete někoho jiného.',
    },
    recenze: {
      title: 'Máte spokojené zákazníky, ale málo recenzí?',
      problem: 'Návštěva dopadla dobře. Zákazník odejde. Výzva k recenzi se nestane, protože zrovna uklízíte nebo berete dalšího.',
      solution: 'Po návštěvě může Moderník poslat poděkování a slušnou výzvu k recenzi za vás. Vy mezitím děláte svou práci.',
    },
    sklad: {
      title: 'Nevíte přesně, co dochází?',
      problem: 'Barva, šampon, díl. Kontrolujete očima, až když něco chybí uprostřed služby.',
      solution: 'Materiálník hlídá spotřebu u služeb. Vidíte, co dochází, dřív než to dojde na polici.',
    },
    diar: {
      title: 'Máte provoz rozdělený mezi diář, telefon a zprávy?',
      problem: 'Termín je v sešitě, přesun v SMS, poznámka v hlavě. Kolega to nevidí. Vy to skládáte každé ráno znovu.',
      solution: 'FLOW dá termíny, tým i stavy návštěv na jedno místo. Kalendář provozovny, ne tři různé evidenční systémy.',
      img: 'https://haklweb.b-cdn.net/ULOV_KLIENTA/ui_flow1.webp',
      imgAlt: 'FLOW — kalendář provozovny',
    },
    emaily: {
      title: 'Píšete zákazníkům pořád stejné zprávy?',
      problem: 'Potvrzení rezervace, připomínka, poděkování. Stejný text pořád dokola, nebo se nepošle vůbec.',
      solution: 'Potvrzení, připomínky a další komunikace může odcházet automaticky. Texty jdou upravit, provoz běží i ve tři ráno.',
    },
    celky: {
      title: 'Platíte několik služeb, které spolu nemluví?',
      problem: 'Jeden nástroj na web, druhý na termíny, třetí na sklady. Data se přepisují. Když jeden spadne, držíte to ručně.',
      solution: 'Části Moderníka jsou navržené tak, aby na sebe navazovaly. Zákazník, termín, karta i zpráva patří k sobě — ne k pěti přihlášením.',
    },
  };

  const problemDialog = document.getElementById('problem-dialog');
  const problemBody = document.getElementById('problem-dialog-body');
  const problemClose = document.getElementById('problem-dialog-close');

  function closeProblemDialog() {
    if (problemDialog?.open) problemDialog.close();
  }

  function openProblemDialog(id) {
    const item = PROBLEMS[id];
    if (!item || !problemDialog || !problemBody) return;
    const img = item.img
      ? `<img class="problem-dialog-shot" src="${item.img}" alt="${item.imgAlt || ''}" width="1600" height="900">`
      : '';
    problemBody.innerHTML = `
      <h2 id="problem-dialog-title">${item.title}</h2>
      <h3>Problém</h3>
      <p>${item.problem}</p>
      <h3>Jak to řeší Moderník</h3>
      <p>${item.solution}</p>
      ${img}
    `;
    if (typeof problemDialog.showModal === 'function') problemDialog.showModal();
  }

  document.querySelectorAll('.problem-open').forEach((btn) => {
    btn.addEventListener('click', () => openProblemDialog(btn.dataset.problem));
  });
  problemClose?.addEventListener('click', closeProblemDialog);
  problemDialog?.addEventListener('click', (event) => {
    if (event.target === problemDialog) closeProblemDialog();
  });

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const cat = tab.dataset.category || 'all';
      tabs.forEach((t) => t.classList.toggle('is-active', t === tab));
      items.forEach((item) => {
        const match = cat === 'all' || item.dataset.category === cat;
        item.hidden = !match;
      });
    });
  });

  /* ── Poptávka formulář (stejná logika jako beauty) ── */
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
          `Formulář je dočasně uzavřen (ochrana proti robotům). Zkuste to za ${lockHours} h, nebo napište na ${CONTACT_EMAIL}.`;
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
            `Kvůli opakovanému špatnému zadání je formulář dočasně uzavřen. Zkuste to prosím za ${lockHours} hodin, nebo napište na ${CONTACT_EMAIL}.`;
          msg.className = 'form-msg error';
          return;
        }
        pickNewCaptcha(currentCaptchaAnswer);
        const rem = maxAttempts - attempts;
        const word = rem === 1 ? 'pokus' : rem < 5 ? 'pokusy' : 'pokusů';
        msg.textContent = `Špatné číslo. Zbývají vám ${rem} ${word}.`;
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

    const zpravaParts = [`Zdroj: ${POPTAVKA_SOURCE}`, payload.zprava];
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
})();
