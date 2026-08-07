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

  /* Jemný parallax blueprintu podle myši — wow bez přetížení */
  const stage = document.querySelector('[data-parallax]');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (stage && !reduceMotion) {
    let raf = 0;
    let targetX = 0;
    let targetY = 0;
    let curX = 0;
    let curY = 0;

    const tick = () => {
      curX += (targetX - curX) * 0.08;
      curY += (targetY - curY) * 0.08;
      stage.style.transform = `translate3d(${curX.toFixed(2)}px, ${curY.toFixed(2)}px, 0)`;
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener('pointermove', (e) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      targetX = nx * -18;
      targetY = ny * -10;
    }, { passive: true });

    raf = requestAnimationFrame(tick);
    window.addEventListener('pagehide', () => cancelAnimationFrame(raf), { once: true });
  }

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
