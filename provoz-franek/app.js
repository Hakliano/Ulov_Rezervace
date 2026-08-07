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
  const navCar = document.getElementById('nav-car');
  const road = document.querySelector('.nav-road');

  const spinWheels = (deg) => {
    navCar?.querySelectorAll('.bp-wheel-group').forEach((g) => {
      const wheel = g.querySelector('.bp-wheel');
      const cx = Number(wheel?.getAttribute('cx') || 0);
      const cy = Number(wheel?.getAttribute('cy') || 0);
      g.setAttribute('transform', `rotate(${deg} ${cx} ${cy})`);
    });
  };

  const updateNavCar = () => {
    if (!navCar || !road) return;
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const progress = reduceMotion ? 0 : clamp(window.scrollY / maxScroll, 0, 1);
    const roadW = road.clientWidth;
    const carW = navCar.offsetWidth || 140;
    const travel = Math.max(0, roadW - carW - 24);
    const x = 12 + travel * progress;
    navCar.style.transform = `translate3d(${x.toFixed(1)}px, -50%, 0)`;
    spinWheels(progress * 720);
  };

  updateNavCar();
  window.addEventListener('scroll', updateNavCar, { passive: true });
  window.addEventListener('resize', updateNavCar, { passive: true });

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
