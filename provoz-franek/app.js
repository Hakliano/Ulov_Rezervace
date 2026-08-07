(() => {
  const toggle = document.getElementById('nav-toggle');
  const nav = document.getElementById('nav');
  toggle?.addEventListener('click', () => {
    nav?.classList.toggle('is-open');
  });

  nav?.querySelectorAll('a').forEach((a) => {
    a.addEventListener('click', () => nav.classList.remove('is-open'));
  });

  const form = document.getElementById('contact-form');
  const msg = document.getElementById('form-msg');
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    const jmeno = document.getElementById('f-jmeno')?.value.trim();
    const email = document.getElementById('f-email')?.value.trim();
    const zprava = document.getElementById('f-zprava')?.value.trim();
    if (!jmeno || !email || !zprava) {
      if (msg) {
        msg.textContent = 'Vyplňte prosím jméno, e-mail a popis problému.';
        msg.classList.add('is-err');
        msg.classList.remove('is-ok');
      }
      return;
    }
    if (msg) {
      msg.textContent = 'Náhled OK — odesílání formuláře napojíme až s daty partnera (zatím bez API).';
      msg.classList.add('is-ok');
      msg.classList.remove('is-err');
    }
  });

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));
  const lerp = (a, b, t) => a + (b - a) * t;
  const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2);

  const traveler = document.getElementById('car-traveler');
  const hero = document.querySelector('.hero');
  const sluzby = document.getElementById('sluzby');
  const kontakt = document.getElementById('kontakt');
  const dockSluzby = document.getElementById('car-dock-sluzby');
  const dockPark = document.getElementById('car-dock-park');

  /* Hero → skip O nás → Služby → skip Mapa → Kontakt (park) */
  const stops = [
    { el: hero, tone: 'hero' },
    { el: sluzby, tone: 'mid', dock: dockSluzby },
    { el: kontakt, tone: 'park', dock: dockPark, final: true },
  ];

  let spinAcc = 0;
  let lastX = null;

  const spinWheels = (deg) => {
    traveler?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const carWidth = (tone) => {
    if (window.innerWidth < 880) return Math.min(300, window.innerWidth * 0.72);
    if (tone === 'hero') return Math.min(560, window.innerWidth * 0.48);
    if (tone === 'park') return Math.min(380, window.innerWidth * 0.3);
    return Math.min(440, window.innerWidth * 0.38);
  };

  /* Jedna vodorovná linie jízdy ve viewportu — Y se při jízdě nemění */
  const roadTop = (h) => window.innerHeight * 0.5 - h / 2;

  const parkX = (stop, w) => {
    if (stop.dock) {
      const r = stop.dock.getBoundingClientRect();
      if (r.width > 40) {
        return r.left + Math.max(0, (r.width - w) / 2);
      }
    }
    if (stop.tone === 'hero') {
      return Math.min(window.innerWidth - w - 28, window.innerWidth * 0.48);
    }
    if (stop.tone === 'mid') return 20;
    if (form) {
      const a = form.getBoundingClientRect();
      return Math.min(window.innerWidth - w - 16, a.right + 18);
    }
    return window.innerWidth - w - 24;
  };

  const focusY = () => window.scrollY + window.innerHeight * 0.42;

  const stopFocusY = (stop) => {
    const r = stop.el.getBoundingClientRect();
    return window.scrollY + r.top + r.height * (stop.tone === 'hero' ? 0.5 : 0.35);
  };

  const place = (x, w, tone, opacity, driving) => {
    if (!traveler) return;
    const h = w * (280 / 640);
    const y = roadTop(h);
    traveler.style.width = `${w}px`;
    traveler.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
    traveler.style.opacity = String(clamp(opacity, 0, 1));
    traveler.classList.toggle('is-hero', tone === 'hero' && !driving);
    traveler.classList.toggle('is-light', tone !== 'hero');
    traveler.classList.toggle('is-driving', driving);

    if (lastX != null && driving) {
      spinAcc += (x - lastX) * 0.55;
    }
    lastX = x;
    spinWheels(driving ? spinAcc : spinAcc * 0.15);
  };

  const updateCarDrive = () => {
    if (!traveler || stops.some((s) => !s.el)) return;

    const ys = stops.map(stopFocusY);
    const y = focusY();
    const widths = stops.map((s) => carWidth(s.tone));
    const xs = stops.map((s, i) => parkX(s, widths[i]));

    if (reduceMotion) {
      place(xs[0], widths[0], 'hero', 1, false);
      return;
    }

    if (y <= ys[0]) {
      place(xs[0], widths[0], 'hero', 1, false);
      return;
    }

    if (y >= ys[ys.length - 1]) {
      const i = ys.length - 1;
      place(xs[i], widths[i], 'park', 1, false);
      return;
    }

    let i = 0;
    for (let n = 0; n < ys.length - 1; n += 1) {
      if (y >= ys[n] && y <= ys[n + 1]) {
        i = n;
        break;
      }
    }

    const t = clamp((y - ys[i]) / Math.max(ys[i + 1] - ys[i], 1), 0, 1);
    const fromX = xs[i];
    const toX = xs[i + 1];
    const fromW = widths[i];
    const toW = widths[i + 1];
    const toTone = stops[i + 1].tone;
    const fromTone = stops[i].tone;
    const offRight = window.innerWidth + fromW * 0.2;
    const offLeft = -toW * 1.1;

    /* Jen horizont: park → vpravo pryč → zleva → park. Y vždy roadTop. */
    if (t < 0.16) {
      place(fromX, fromW, fromTone, 1, false);
      return;
    }
    if (t < 0.48) {
      const p = easeInOut((t - 0.16) / 0.32);
      place(lerp(fromX, offRight, p), lerp(fromW, toW, p * 0.25), fromTone, 1, true);
      return;
    }
    if (t < 0.52) {
      place(offLeft, toW, toTone, 0, false);
      lastX = offLeft;
      return;
    }
    if (t < 0.84) {
      const p = easeInOut((t - 0.52) / 0.32);
      place(lerp(offLeft, toX, p), lerp(fromW * 0.95, toW, p), toTone, 1, true);
      return;
    }

    place(toX, toW, toTone, 1, false);
  };

  let raf = 0;
  const loop = () => {
    updateCarDrive();
    raf = requestAnimationFrame(loop);
  };

  if (!reduceMotion) {
    raf = requestAnimationFrame(loop);
    window.addEventListener('pagehide', () => cancelAnimationFrame(raf), { once: true });
  } else {
    updateCarDrive();
    window.addEventListener('scroll', updateCarDrive, { passive: true });
  }

  window.addEventListener('resize', updateCarDrive, { passive: true });

  /* Po dokreslení blueprintu nechat čáry napevno */
  window.setTimeout(() => traveler?.classList.add('is-drawn'), 2600);

  const revealEls = [
    ...document.querySelectorAll('.section-grid, .service-list li, .map-frame, .contact-form'),
  ];
  revealEls.forEach((el) => el.classList.add('reveal'));
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealEls.forEach((el, i) => {
      el.style.transitionDelay = `${Math.min(i % 6, 5) * 60}ms`;
      io.observe(el);
    });
  } else {
    revealEls.forEach((el) => el.classList.add('is-in'));
  }
})();
