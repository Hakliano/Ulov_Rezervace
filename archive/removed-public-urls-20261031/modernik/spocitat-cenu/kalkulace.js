(function () {
  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1';
  const isStaging = host.includes('staging');
  const API_BASE = isLocal
    ? `http://${host}:8000/api`
    : (isStaging
      ? 'https://api-staging.ulovklienty.cz/api'
      : 'https://api.ulovklienty.cz/api');
  const CONTACT_EMAIL = 'hakl@modernik.cz';

  const TYPES = {
    kaderictvi: 'Kadeřnictví / beauty',
    veterina: 'Veterinární ordinace',
    psi_salon: 'Psí salon / grooming',
    autoservis: 'Autoservis',
    dental: 'Dentální hygiena',
    jina: 'Jiná',
  };

  const PLANS = {
    start: {
      label: 'Moderník START',
      pick: 'Moderník START',
      kicker: 'MODERNÍK START',
      blurb: 'Základ pro vlastní prezentaci a online objednávání. Váš web, rezervace a každodenní provoz na jednom místě.',
      included: 'START řeší základ — najít vás a nechat zákazníky objednat se sami.',
    },
    pro: {
      label: 'Moderník PRO',
      pick: 'Moderník PRO',
      kicker: 'MODERNÍK PRO',
      blurb: 'Moderník, který vám kromě webu a rezervací pomáhá šetřit čas, pracovat se zákazníky, získávat recenze a mít větší přehled o provozu.',
      included: 'PRO pracuje i ve chvíli, kdy vy pracujete se zákazníkem.',
    },
  };

  const BASE_PRICE = {
    start: { 6: 1800, 12: 3000 },
    pro: { 6: 3600, 12: 5999 },
  };

  const form = document.getElementById('kalkulace-form');
  const thanks = document.getElementById('calc-thanks');
  const msg = document.getElementById('form-msg');
  const pagesInput = document.getElementById('calc-pages');
  const noteInput = document.getElementById('calc-note');
  const growthCheck = document.getElementById('calc-growth');
  const growthCheck12 = document.getElementById('calc-growth-12');
  const growthModal = document.getElementById('calc-growth-modal');
  const growthModalCta = document.getElementById('calc-growth-modal-cta');

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

  function initCaptcha() {
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
      document.querySelector('.calc-contact')?.classList.add('is-locked');
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

  function webMonthly(pages) {
    const extra = Math.max(0, pages - 4);
    return extra === 0 ? 0 : Math.ceil(extra / 3) * 30;
  }

  function formatKc(n) {
    return `${String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0')}\u00a0Kč`;
  }

  function selectedType() {
    return form?.querySelector('input[name="typ"]:checked')?.value || '';
  }

  function selectedPeriod() {
    const raw = form?.querySelector('input[name="period"]:checked')?.value;
    return raw === '6' || raw === '12' ? Number(raw) : 0;
  }

  function selectedPlan() {
    const raw = form?.querySelector('input[name="plan"]:checked')?.value;
    return raw === 'start' || raw === 'pro' ? raw : '';
  }

  function pagesValue() {
    const n = Number.parseInt(pagesInput?.value, 10);
    if (Number.isNaN(n) || n < 0) return 0;
    return Math.min(n, 1000);
  }

  function materialnikYes() {
    return form?.querySelector('input[name="materialnik"]:checked')?.value === 'ano';
  }

  function materialnikIsIncluded(plan) {
    return plan === 'pro';
  }

  function growthIsFree(plan, months) {
    return plan === 'pro' && months === 12;
  }

  function growthWanted() {
    const plan = selectedPlan();
    const months = selectedPeriod();
    if (growthIsFree(plan, months)) return true;
    if (months === 12) return !!growthCheck12?.checked;
    return !!growthCheck?.checked;
  }

  function isThrottleMessage(text) {
    return /throttl|limitován|omezení počtu|Expected available|rate.?limit|429/i.test(text || '');
  }

  function userFacingSubmitError(res, data) {
    const raw = data && data.detail;
    const detail = typeof raw === 'string' ? raw : '';
    if (res.status === 429 || isThrottleMessage(detail)) {
      return 'Kalkulaci se nyní nepodařilo odeslat. Zkuste to prosím později.';
    }
    if (detail && !isThrottleMessage(detail)) return detail;
    return 'Kalkulaci se nyní nepodařilo odeslat. Zkuste to prosím později.';
  }

  function compute(plan, pages, months, materialnik, growth) {
    const base = BASE_PRICE[plan]?.[months];
    if (!base) return null;
    const wm = webMonthly(pages);
    const mat = materialnikIsIncluded(plan) ? 0 : (materialnik ? 99 : 0);
    const gr = growthIsFree(plan, months) ? 0 : (growth ? 999 : 0);
    const total = base + wm * months + mat * months + gr;
    return { total, monthly: Math.round(total / months), wm, mat, gr, base };
  }

  function updatePeriodCards(plan) {
    const sixMonthly = document.getElementById('calc-period-6-monthly');
    const sixTotal = document.getElementById('calc-period-6-total');
    const sixNote = document.getElementById('calc-period-6-note');
    const yearMonthly = document.getElementById('calc-period-12-monthly');
    const yearTotal = document.getElementById('calc-period-12-total');
    const yearNote = document.getElementById('calc-period-12-note');
    const waitingCopy = 'Cena se zobrazí po výběru START / PRO';
    const setWaiting = (monthlyEl, totalEl, waiting) => {
      monthlyEl?.classList.toggle('is-waiting', waiting);
      totalEl?.classList.toggle('is-waiting', waiting);
    };
    if (plan === 'start') {
      setWaiting(sixMonthly, sixTotal, false);
      setWaiting(yearMonthly, yearTotal, false);
      if (sixMonthly) sixMonthly.textContent = `≈ ${formatKc(300)} / měsíc`;
      if (sixTotal) sixTotal.textContent = `${formatKc(1800)} za 6 měsíců`;
      if (sixNote) sixNote.textContent = 'Poté možnost pokračovat, nebo si znovu zvolit předplacené období.';
      if (yearMonthly) yearMonthly.textContent = `≈ ${formatKc(250)} / měsíc`;
      if (yearTotal) yearTotal.textContent = `${formatKc(3000)} za 12 měsíců`;
      if (yearNote) yearNote.textContent = 'Poté možnost pokračovat, nebo si znovu zvolit předplacené období.';
    } else if (plan === 'pro') {
      setWaiting(sixMonthly, sixTotal, false);
      setWaiting(yearMonthly, yearTotal, false);
      if (sixMonthly) sixMonthly.textContent = `≈ ${formatKc(600)} / měsíc`;
      if (sixTotal) sixTotal.textContent = `${formatKc(3600)} za 6 měsíců`;
      if (sixNote) sixNote.textContent = 'Poté možnost pokračovat za 550 Kč/měs. nebo si znovu zvolit předplacené období.';
      if (yearMonthly) yearMonthly.textContent = `≈ ${formatKc(500)} / měsíc`;
      if (yearTotal) yearTotal.textContent = `${formatKc(5999)} za 12 měsíců`;
      if (yearNote) yearNote.textContent = 'Poté možnost pokračovat za 499 Kč/měs. nebo si znovu zvolit předplacené období.';
    } else {
      setWaiting(sixMonthly, sixTotal, true);
      setWaiting(yearMonthly, yearTotal, true);
      if (sixMonthly) sixMonthly.textContent = waitingCopy;
      if (sixTotal) sixTotal.textContent = '';
      if (sixNote) sixNote.textContent = 'Poté možnost pokračovat, nebo si znovu zvolit předplacené období.';
      if (yearMonthly) yearMonthly.textContent = waitingCopy;
      if (yearTotal) yearTotal.textContent = '';
      if (yearNote) yearNote.textContent = 'Poté možnost pokračovat, nebo si znovu zvolit předplacené období.';
    }
    const paid12 = document.getElementById('calc-growth-panel-12-paid');
    const free12 = document.getElementById('calc-growth-panel-12-free');
    const yearIsFree = plan === 'pro';
    if (paid12) paid12.hidden = yearIsFree;
    if (free12) free12.hidden = !yearIsFree;
  }

  function updatePlanCtas(plan) {
    document.querySelectorAll('.calc-plan-cta').forEach((el) => {
      const kind = el.getAttribute('data-cta');
      if (kind === 'start') el.textContent = plan === 'start' ? 'START ✓' : 'Chci START';
      if (kind === 'pro') el.textContent = plan === 'pro' ? 'PRO ✓' : 'Chci PRO';
    });
  }

  function pagesPhrase(pages) {
    if (pages === 0) return 'Web: hlavní stránka';
    if (pages === 1) return 'Web: hlavní + 1 podstránka';
    if (pages >= 2 && pages <= 4) return `Web: hlavní + ${pages} podstránky`;
    return `Web: hlavní + ${pages} podstránek`;
  }

  function periodPhrase(months) {
    return months === 12 ? 'Partnerství: 12 měsíců' : 'Partnerství: 6 měsíců';
  }

  function growthPhrase(plan, months, growth) {
    if (growthIsFree(plan, months)) return 'Program růstu zdarma';
    if (growth) return 'Program růstu';
    return '';
  }

  function render() {
    if (!form) return;
    const pages = pagesValue();
    const months = selectedPeriod();
    const materialnik = materialnikYes();
    const growth = growthWanted();
    const plan = selectedPlan();
    const typ = TYPES[selectedType()] || '';
    const note = (noteInput?.value || '').trim();
    const summary = document.querySelector('.calc-summary');
    const emptyEl = document.getElementById('calc-summary-empty');
    const emptyTitle = document.getElementById('calc-empty-title');
    const emptyText = document.getElementById('calc-empty-text');
    const priceWrap = document.getElementById('calc-summary-price');
    const monthlyEl = document.getElementById('calc-monthly');
    const totalEl = document.getElementById('calc-total');
    const picksEl = document.getElementById('calc-picks');
    const specialEl = document.getElementById('calc-special');
    const growthHint = document.getElementById('calc-growth-hint');
    const includedEl = document.getElementById('calc-included');
    const productKicker = document.getElementById('calc-product-kicker');
    const productBlurb = document.getElementById('calc-product-blurb');

    document.querySelectorAll('.calc-period-card').forEach((card) => {
      const input = card.querySelector('input[name="period"]');
      card.classList.toggle('is-active', !!input?.checked);
    });
    document.querySelectorAll('.calc-plan-card').forEach((card) => {
      const input = card.querySelector('input[name="plan"]');
      card.classList.toggle('is-active', !!input?.checked);
    });
    updatePeriodCards(plan);
    updatePlanCtas(plan);
    const matChoice = document.getElementById('calc-mat-choice');
    const matIncluded = document.getElementById('calc-mat-included');
    const matInPro = materialnikIsIncluded(plan);
    if (matChoice) matChoice.hidden = matInPro;
    if (matIncluded) matIncluded.hidden = !matInPro;

    const ready = !!plan && (months === 6 || months === 12);
    summary?.classList.toggle('is-empty', !ready);
    if (emptyEl) emptyEl.hidden = ready;
    if (priceWrap) priceWrap.hidden = !ready;
    if (!ready && emptyTitle && emptyText) {
      if (!plan) {
        emptyTitle.textContent = 'Cena se zobrazí po výběru START / PRO';
        emptyText.textContent = 'Nejdřív zvolte, co má Moderník řešit. Cenu uvidíte hned potom.';
      } else {
        emptyTitle.textContent = 'Vyberte si délku Partnerství';
        emptyText.textContent = 'Hned potom vám cenu spočítáme.';
      }
    }

    if (ready) {
      const price = compute(plan, pages, months, materialnik, growth);
      const meta = PLANS[plan];
      if (productKicker) productKicker.textContent = meta.kicker;
      if (productBlurb) productBlurb.textContent = meta.blurb;
      if (monthlyEl) monthlyEl.textContent = `≈ ${formatKc(price.monthly)} / měsíc`;
      if (totalEl) {
        totalEl.textContent = months === 12
          ? `Celkem ${formatKc(price.total)} za prvních 12 měsíců`
          : `${formatKc(price.total)} za prvních 6 měsíců`;
      }
      if (growthHint) {
        if (growthIsFree(plan, months)) {
          growthHint.hidden = false;
          growthHint.textContent = 'Program růstu máte zdarma.';
        } else if (growth) {
          growthHint.hidden = false;
          growthHint.textContent = 'Program růstu je v této kalkulaci započítaný.';
        } else {
          growthHint.hidden = true;
          growthHint.textContent = '';
        }
      }
      if (includedEl) {
        includedEl.hidden = false;
        includedEl.textContent = meta.included;
      }
    } else if (includedEl) {
      includedEl.hidden = true;
      includedEl.textContent = '';
    }

    if (picksEl) {
      const items = [];
      if (typ) items.push(typ);
      if (plan) items.push(PLANS[plan].pick);
      items.push(pagesPhrase(pages));
      if (materialnikIsIncluded(plan)) items.push('Materiálník – v ceně PRO');
      else if (materialnik) items.push('Materiálník +99 Kč/měs.');
      if (months === 6 || months === 12) items.push(periodPhrase(months));
      const g = (months === 6 || months === 12) ? growthPhrase(plan, months, growth) : '';
      if (g) items.push(g);
      if (ready && items.length) {
        picksEl.hidden = false;
        picksEl.innerHTML = `<li class="calc-picks-title">Vybrali jste</li>${
          items.map((t) => `<li>${t}</li>`).join('')
        }`;
      } else {
        picksEl.hidden = true;
        picksEl.innerHTML = '';
      }
    }

    if (specialEl) {
      if (note) {
        specialEl.hidden = false;
        specialEl.textContent = `Speciální požadavek: „${note}“`;
      } else {
        specialEl.hidden = true;
        specialEl.textContent = '';
      }
    }
  }

  function setPages(next) {
    const value = Math.max(0, Math.min(1000, next));
    if (pagesInput) pagesInput.value = String(value);
    render();
  }

  document.getElementById('calc-pages-minus')?.addEventListener('click', () => {
    setPages(pagesValue() - 1);
  });
  document.getElementById('calc-pages-plus')?.addEventListener('click', () => {
    setPages(pagesValue() + 1);
  });

  document.querySelectorAll('[data-growth-open]').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const period = btn.getAttribute('data-growth-open');
      const months = period === '6' ? 6 : 12;
      const plan = selectedPlan();
      const free = growthIsFree(plan, months);
      if (growthModalCta) {
        growthModalCta.textContent = free
          ? 'Program růstu zdarma'
          : 'Program růstu +999 Kč';
      }
      const cont = document.getElementById('calc-growth-continue');
      if (cont) cont.hidden = months !== 6;
      if (growthModal?.showModal) growthModal.showModal();
    });
  });

  growthCheck?.addEventListener('change', () => {
    if (!growthCheck.checked) return;
    const six = form?.querySelector('input[name="period"][value="6"]');
    if (six) six.checked = true;
    render();
  });

  growthCheck12?.addEventListener('change', () => {
    if (!growthCheck12.checked) return;
    const year = form?.querySelector('input[name="period"][value="12"]');
    if (year) year.checked = true;
    render();
  });

  form?.addEventListener('input', render);
  form?.addEventListener('change', render);
  initCaptcha();
  render();

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!msg) return;
    if (form.classList.contains('is-locked')) return;

    const hp = form.querySelector('input[name="_gotcha"]');
    if (hp && hp.value.trim() !== '') return;

    msg.textContent = '';
    msg.className = 'form-msg';

    const typ = selectedType();
    const plan = selectedPlan();
    const email = document.getElementById('calc-email')?.value.trim() || '';
    const telefon = document.getElementById('calc-phone')?.value.trim() || '';
    const pages = pagesValue();
    const months = selectedPeriod();
    const materialnik = materialnikYes();
    const growth = growthWanted();
    const poznamka = (noteInput?.value || '').trim();

    if (!typ) {
      msg.textContent = 'Vyberte typ provozovny.';
      msg.className = 'form-msg error';
      return;
    }
    if (!plan) {
      msg.textContent = 'Vyberte variantu Moderníku START nebo PRO.';
      msg.className = 'form-msg error';
      return;
    }
    if (months !== 6 && months !== 12) {
      msg.textContent = 'Vyberte délku Partnerství.';
      msg.className = 'form-msg error';
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      msg.textContent = 'Zadejte platný e-mail.';
      msg.className = 'form-msg error';
      return;
    }
    if (!telefon) {
      msg.textContent = 'Vyplňte telefon.';
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
          document.querySelector('.calc-contact')?.classList.add('is-locked');
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

    try {
      const res = await fetch(`${API_BASE}/kalkulace/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          telefon,
          typ,
          pages,
          materialnik: materialnikIsIncluded(plan) ? true : materialnik,
          period: months,
          growth,
          poznamka,
          plan,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(userFacingSubmitError(res, data));

      const localPrice = compute(plan, pages, months, materialnik, growth);
      const backendTotal = Number(data.total);
      const total = Number.isFinite(backendTotal)
        ? backendTotal
        : (localPrice ? localPrice.total : NaN);
      const periodMonths = Number(data.period_months) || months;
      const monthly = Number.isFinite(total) ? Math.round(total / periodMonths) : null;
      const thanksMonthly = document.getElementById('calc-thanks-monthly');
      const thanksPrice = document.getElementById('calc-thanks-price');
      if (thanksMonthly && monthly != null) {
        thanksMonthly.textContent = `≈ ${formatKc(monthly)} / měsíc`;
      }
      if (thanksPrice && Number.isFinite(total)) {
        thanksPrice.textContent = periodMonths === 6
          ? `${formatKc(total)} za prvních 6 měsíců`
          : `${formatKc(total)} za prvních 12 měsíců`;
      }
      form.classList.add('is-sent');
      document.querySelector('.calc-contact')?.classList.add('is-sent');
      if (thanks) {
        thanks.hidden = false;
        thanks.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      msg.textContent = '';
    } catch (err) {
      const raw = err && err.message ? String(err.message) : '';
      msg.textContent = isThrottleMessage(raw)
        ? 'Kalkulaci se nyní nepodařilo odeslat. Zkuste to prosím později.'
        : (raw || 'Kalkulaci se nyní nepodařilo odeslat. Zkuste to prosím později.');
      msg.className = 'form-msg error';
    }
  });
})();
