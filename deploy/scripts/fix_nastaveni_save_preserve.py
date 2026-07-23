from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OLD = """$('#form-nastaveni').addEventListener('submit', async (e) => {
  e.preventDefault();
  const storno = $('#nast-storno').value;
  try {
  await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`, {
    method: 'PUT',
    body: JSON.stringify({
      interval_minut: parseInt($('#nast-interval').value, 10),
      min_predstih_hodin: parseInt($('#nast-min-h').value, 10),
      max_predstih_mesicu: parseInt($('#nast-max-m').value, 10),
      storno_do_hodin: storno === '' ? null : parseInt(storno, 10),
      potvrzeni_platnost_hodin: parseInt($('#nast-potvrzeni-h').value, 10) || 24,
      gdpr_zasady_verze: $('#nast-gdpr-verze').value.trim() || '1.0',
      recenze_url: $('#nast-recenze-url').value.trim(),
      notifikace: collectNotifikace(),
    }),
  });
  alert('Nastavení uloženo.');
  loadNastaveni();
  } catch (err) {
    alert(err.message);
  }
});"""

NEW = """$('#form-nastaveni').addEventListener('submit', async (e) => {
  e.preventDefault();
  const storno = $('#nast-storno').value;
  try {
  const current = await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`);
  await api(`/salon/${SALON_ID}/rezervace/admin/nastaveni/`, {
    method: 'PUT',
    body: JSON.stringify({
      ...current,
      interval_minut: parseInt($('#nast-interval').value, 10),
      min_predstih_hodin: parseInt($('#nast-min-h').value, 10),
      max_predstih_mesicu: parseInt($('#nast-max-m').value, 10),
      storno_do_hodin: storno === '' ? null : parseInt(storno, 10),
      potvrzeni_platnost_hodin: parseInt($('#nast-potvrzeni-h').value, 10) || 24,
      gdpr_zasady_verze: $('#nast-gdpr-verze').value.trim() || '1.0',
    }),
  });
  alert('Nastavení uloženo.');
  loadNastaveni();
  } catch (err) {
    alert(err.message);
  }
});"""

n = 0
for p in ROOT.glob('*/rezervace.js'):
    t = p.read_text(encoding='utf-8')
    if OLD not in t:
        print('skip', p.parent.name)
        continue
    p.write_text(t.replace(OLD, NEW), encoding='utf-8')
    n += 1
    print('ok', p.parent.name)
print('done', n)
