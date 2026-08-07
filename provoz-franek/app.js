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

  /* Zastávky na každé druhé sekci: Hero → (skip O nás) → Služby → (skip Mapa) → Kontakt */
  const stops = [
    { el: hero, side: 'right', final: false, tone: 'hero' },
    { el: sluzby, side: 'left', final: false, tone: 'mid' },
    { el: kontakt, side: 'right', final: true, tone: 'park', anchor: form },
  ];

  let parallaxX = 0;
  let parallaxY = 0;
  let targetParallaxX = 0;
  let targetParallaxY = 0;

  const spinWheels = (deg) => {
    traveler?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const carWidth = (tone) => {
    if (window.innerWidth < 880) return Math.min(320, window.innerWidth * 0.78);
    if (tone === 'hero') return Math.min(580, window.innerWidth * 0.52);
    if (tone === 'park') return Math.min(420, window.innerWidth * 0.34);
    return Math.min(500, window.innerWidth * 0.46);
  };

  const dockPoint = (stop) => {
    const w = carWidth(stop.tone);
    const h = w * (280 / 640);
    const r = stop.el.getBoundingClientRect();

    if (stop.anchor) {
      const a = stop.anchor.getBoundingClientRect();
      let left = a.right + 20;
      let top = a.top + a.height * 0.28;
      if (left + w > window.innerWidth - 10) {
        left = Math.max(12, window.innerWidth - w - 14);
        top = a.top + a.height * 0.08;
      }
      if (window.innerWidth < 880) {
        left = Math.max(12, (window.innerWidth - w) / 2);
        top = a.bottom - h * 0.15;
      }
      return { left, top, w, h, opacity: window.innerWidth < 880 ? 0.45 : 0.7 };
    }

    if (stop.side === 'left') {
      return {
        left: Math.max(12, r.left + 8),
        top: r.top + r.height * 0.38,
        w,
        h,
        opacity: 0.7,
      };
    }

    /* right — hero default */
    return {
      left: Math.min(r.right - w - 8, window.innerWidth - w - 20),
      top: stop.tone === 'hero' ? r.bottom - h - Math.min(70, r.height * 0.1) : r.top + r.height * 0.3,
      w,
      h,
      opacity: stop.tone === 'hero' ? 1 : 0.72,
    };
  };

  const focusY = () => window.scrollY + window.innerHeight * 0.42;

  const stopFocusY = (stop) => {
    const r = stop.el.getBoundingClientRect();
    return window.scrollY + r.top + r.height * (stop.tone === 'hero' ? 0.55 : 0.35);
  };

  const place = (left, top, w, opacity, spin, parallax = true) => {
    if (!traveler) return;
    const px = parallax ? parallaxX * opacity : 0;
    const py = parallax ? parallaxY * opacity : 0;
    traveler.style.width = `${w}px`;
    traveler.style.transform = `translate3d(${(left + px).toFixed(1)}px, ${(top + py).toFixed(1)}px, 0)`;
    traveler.style.opacity = String(clamp(opacity, 0, 1));
    traveler.classList.toggle('is-hero', opacity > 0.85 && spin < 40);
    spinWheels(spin);
  };

  const updateCarDrive = () => {
    if (!traveler || stops.some((s) => !s.el)) return;

    parallaxX += (targetParallaxX - parallaxX) * 0.1;
    parallaxY += (targetParallaxY - parallaxY) * 0.1;

    const docks = stops.map(dockPoint);
    const ys = stops.map(stopFocusY);
    const y = focusY();

    if (reduceMotion) {
      const d = docks[0];
      place(d.left, d.top, d.w, 1, 0, false);
      return;
    }

    /* Park at first stop */
    if (y <= ys[0]) {
      const d = docks[0];
      place(d.left, d.top, d.w, d.opacity, 0);
      return;
    }

    /* Final park at form — stays */
    if (y >= ys[ys.length - 1]) {
      const d = docks[docks.length - 1];
      place(d.left, d.top, d.w, d.opacity, 0, false);
      return;
    }

    /* Find leg between stop i and i+1 */
    let i = 0;
    for (let n = 0; n < ys.length - 1; n += 1) {
      if (y >= ys[n] && y <= ys[n + 1]) {
        i = n;
        break;
      }
    }

    const yA = ys[i];
    const yB = ys[i + 1];
    const t = clamp((y - yA) / Math.max(yB - yA, 1), 0, 1);
    const from = docks[i];
    const to = docks[i + 1];
    const offRight = window.innerWidth + from.w * 0.15;
    const offLeft = -to.w * 1.05;
    const midY = (from.top + to.top) / 2;

    /*
      0–0.18 park at A
      0.18–0.48 exit right (skip section in between)
      0.48–0.52 invisible teleport
      0.52–0.82 enter from left to B
      0.82–1 park at B
    */
    if (t < 0.18) {
      place(from.left, from.top, from.w, from.opacity, 0);
      return;
    }
    if (t < 0.48) {
      const p = easeInOut((t - 0.18) / 0.3);
      place(
        lerp(from.left, offRight, p),
        lerp(from.top, midY, p * 0.35),
        lerp(from.w, to.w, p * 0.3),
        from.opacity * (1 - p * 0.15),
        p * 520,
      );
      return;
    }
    if (t < 0.52) {
      place(offLeft, midY, to.w, 0, 260, false);
      return;
    }
    if (t < 0.82) {
      const p = easeInOut((t - 0.52) / 0.3);
      place(
        lerp(offLeft, to.left, p),
        lerp(midY, to.top, p),
        lerp(from.w * 0.9, to.w, p),
        to.opacity * (0.35 + p * 0.65),
        (1 - p) * 480,
      );
      return;
    }

    place(to.left, to.top, to.w, to.opacity, 0);
  };

  let raf = 0;
  const loop = () => {
    updateCarDrive();
    raf = requestAnimationFrame(loop);
  };

  if (!reduceMotion) {
    window.addEventListener('pointermove', (e) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      targetParallaxX = nx * -14;
      targetParallaxY = ny * -8;
    }, { passive: true });
    raf = requestAnimationFrame(loop);
    window.addEventListener('pagehide', () => cancelAnimationFrame(raf), { once: true });
  } else {
    updateCarDrive();
    window.addEventListener('scroll', updateCarDrive, { passive: true });
  }

  window.addEventListener('resize', updateCarDrive, { passive: true });

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
