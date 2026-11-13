(function () {
  'use strict';

  const root = document.getElementById('phone-clicker-app');
  if (!root) return;

  const configNode = document.getElementById('phone-clicker-config');
  let config = {};
  if (configNode) {
    try {
      config = JSON.parse(configNode.textContent);
    } catch (_err) {
      config = {};
    }
  }
  const scenarios = config.scenarios || [];
  const snapshotUrlTpl = config.snapshotUrlTemplate || '';
  const defaultAgent = config.defaultAgentName || '';

  const els = {
    prep: root.querySelector('[data-phone-prep]'),
    call: root.querySelector('[data-phone-call]'),
    productCards: root.querySelectorAll('[data-product]'),
    webChips: root.querySelectorAll('[data-web]'),
    styleChips: root.querySelectorAll('[data-sales-style]'),
    agentInput: root.querySelector('[data-agent-name]'),
    btnPrepare: root.querySelector('[data-btn-prepare]'),
    btnStart: root.querySelector('[data-btn-start]'),
    status: root.querySelector('[data-prepare-status]'),
    sayText: root.querySelector('[data-say-text]'),
    goalNote: root.querySelector('[data-goal-note]'),
    answers: root.querySelector('[data-answers]'),
    metaBar: root.querySelector('[data-meta-bar]'),
    btnBack: root.querySelector('[data-btn-back]'),
    btnObjections: root.querySelector('[data-btn-objections]'),
    btnCopy: root.querySelector('[data-btn-copy]'),
    btnNewCall: root.querySelector('[data-btn-new]'),
    areaSelect: root.querySelector('[data-area-select]'),
    btnAreaJump: root.querySelector('[data-btn-area]'),
    overlay: root.querySelector('[data-overlay]'),
    objectionList: root.querySelector('[data-objection-list]'),
    objectionView: root.querySelector('[data-objection-view]'),
    objectionTitle: root.querySelector('[data-objection-title]'),
    objectionResponses: root.querySelector('[data-objection-responses]'),
    btnCloseOverlay: root.querySelector('[data-close-overlay]'),
    btnObjectionBack: root.querySelector('[data-objection-back]'),
    scenarioField: root.querySelector('[data-scenario-field]'),
    versionField: root.querySelector('[data-version-field]'),
    scenarioSelect: root.querySelector('[data-scenario-select]'),
    versionSelect: root.querySelector('[data-version-select]'),
    manageLink: root.querySelector('[data-manage-link]'),
  };

  const state = {
    product: null,
    scenarioId: null,
    versionId: null,
    webStatus: null,
    salesStyle: null,
    agentName: defaultAgent,
    scriptSlug: null,
    payload: null,
    steps: new Map(),
    areas: new Map(),
    branchKey: null,
    currentStepId: null,
    stepStack: [],
    returnAfterObjection: null,
    inObjectionFlow: false,
    prepared: false,
  };

  function selectChip(group, el, attrName) {
    group.forEach((node) => node.classList.toggle('is-selected', node === el));
    return el.getAttribute(attrName) || '';
  }

  if (els.manageLink && config.manageUrl) {
    els.manageLink.href = config.manageUrl;
    els.manageLink.hidden = false;
  }

  function scenariosForProduct(product) {
    return scenarios.filter((s) => s.product === product);
  }

  function selectedScenario() {
    return scenarios.find((s) => String(s.id) === String(state.scenarioId));
  }

  function populateScenarios() {
    if (!els.scenarioSelect) return;
    const list = scenariosForProduct(state.product);
    els.scenarioSelect.innerHTML = '';
    list.forEach((sc) => {
      const opt = document.createElement('option');
      opt.value = String(sc.id);
      opt.textContent = sc.name + (sc.isActive ? '' : ' (neaktivní)');
      els.scenarioSelect.appendChild(opt);
    });
    if (els.scenarioField) els.scenarioField.hidden = list.length === 0;
    if (list.length === 1) {
      state.scenarioId = list[0].id;
      els.scenarioSelect.value = String(state.scenarioId);
    } else if (config.preselectScriptId && list.some((s) => s.id === config.preselectScriptId)) {
      state.scenarioId = config.preselectScriptId;
      els.scenarioSelect.value = String(state.scenarioId);
    } else {
      state.scenarioId = list[0]?.id || null;
      if (state.scenarioId) els.scenarioSelect.value = String(state.scenarioId);
    }
    populateVersions();
  }

  function populateVersions() {
    if (!els.versionSelect) return;
    const sc = selectedScenario();
    const versions = sc?.versions || [];
    els.versionSelect.innerHTML = '';
    versions.forEach((ver) => {
      const opt = document.createElement('option');
      opt.value = String(ver.id);
      let label = `v${ver.number}`;
      if (ver.statusLabel) label += ` — ${ver.statusLabel}`;
      if (ver.isCurrent) label += ' (aktuální)';
      opt.textContent = label;
      if (ver.isDefault) opt.selected = true;
      els.versionSelect.appendChild(opt);
    });
    if (els.versionField) els.versionField.hidden = versions.length === 0;
    const defaultVer = versions.find((v) => v.isDefault) || versions[0];
    if (config.preselectVersionId && versions.some((v) => v.id === config.preselectVersionId)) {
      state.versionId = config.preselectVersionId;
      els.versionSelect.value = String(state.versionId);
    } else if (defaultVer) {
      state.versionId = defaultVer.id;
      els.versionSelect.value = String(state.versionId);
    } else {
      state.versionId = null;
    }
    if (sc) state.scriptSlug = sc.slug;
  }

  els.scenarioSelect?.addEventListener('change', () => {
    state.scenarioId = els.scenarioSelect.value;
    populateVersions();
    resetPrepared();
  });

  els.versionSelect?.addEventListener('change', () => {
    state.versionId = els.versionSelect.value;
    resetPrepared();
  });

  els.productCards.forEach((card) => {
    card.addEventListener('click', () => {
      state.product = selectChip(els.productCards, card, 'data-product');
      populateScenarios();
      resetPrepared();
    });
  });

  els.styleChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      state.salesStyle = selectChip(els.styleChips, chip, 'data-sales-style');
      resetPrepared();
    });
  });

  els.webChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      state.webStatus = selectChip(els.webChips, chip, 'data-web');
      resetPrepared();
    });
  });

  if (els.agentInput) {
    els.agentInput.value = defaultAgent;
    els.agentInput.addEventListener('input', () => {
      state.agentName = els.agentInput.value.trim();
    });
  }

  function resetPrepared() {
    state.prepared = false;
    state.payload = null;
    state.steps = new Map();
    if (els.btnStart) els.btnStart.disabled = true;
    if (els.status) {
      els.status.hidden = true;
      els.status.className = 'phone-status';
    }
  }

  function branchKey() {
    return `${state.webStatus}_${state.salesStyle}`;
  }

  function setStatus(text, kind) {
    if (!els.status) return;
    els.status.hidden = false;
    els.status.textContent = text;
    els.status.className = `phone-status ${kind}`;
  }

  function indexPayload(data) {
    state.payload = data;
    state.steps = new Map(Object.entries(data.steps || {}));
    state.areas = new Map(Object.entries(data.areas || {}));
  }

  function applyAgentName(text) {
    const name = state.agentName || 'kolega';
    return (text || '').replaceAll('{agent_name}', name);
  }

  function renderStep(stepId) {
    const step = state.steps.get(stepId);
    if (!step) {
      setStatus('Chybějící krok ve scénáři.', 'err');
      return;
    }
    state.currentStepId = stepId;
    if (els.sayText) els.sayText.textContent = applyAgentName(step.say);
    if (els.goalNote) {
      const goal = (step.goal || '').trim();
      els.goalNote.hidden = !goal;
      els.goalNote.textContent = goal ? `Cíl otázky: ${goal}` : '';
    }
    if (els.metaBar && state.payload?.meta) {
      els.metaBar.textContent = `${state.payload.meta.name} · v${state.payload.meta.version} · krok ${stepId}`;
    }
    if (!els.answers) return;
    els.answers.innerHTML = '';
    (step.answers || []).forEach((ans) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'phone-answer-btn';
      btn.textContent = ans.label;
      btn.addEventListener('click', () => onAnswer(ans));
      els.answers.appendChild(btn);
    });
  }

  function onAnswer(ans) {
    if (ans.endCall) {
      renderStep(state.currentStepId);
      if (els.sayText) {
        els.sayText.textContent =
          'Děkuji za váš čas. Přeji hezký den a na shledanou.';
      }
      if (els.answers) els.answers.innerHTML = '';
      return;
    }
    if (ans.jumpAreaSlug) {
      const area = state.areas.get(ans.jumpAreaSlug);
      if (area?.entryStepId) {
        state.stepStack.push(state.currentStepId);
        renderStep(area.entryStepId);
      }
      return;
    }
    if (ans.targetStepId) {
      state.stepStack.push(state.currentStepId);
      renderStep(ans.targetStepId);
    }
  }

  function populateAreas() {
    if (!els.areaSelect || !state.payload) return;
    els.areaSelect.innerHTML = '';
    const sorted = [...state.areas.values()].sort((a, b) => a.sortOrder - b.sortOrder);
    sorted.forEach((area) => {
      const opt = document.createElement('option');
      opt.value = area.slug;
      opt.textContent = area.name;
      els.areaSelect.appendChild(opt);
    });
  }

  function populateObjections() {
    if (!els.objectionList || !state.payload) return;
    els.objectionList.innerHTML = '';
    const items = Object.values(state.payload.objections || {}).sort(
      (a, b) => a.sortOrder - b.sortOrder,
    );
    items.forEach((obj) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'phone-answer-btn';
      btn.textContent = obj.title;
      btn.addEventListener('click', () => openObjection(obj));
      els.objectionList.appendChild(btn);
    });
  }

  function openOverlay() {
    state.returnAfterObjection = state.currentStepId;
    state.inObjectionFlow = false;
    if (els.objectionView) els.objectionView.hidden = true;
    if (els.objectionList) els.objectionList.hidden = false;
    if (els.overlay) els.overlay.hidden = false;
    populateObjections();
  }

  function closeOverlay() {
    if (els.overlay) els.overlay.hidden = true;
    if (!state.inObjectionFlow && state.returnAfterObjection) {
      renderStep(state.returnAfterObjection);
    }
    state.inObjectionFlow = false;
  }

  function openObjection(obj) {
    state.inObjectionFlow = true;
    if (els.objectionList) els.objectionList.hidden = true;
    if (els.objectionView) els.objectionView.hidden = false;
    if (els.objectionTitle) els.objectionTitle.textContent = obj.title;
    if (!els.objectionResponses) return;
    els.objectionResponses.innerHTML = '';

    if (obj.rootStepId && state.steps.has(obj.rootStepId)) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'phone-answer-btn';
      btn.textContent = 'Otevřít navazující otázky';
      btn.addEventListener('click', () => {
        closeOverlay();
        state.stepStack.push(state.currentStepId);
        renderStep(obj.rootStepId);
      });
      els.objectionResponses.appendChild(btn);
    }

    (obj.responses || []).forEach((resp) => {
      const wrap = document.createElement('div');
      wrap.className = 'phone-objection-response';
      const p = document.createElement('p');
      p.className = 'phone-say-text';
      p.style.fontSize = '1.1rem';
      p.textContent = applyAgentName(resp.say);
      wrap.appendChild(p);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn secondary';
      if (resp.hardReject) {
        btn.textContent = 'Ukončit hovor';
        btn.addEventListener('click', () => {
          closeOverlay();
          if (els.sayText) {
            els.sayText.textContent =
              'Rozumím, děkuji. Už vás nebudu kontaktovat. Hezký den.';
          }
          if (els.answers) els.answers.innerHTML = '';
        });
      } else if (resp.targetStepId) {
        btn.textContent = 'Pokračovat v rozhovoru';
        btn.addEventListener('click', () => {
          closeOverlay();
          state.stepStack.push(state.currentStepId);
          renderStep(resp.targetStepId);
        });
      } else {
        btn.textContent = 'Zpět k rozhovoru';
        btn.addEventListener('click', () => closeOverlay());
      }
      wrap.appendChild(btn);
      els.objectionResponses.appendChild(wrap);
    });
  }

  els.btnPrepare?.addEventListener('click', async () => {
    if (!state.product || !state.scenarioId || !state.versionId) {
      setStatus('Vyberte produkt, scénář a verzi.', 'err');
      return;
    }
    if (!state.webStatus || !state.salesStyle) {
      setStatus('Vyberte stav webu a styl prodeje.', 'err');
      return;
    }
    if (!state.versionId) {
      setStatus('Vyberte scénář a verzi.', 'err');
      return;
    }
    const url = snapshotUrlTpl.replace('__VERSION_ID__', encodeURIComponent(String(state.versionId)));
    setStatus('Načítám scénář…', 'wait');
    els.btnPrepare.disabled = true;
    try {
      const res = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('fetch-failed');
      const data = await res.json();
      indexPayload(data);
      const key = branchKey();
      const entry = data.initialBranches?.[key];
      if (!entry) {
        throw new Error('missing-branch');
      }
      state.branchKey = key;
      state.entryStepId = entry;
      state.prepared = true;
      populateAreas();
      setStatus(`Scénář připraven (větev ${key} → krok ${entry})`, 'ok');
      if (els.btnStart) els.btnStart.disabled = false;
    } catch (e) {
      const msg =
        e.message === 'missing-branch'
          ? `Scénář neobsahuje větev ${branchKey()}.`
          : 'Scénář se nepodařilo načíst. Zkuste to znovu.';
      setStatus(msg, 'err');
      resetPrepared();
    } finally {
      els.btnPrepare.disabled = false;
    }
  });

  els.btnStart?.addEventListener('click', () => {
    if (!state.prepared || !state.entryStepId) return;
    state.stepStack = [];
    if (els.prep) els.prep.classList.add('is-hidden');
    if (els.call) els.call.hidden = false;
    renderStep(state.entryStepId);
  });

  els.btnBack?.addEventListener('click', () => {
    const prev = state.stepStack.pop();
    if (prev) renderStep(prev);
  });

  els.btnCopy?.addEventListener('click', async () => {
    const step = state.steps.get(state.currentStepId);
    if (!step) return;
    const text = applyAgentName(step.say);
    try {
      await navigator.clipboard.writeText(text);
    } catch (_e) {
      /* ignore */
    }
  });

  els.btnObjections?.addEventListener('click', openOverlay);
  els.btnCloseOverlay?.addEventListener('click', closeOverlay);
  els.btnObjectionBack?.addEventListener('click', () => {
    if (els.objectionView) els.objectionView.hidden = true;
    if (els.objectionList) els.objectionList.hidden = false;
    state.inObjectionFlow = false;
  });

  els.btnAreaJump?.addEventListener('click', () => {
    const slug = els.areaSelect?.value;
    const area = slug ? state.areas.get(slug) : null;
    if (area?.entryStepId) {
      state.stepStack.push(state.currentStepId);
      renderStep(area.entryStepId);
    }
  });

  els.btnNewCall?.addEventListener('click', () => {
    if (!window.confirm('Opravdu začít nový hovor? Aktuální pozice se ztratí.')) return;
    if (els.call) els.call.hidden = true;
    if (els.prep) els.prep.classList.remove('is-hidden');
    resetPrepared();
    state.stepStack = [];
    state.currentStepId = null;
  });
})();
