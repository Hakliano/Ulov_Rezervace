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
  const easeOutCubic = (t) => 1 - (1 - t) ** 3;

  const hero = document.querySelector('.hero');
  const exitStage = document.querySelector('[data-car-exit]');
  const enterStage = document.querySelector('[data-car-enter]');
  const onas = document.getElementById('o-nas');

  let parallaxX = 0;
  let parallaxY = 0;
  let targetParallaxX = 0;
  let targetParallaxY = 0;

  const spinWheels = (stage, deg) => {
    stage?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const updateCarDrive = () => {
    if (!hero || !exitStage || !enterStage || !onas) return;

    if (reduceMotion) {
      exitStage.style.transform = 'translate3d(0,0,0)';
      exitStage.style.opacity = '1';
      enterStage.style.transform = 'translate3d(0,-50%,0)';
      enterStage.style.opacity = '0.55';
      return;
    }

    const heroRect = hero.getBoundingClientRect();
    /* 0 = hero nahoře, 1 = auto už mimo vpravo */
    const exitRaw = clamp(-heroRect.top / Math.max(heroRect.height * 0.72, 1), 0, 1);
    const exitP = easeOutCubic(exitRaw);
    const exitTravel = window.innerWidth * 0.95;
    const exitX = exitTravel * exitP;
    const exitOpacity = clamp(1 - exitP * 1.05, 0, 1);

    parallaxX += (targetParallaxX - parallaxX) * 0.1;
    parallaxY += (targetParallaxY - parallaxY) * 0.1;
    const px = parallaxX * (1 - exitP);
    const py = parallaxY * (1 - exitP);

    exitStage.style.transform = `translate3d(${(exitX + px).toFixed(1)}px, ${py.toFixed(1)}px, 0)`;
    exitStage.style.opacity = exitOpacity.toFixed(3);
    spinWheels(exitStage, exitP * 420);

    const onasRect = onas.getBoundingClientRect();
    /* 0 = ještě mimo / dole, 1 = zaparkováno v bloku O nás */
    const enterRaw = clamp(
      (window.innerHeight * 0.88 - onasRect.top) / Math.max(window.innerHeight * 0.55, 1),
      0,
      1,
    );
    const enterP = easeOutCubic(enterRaw);
    const enterTravel = window.innerWidth * 0.85;
    const enterX = -enterTravel * (1 - enterP);
    const enterOpacity = clamp(enterP * 0.72, 0, 0.72);

    enterStage.style.transform = `translate3d(${enterX.toFixed(1)}px, -50%, 0)`;
    enterStage.style.opacity = enterOpacity.toFixed(3);
    spinWheels(enterStage, enterP * 360);
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
      targetParallaxX = nx * -18;
      targetParallaxY = ny * -10;
    }, { passive: true });
    raf = requestAnimationFrame(loop);
    window.addEventListener('pagehide', () => cancelAnimationFrame(raf), { once: true });
  } else {
    updateCarDrive();
  }

  window.addEventListener('scroll', () => {
    if (reduceMotion) updateCarDrive();
  }, { passive: true });
  window.addEventListener('resize', updateCarDrive, { passive: true });

  /* Scroll reveal služeb / sekcí */
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
