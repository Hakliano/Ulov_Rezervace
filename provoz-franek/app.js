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

  const navCar = document.getElementById('nav-car');
  const track = document.querySelector('.nav-road-track');
  const stopLinks = [...document.querySelectorAll('.nav-stop')];

  const sectionEls = {
    top: document.querySelector('.hero'),
    'o-nas': document.getElementById('o-nas'),
    sluzby: document.getElementById('sluzby'),
    mapa: document.getElementById('mapa'),
    kontakt: document.getElementById('kontakt'),
  };

  const stops = stopLinks
    .map((label) => {
      const key = label.getAttribute('data-stop');
      return { key, label, el: sectionEls[key] };
    })
    .filter((s) => s.el && s.label);

  const spinWheels = (deg) => {
    navCar?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const sectionFocusY = (el) => {
    const r = el.getBoundingClientRect();
    return window.scrollY + r.top + Math.min(r.height * 0.25, 160);
  };

  const labelCenterX = (label) => {
    const lr = label.getBoundingClientRect();
    const tr = track.getBoundingClientRect();
    return lr.left + lr.width / 2 - tr.left;
  };

  const updateNavCar = () => {
    if (!navCar || !track || stops.length < 2) return;

    const focus = window.scrollY + window.innerHeight * 0.28;
    const ys = stops.map((s) => sectionFocusY(s.el));
    const carW = navCar.offsetWidth || 140;

    let i = 0;
    for (; i < ys.length - 1; i += 1) {
      if (focus < ys[i + 1]) break;
    }

    let t = 0;
    let active = 0;
    if (focus <= ys[0]) {
      t = 0;
      active = 0;
      i = 0;
    } else if (focus >= ys[ys.length - 1]) {
      t = 1;
      active = ys.length - 1;
      i = ys.length - 2;
    } else {
      t = clamp((focus - ys[i]) / Math.max(ys[i + 1] - ys[i], 1), 0, 1);
      active = t < 0.5 ? i : i + 1;
    }

    const x0 = labelCenterX(stops[i].label) - carW / 2;
    const x1 = labelCenterX(stops[Math.min(i + 1, stops.length - 1)].label) - carW / 2;
    const x = reduceMotion
      ? labelCenterX(stops[active].label) - carW / 2
      : lerp(x0, x1, t);

    const maxX = Math.max(0, track.clientWidth - carW - 4);
    navCar.style.transform = `translate3d(${clamp(x, 4, maxX).toFixed(1)}px, 0, 0)`;
    spinWheels((reduceMotion ? active / (stops.length - 1) : (i + t) / (stops.length - 1)) * 540);

    stops.forEach((s, idx) => {
      s.label.classList.toggle('is-active', idx === active);
    });
  };

  updateNavCar();
  window.addEventListener('scroll', updateNavCar, { passive: true });
  window.addEventListener('resize', updateNavCar, { passive: true });

  /* Hero auto: scan + odjezd doprava jen uvnitř hero (scroll dolů/nahoru) */
  const hero = document.querySelector('.hero');
  const heroStage = document.getElementById('hero-stage');
  const easeOutCubic = (t) => 1 - (1 - t) ** 3;

  const spinHeroWheels = (deg) => {
    heroStage?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const updateHeroCar = () => {
    if (!hero || !heroStage) return;
    if (reduceMotion) {
      heroStage.style.transform = 'translate3d(0,0,0)';
      heroStage.style.opacity = '1';
      return;
    }
    const r = hero.getBoundingClientRect();
    /* 0 = hero nahoře / viditelné, 1 = hero odscrollované → auto pryč vpravo */
    const raw = clamp(-r.top / Math.max(r.height * 0.7, 1), 0, 1);
    const p = easeOutCubic(raw);
    const travel = Math.max(window.innerWidth * 0.85, heroStage.offsetWidth + 80);
    heroStage.style.transform = `translate3d(${(travel * p).toFixed(1)}px, 0, 0)`;
    heroStage.style.opacity = String(clamp(1 - p * 0.35, 0.4, 1));
    spinHeroWheels(p * 480);
  };

  updateHeroCar();
  window.addEventListener('scroll', updateHeroCar, { passive: true });
  window.addEventListener('resize', updateHeroCar, { passive: true });
  window.setTimeout(() => heroStage?.classList.add('is-drawn'), 2600);

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
