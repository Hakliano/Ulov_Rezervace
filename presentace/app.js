const SALON_PORTS = { 1: 5500, 2: 5501, 3: 5502, 4: 5503 };

const host = window.location.hostname;
const isLocal = host === 'localhost' || host === '127.0.0.1';
const API_BASE = isLocal
  ? `http://${host}:8000/api`
  : `${window.location.origin}/api`;

function salonDemoUrl(salonId, page) {
  const port = window.location.port;
  const useSalonPorts = isLocal && port === '5510';

  if (useSalonPorts) {
    const p = SALON_PORTS[salonId];
    return page === 'web'
      ? `http://${host}:${p}/`
      : `http://${host}:${p}/rezervace.html`;
  }
  const base = `../salon${salonId}`;
  return page === 'web' ? `${base}/index.html` : `${base}/rezervace.html`;
}

document.querySelectorAll('[data-demo]').forEach((link) => {
  const salonId = Number(link.dataset.demo);
  const page = link.dataset.page || 'web';
  if (SALON_PORTS[salonId]) {
    link.href = salonDemoUrl(salonId, page);
    link.target = '_blank';
    link.rel = 'noopener';
  }
});

const form = document.getElementById('poptavka-form');
const msg = document.getElementById('form-msg');

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  msg.textContent = 'Odesílám…';
  msg.className = 'form-msg';

  const payload = {
    jmeno: document.getElementById('p-jmeno').value.trim(),
    email: document.getElementById('p-email').value.trim(),
    telefon: document.getElementById('p-telefon').value.trim(),
    salon_nazev: document.getElementById('p-salon').value.trim(),
    zprava: document.getElementById('p-zprava').value.trim(),
    balicek: document.getElementById('p-balicek')?.value.trim() || '',
    souhlas: document.getElementById('p-souhlas').checked,
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
  } catch (err) {
    msg.textContent = err.message;
    msg.className = 'form-msg error';
  }
});
