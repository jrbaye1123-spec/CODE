/* ============================================================
   matrAIx OS — evaluation portal
   - Hundreds of simulated agents evaluate the selected app
   - A few "in-focus" agents step through the flow slowly so you
     can actually follow a trajectory
   - Background agents complete continuously to drive the reports
   - Neural Eval Core brain pulses the region each behavior stresses
   ============================================================ */

(() => {
  const DIM = (window.MATRAIX_DIMENSIONS && window.MATRAIX_DIMENSIONS.dimensions) || [];
  const byId = Object.fromEntries(DIM.map(d => [d.id, d]));
  const fmt = new Intl.NumberFormat('en-US');
  const compactFmt = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = s => document.querySelector(s);
  const clamp01 = x => (x < 0 ? 0 : x > 1 ? 1 : x);
  const pick = a => a[(Math.random() * a.length) | 0];
  const pad = (n, w) => String(n).padStart(w, '0');
  const randomAgentScale = () => Math.round(10 ** (Math.log10(2300) + Math.random() * (Math.log10(5.6e9) - Math.log10(2300))));

  /* ---------- shared-site mobile navigation ---------- */
  const playgroundMenu = $('.os-menu');
  const playgroundNav = $('.os-nav');
  const closePlaygroundMenu = () => {
    if (!playgroundMenu || !playgroundNav) return;
    playgroundNav.classList.remove('open');
    playgroundMenu.setAttribute('aria-expanded', 'false');
  };
  if (playgroundMenu && playgroundNav) {
    playgroundMenu.addEventListener('click', () => {
      const open = playgroundNav.classList.toggle('open');
      playgroundMenu.setAttribute('aria-expanded', String(open));
    });
    playgroundNav.addEventListener('click', event => {
      if (event.target.closest('a')) closePlaygroundMenu();
    });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || !playgroundNav.classList.contains('open')) return;
      closePlaygroundMenu();
      playgroundMenu.focus();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 860) closePlaygroundMenu();
    });
  }

  /* ---------- persona sampling (subset of the canonical dimension space) ---------- */
  const KEY = ['age_bracket', 'region', 'primary_language', 'english_proficiency', 'intent',
    'device_context', 'expertise_gap', 'safety_sensitivity', 'trust_level', 'query_complexity',
    'emotional_state', 'prior_context'];
  const PENALTY = {
    query_complexity:   { 'Adversarial': 0.40, 'Ambiguous / underspecified': 0.18, 'Open-ended creative': 0.09, 'Multi-step': 0.04 },
    safety_sensitivity: { 'Potentially harmful': 0.45, 'Dual-use': 0.28, 'High-stakes (medical/legal/financial)': 0.14, 'Sensitive personal': 0.06 },
    trust_level:        { 'Hostile': 0.24, 'Skeptical': 0.08 },
    english_proficiency:{ 'None': 0.26, 'Basic (A1–A2)': 0.12, 'Intermediate (B1–B2)': 0.04 },
    expertise_gap:      { 'Expert testing the system': 0.10, 'Teaching the model': 0.03 },
    emotional_state:    { 'Frustrated': 0.06, 'Anxious': 0.04, 'Urgent': 0.05 },
    device_context:     { 'Low-bandwidth': 0.10, 'Mobile, on-the-go': 0.05, 'Accessibility tool': 0.06 },
  };
  function samplePersona() {
    const p = {};
    KEY.forEach(k => { if (byId[k]) p[k] = pick(byId[k].values); });
    return p;
  }
  function personaPenalty(p) {
    const hits = [];
    for (const k in PENALTY) if (PENALTY[k][p[k]]) hits.push(PENALTY[k][p[k]]);
    if (!hits.length) return 0;
    const mx = Math.max(...hits);
    return mx + 0.18 * (hits.reduce((a, b) => a + b, 0) - mx);
  }
  const personaLabel = p => `${p.age_bracket} · ${p.region} · ${p.primary_language} · ${p.intent}`;
  function regionFor(p) {
    if (PENALTY.safety_sensitivity[p.safety_sensitivity]) return 'Safety';
    if (PENALTY.query_complexity[p.query_complexity]) return 'Reasoning';
    if (p.intent === 'Decide' || p.intent === 'Get task done') return 'Planning';
    if (PENALTY.english_proficiency[p.english_proficiency]) return 'Language';
    if (p.prior_context === 'Long ongoing project' || p.prior_context === 'Returning user') return 'Memory';
    return 'Perception';
  }
  const TELEMETRY = {
    Survey: {
      meta: 'question → response → score',
      actions: ['read question', 'compare choices', 'select response', 'revise response', 'add explanation', 'skip question', 'submit survey'],
      micro: ['re-reads the question', 'hesitates between choices', 'checks prior response', 'adds context'],
    },
    Chatbot: {
      meta: 'prompt → reply → score',
      actions: ['send prompt', 'read reply', 'ask follow-up', 'clarify constraint', 'check citation', 'request revision', 'rate reply'],
      micro: ['rephrases the request', 'checks the answer', 'adds a constraint', 'waits for reply'],
    },
    Website: {
      meta: 'page → interaction → outcome',
      actions: ['scan page', 'follow link', 'search', 'open details', 'compare options', 'scroll', 'go back', 'confirm choice'],
      micro: ['scans the page', 'checks navigation', 'waits for load', 'compares options'],
    },
    App: {
      meta: 'screen → gesture → outcome',
      actions: ['inspect screen', 'tap control', 'swipe', 'enter value', 'open menu', 'dismiss dialog', 'confirm action', 'go back'],
      micro: ['checks the screen', 'hesitates before tapping', 'waits for update', 'reviews the result'],
    },
  };
  const taskNature = t => (t.url.split(' · ')[0] || 'Website');
  const telemetryFor = t => TELEMETRY[taskNature(t)] || TELEMETRY.Website;

  /* ---------- targets (apps/websites under evaluation) ---------- */
  const TARGETS = [
    { id: 'candy-land-price', url: 'Survey · Commerce', label: 'Candy Land price sensitivity',
      blurb: 'Tests how price changes affect purchase intent across different shopper segments.',
      scoreLabels: ['Would not buy', 'Would buy Candy Land'],
      personaFolder: 'Type 1 - Survey/survey_price-sensitivity-hasbro-gaming-candy-land/Persona Profiles', personaFiles: ['persona_0001.yaml','persona_0002.yaml','persona_0003.yaml','persona_0004.yaml','persona_0005.yaml','persona_0006.yaml','persona_0007.yaml','persona_0008.yaml','persona_0009.yaml','persona_0010.yaml','persona_0011.yaml','persona_0012.yaml'],
      steps: ['review product context', 'compare price points', 'state purchase intent', 'explain price sensitivity', 'submit survey'],
      report: { a: 'Current price', b: 'Proposed price', winner: 'A', lift: '+12.0%', metric: 'purchase intent', agents: 0,
        segments: [['Parents', 72, 61], ['Gift buyers', 68, 57], ['Teachers', 64, 55], ['Price-sensitive households', 59, 41]],
        findings: [['high', 'Price-sensitive households show the largest decline at the proposed price.'], ['med', 'Gift buyers tolerate a smaller increase when the product is bundled.'], ['low', 'Brand familiarity moderates the decline in purchase intent.']] } },
    { id: 'annual-checkup', url: 'Survey · Healthcare', label: 'Annual checkup habits',
      blurb: 'Measures which barriers and reminders influence people to schedule an annual checkup.',
      scoreLabels: ['Would not book', 'Would book a checkup'],
      personaFolder: 'Type 1 - Survey/survey_annual-checkup-habits/Persona Profiles', personaFiles: ['persona_0002.yaml','persona_0003.yaml','persona_0004.yaml','persona_0005.yaml','persona_0006.yaml','persona_0007.yaml','persona_0008.yaml','persona_0009.yaml','persona_0010.yaml','persona_0011.yaml','persona_0012.yaml','persona_0013.yaml'],
      steps: ['review health context', 'report checkup frequency', 'identify barriers', 'evaluate reminder', 'state booking intent'],
      report: { a: 'General reminder', b: 'Personalized planning', winner: 'B', lift: '+16.0%', metric: 'booking intent', agents: 0,
        segments: [['Regular patients', 74, 86], ['Care avoiders', 38, 57], ['Uninsured', 31, 43], ['Rural patients', 45, 61]],
        findings: [['high', 'Cost and access remain the dominant barriers for uninsured personas.'], ['med', 'Personalized next steps improve intent most among care avoiders.'], ['low', 'Reminder timing matters more for parents and caregivers.']] } },
    { id: 'meal-planning', url: 'Chatbot · Healthcare', label: 'Meal planning nutrition assistant',
      blurb: 'Evaluates whether meal plans are useful, safe, and tailored to dietary constraints.',
      scoreLabels: ['Unhelpful or unsafe', 'Useful and safe plan'],
      personaFolder: 'Type 2 - Chatbot/meal-planning-nutrition_chatbot/Persona Profiles', personaFiles: ['persona_0001.yaml','persona_0002.yaml','persona_0003.yaml','persona_0004.yaml','persona_0005.yaml','persona_0006.yaml','persona_0007.yaml','persona_0008.yaml','persona_0009.yaml','persona_0010.yaml','persona_0011.yaml','persona_0012.yaml'],
      steps: ['describe dietary goals', 'share restrictions', 'review meal plan', 'request substitution', 'rate usefulness'],
      report: { a: 'Generic assistant', b: 'Persona-aware assistant', winner: 'B', lift: '+21.0%', metric: 'useful safe plans', agents: 0,
        segments: [['Budget constrained', 58, 82], ['Food allergies', 61, 89], ['Busy households', 67, 86], ['Fitness focused', 73, 88]],
        findings: [['high', 'Generic plans violate at least one stated constraint for allergy personas.'], ['med', 'Budget-aware substitutions drive the largest usefulness gain.'], ['low', 'Short preparation steps improve completion for busy households.']] } },
    { id: 'openbb-corporate-action', url: 'Chatbot · Finance', label: 'OpenBB corporate action',
      blurb: 'Checks whether financial answers explain corporate actions accurately and cite reliable sources.',
      scoreLabels: ['Incorrect or unsupported', 'Accurate and sourced'],
      personaFolder: 'Type 2 - Chatbot/chat-openbb-corporate-action/Persona Profiles', personaFiles: ['persona_0001.yaml','persona_0002.yaml','persona_0003.yaml','persona_0004.yaml','persona_0005.yaml','persona_0006.yaml','persona_0007.yaml','persona_0008.yaml','persona_0009.yaml','persona_0010.yaml','persona_0011.yaml','persona_0012.yaml'],
      steps: ['enter ticker', 'inspect missing quote', 'request delisting explanation', 'verify sources', 'summarize status'],
      report: { a: 'Quote-only response', b: 'Source-grounded research', winner: 'B', lift: '+28.0%', metric: 'research accuracy', agents: 0,
        segments: [['Retail investors', 52, 84], ['Analysts', 63, 91], ['Finance students', 48, 83], ['Low expertise', 41, 76]],
        findings: [['high', 'Unsupported responses frequently confuse corporate actions with temporary data gaps.'], ['med', 'Source citations sharply improve trust among analysts.'], ['low', 'Plain-language corporate-action explanations help low-expertise users.']] } },
    { id: 'notion-plans', url: 'Website · Software', label: 'Notion plan comparison',
      blurb: 'Tests whether users can understand plan differences and choose the right subscription.',
      scoreLabels: ['Rejects Notion plan', 'Chooses the right plan'],
      personaFolder: 'Type 3 - Website/web-notion-plan-comparison/Persona Profiles', personaFiles: ['persona_0002.yaml','persona_0038.yaml','persona_0056.yaml','persona_0091.yaml','persona_0109.yaml','persona_0130.yaml','persona_0131.yaml','persona_0164.yaml','persona_0170.yaml','persona_0176.yaml','persona_0189.yaml','persona_0231.yaml'],
      steps: ['open pricing page', 'compare plan features', 'check limits', 'match plan to needs', 'confirm choice'],
      report: { a: 'Comparison table', b: 'Guided recommendation', winner: 'B', lift: '+14.0%', metric: 'correct plan choice', agents: 0,
        segments: [['Individuals', 78, 89], ['Small teams', 67, 86], ['Enterprise admins', 71, 84], ['First-time users', 55, 79]],
        findings: [['high', 'First-time users misread guest and member limits in the comparison table.'], ['med', 'Guided questions reduce over-purchasing among individuals.'], ['low', 'Security details remain difficult to find for enterprise admins.']] } },
    { id: 'mit-ocw-choice', url: 'Website · Education', label: 'MIT OpenCourseWare course choice',
      blurb: 'Evaluates how easily learners can find a suitable course for their goals and background.',
      scoreLabels: ['Unsuitable course', 'Suitable course selected'],
      personaFolder: 'Type 3 - Website/web-playwright-mit-ocw-course-choice/Persona Profiles', personaFiles: ['persona_0006.yaml','persona_0007.yaml','persona_0011.yaml','persona_0016.yaml','persona_0019.yaml','persona_0021.yaml','persona_0024.yaml','persona_0030.yaml','persona_0032.yaml','persona_0037.yaml','persona_0039.yaml','persona_0043.yaml'],
      steps: ['state learning goal', 'search course catalog', 'compare prerequisites', 'inspect materials', 'choose course'],
      report: { a: 'Catalog search', b: 'Goal-guided shortlist', winner: 'B', lift: '+19.0%', metric: 'suitable course choice', agents: 0,
        segments: [['High-school learners', 49, 76], ['University students', 68, 85], ['Professionals', 61, 82], ['Non-native English', 54, 79]],
        findings: [['high', 'Prerequisite language causes the most mismatches for early learners.'], ['med', 'Goal-guided shortlists reduce time to a suitable course.'], ['low', 'Material-format filters matter most to working professionals.']] } },
    { id: 'news-plus', url: 'App · Software', label: 'News+ subscription decision',
      blurb: 'Tests whether the offer communicates content, trial terms, and subscription value clearly.',
      scoreLabels: ['Declines News+', 'Subscribes to News+'],
      personaFolder: 'Type 4 - App/pg-os-app-ios-news-subscription-decision/Persona Profiles', personaFiles: ['persona_0005.yaml','persona_0010.yaml','persona_0019.yaml','persona_0025.yaml','persona_0038.yaml','persona_0050.yaml','persona_0054.yaml','persona_0062.yaml','persona_0086.yaml','persona_0095.yaml','persona_0097.yaml','persona_0100.yaml'],
      steps: ['open subscription offer', 'review included publications', 'inspect trial terms', 'compare value', 'make decision'],
      report: { a: 'Standard offer', b: 'Personalized content preview', winner: 'B', lift: '+11.0%', metric: 'informed subscription intent', agents: 0,
        segments: [['Daily readers', 73, 87], ['Occasional readers', 42, 58], ['Existing subscribers', 65, 77], ['Price-sensitive users', 36, 49]],
        findings: [['high', 'Trial-renewal terms are missed by many occasional readers.'], ['med', 'Relevant publication previews improve perceived value.'], ['low', 'Price-sensitive users prefer annual savings stated in absolute dollars.']] } },
    { id: 'stocks-sentiment', url: 'App · Finance', label: 'Stocks sentiment',
      blurb: 'Measures whether users interpret market sentiment correctly when context and risk cues are provided.',
      scoreLabels: ['Misreads sentiment', 'Interprets it correctly'],
      personaFolder: 'Type 4 - App/pg-os-app-macos-stocks-mu-sentiment/Persona Profiles', personaFiles: ['persona_0001.yaml','persona_0004.yaml','persona_0005.yaml','persona_0008.yaml','persona_0011.yaml','persona_0012.yaml','persona_0027.yaml','persona_0030.yaml','persona_0051.yaml','persona_0053.yaml','persona_0066.yaml','persona_0093.yaml'],
      steps: ['select stock', 'review sentiment signal', 'inspect source context', 'assess confidence', 'state intended action'],
      report: { a: 'Raw sentiment score', b: 'Sentiment with context', winner: 'B', lift: '+23.0%', metric: 'correct interpretation', agents: 0,
        segments: [['Beginner investors', 44, 76], ['Long-term investors', 63, 84], ['Active traders', 72, 89], ['Risk-averse users', 51, 81]],
        findings: [['high', 'Beginners often interpret an unexplained score as investment advice.'], ['med', 'Source context improves calibration across every segment.'], ['low', 'Risk warnings are most effective beside the sentiment label.']] } },
  ];
  TARGETS.forEach(t => { t.agentScale = randomAgentScale(); t.report.agents = t.agentScale; });
  window.MATRAIX_TASK_AGENT_COUNTS = Object.fromEntries(TARGETS.map(t => [t.id, t.agentScale]));

  // Each task begins with three metrics matched to what it is actually evaluating.
  // Users can add any catalog or custom metric after these defaults.
  const TASK_METRICS = {
    'candy-land-price': [
      ['Purchase intent', 'likelihood of buying at the shown price', 0.74],
      ['Price sensitivity', 'response to the proposed price change', 0.68],
      ['Value perception', 'perceived value relative to price', 0.72],
    ],
    'annual-checkup': [
      ['Scheduling intent', 'likelihood of booking an annual checkup', 0.81],
      ['Access barriers', 'cost, availability, and convenience barriers', 0.76],
      ['Reminder effectiveness', 'response to the proposed reminder', 0.84],
    ],
    'meal-planning': [
      ['Dietary safety', 'avoids allergens and unsafe recommendations', 0.94],
      ['Constraint adherence', 'respects diet, budget, and time constraints', 0.87],
      ['Plan usefulness', 'produces a practical, usable meal plan', 0.89],
    ],
    'openbb-corporate-action': [
      ['Factual accuracy', 'identifies the corporate action correctly', 0.91],
      ['Source grounding', 'supports claims with reliable evidence', 0.88],
      ['Uncertainty calibration', 'separates verified facts from uncertainty', 0.86],
    ],
    'notion-plans': [
      ['Plan fit', 'matches the selected plan to user needs', 0.90],
      ['Feature comprehension', 'understands limits and plan differences', 0.85],
      ['Price-value alignment', 'balances required features against cost', 0.87],
    ],
    'mit-ocw-choice': [
      ['Course-goal fit', 'matches the course to the learner goal', 0.89],
      ['Prerequisite match', 'aligns prerequisites with learner background', 0.84],
      ['Navigation effort', 'finds and compares courses efficiently', 0.82],
    ],
    'news-plus': [
      ['Offer comprehension', 'understands what the subscription includes', 0.88],
      ['Subscription value', 'judges content value against the price', 0.79],
      ['Renewal-term clarity', 'understands trial and renewal terms', 0.83],
    ],
    'stocks-sentiment': [
      ['Sentiment comprehension', 'interprets the market signal correctly', 0.86],
      ['Risk calibration', 'does not treat sentiment as guaranteed advice', 0.84],
      ['Decision confidence', 'reports appropriately calibrated confidence', 0.81],
    ],
  };

  /* ============================================================
     NEURAL EVAL CORE — skill flow chart
     Each scored behavior flows through the skill it stressed.
     Same public interface as before: { pulse(region, verdict) }.
     ============================================================ */
  const Brain = (() => {
    const wrap = $('#flowNodes');
    const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const keyOf = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    // Editable evaluation metrics — users start from these defaults and add their own.
    // [name, description, target pass-rate]
    const DEFAULTS = TASK_METRICS[TARGETS[0].id];
    const metrics = [];
    const byKey = {};

    const make = (name, desc, base) => ({
      name, desc: desc || 'custom metric',
      base: base == null ? (0.6 + Math.random() * 0.32) : base,
      weight: 0.6 + Math.random() * 0.8, total: 0, pass: 0, el: null, bar: null, n: null, t: null,
    });

    function render() {
      wrap.innerHTML = '';
      metrics.forEach(m => {
        const el = document.createElement('div');
        el.className = 'fnode'; el.dataset.r = m.name;
        el.innerHTML =
          '<div class="fn-top"><span class="fn-name">' + esc(m.name) + '</span>' +
          '<span class="fn-meta"><span class="fn-n"><b>' + (m.total > 999 ? (m.total / 1000).toFixed(1) + 'k' : m.total) + '</b> scored</span>' +
          '<button class="fn-x" type="button" title="Remove metric" aria-label="Remove ' + esc(m.name) + '">✕</button></span></div>' +
          '<div class="fn-sub">' + esc(m.desc) + '</div>' +
          '<i class="fn-bar"><b></b></i>';
        wrap.appendChild(el);
        m.el = el; m.bar = el.querySelector('.fn-bar b'); m.n = el.querySelector('.fn-n b');
        if (m.total) m.bar.style.width = Math.round(m.pass / m.total * 100) + '%';
        el.querySelector('.fn-x').addEventListener('click', () => removeMetric(m.name));
      });
      wrap.classList.toggle('lone', metrics.length <= 1);
    }

    function addMetric(name) {
      name = String(name || '').trim();
      const k = keyOf(name);
      if (!k || byKey[k]) return false;
      const m = make(name); byKey[k] = m; metrics.push(m); render(); return true;
    }
    function removeMetric(name) {
      if (metrics.length <= 1) return;
      const k = keyOf(name), i = metrics.findIndex(m => keyOf(m.name) === k);
      if (i < 0) return;
      delete byKey[k]; metrics.splice(i, 1); render();
    }
    function setMetrics(defaults) {
      metrics.length = 0;
      Object.keys(byKey).forEach(k => delete byKey[k]);
      defaults.forEach(d => {
        const m = make(d[0], d[1], d[2]);
        byKey[keyOf(d[0])] = m;
        metrics.push(m);
      });
      render();
    }
    function pick() {
      let sum = 0; for (const m of metrics) sum += m.weight;
      let r = Math.random() * sum;
      for (const m of metrics) { r -= m.weight; if (r <= 0) return m; }
      return metrics[metrics.length - 1];
    }

    function pulse(verdict) {
      if (!metrics.length) return;
      const m = pick();
      m.total++;
      let passed = Math.random() < m.base;                 // each metric stabilises around its own rate
      if (verdict === 'fail' && Math.random() < 0.5) passed = false;
      if (passed) m.pass++;
      m.n.textContent = m.total > 999 ? (m.total / 1000).toFixed(1) + 'k' : m.total;
      m.bar.style.width = Math.round(m.pass / m.total * 100) + '%';
      m.el.classList.remove('watch', 'fail');
      if (!passed) m.el.classList.add(verdict === 'fail' ? 'fail' : 'watch');
      m.el.classList.add('hot');
      clearTimeout(m.t);
      m.t = setTimeout(() => m.el.classList.remove('hot'), 520);
    }

    DEFAULTS.forEach(d => { const m = make(d[0], d[1], d[2]); byKey[keyOf(d[0])] = m; metrics.push(m); });
    render();

    // selectable catalog, grouped by category — users can still type any custom value
    const GROUPS = (window.MATRAIX_METRIC_GROUPS || []);
    const TOTAL = GROUPS.reduce((s, g) => s + g.metrics.length, 0);
    const inp = $('#metricInput'), addBtn = $('#metricAdd'), menu = $('#metricMenu'), countEl = $('#metricCount');
    if (countEl && TOTAL) countEl.textContent = TOTAL.toLocaleString();

    const submit = () => { if (addMetric(inp.value)) inp.value = ''; inp.focus(); };
    if (addBtn) addBtn.addEventListener('click', () => { submit(); if (menu) renderMenu(); });

    function hi(name, q) {
      if (!q) return esc(name);
      const i = name.toLowerCase().indexOf(q);
      if (i < 0) return esc(name);
      return esc(name.slice(0, i)) + '<mark>' + esc(name.slice(i, i + q.length)) + '</mark>' + esc(name.slice(i + q.length));
    }
    function renderMenu() {
      if (!menu) return;
      const q = (inp.value || '').trim().toLowerCase();
      const MAX = 140;
      let html = '', shown = 0;
      const exact = GROUPS.some(g => g.metrics.some(m => m.toLowerCase() === q));
      if (q && !exact) html += '<button class="mo mo-add" type="button" data-add="1">＋ Add “<b>' + esc(inp.value.trim()) + '</b>”</button>';
      for (const g of GROUPS) {
        if (shown >= MAX) break;
        const ms = q ? g.metrics.filter(m => m.toLowerCase().includes(q)) : g.metrics;
        if (!ms.length) continue;
        let rows = '';
        for (const m of ms) { if (shown >= MAX) break; rows += '<button class="mo" type="button" role="option" data-name="' + esc(m) + '">' + hi(m, q) + '</button>'; shown++; }
        html += '<div class="mg"><div class="mg-h">' + esc(g.category) + '</div>' + rows + '</div>';
      }
      if (shown >= MAX) html += '<div class="metric-empty">keep typing to narrow…</div>';
      if (!html) html = '<div class="metric-empty">no match — press Enter to add it</div>';
      menu.innerHTML = html;
    }
    function openMenu() { if (!menu) return; renderMenu(); menu.hidden = false; inp.setAttribute('aria-expanded', 'true'); }
    function closeMenu() { if (!menu) return; menu.hidden = true; inp.setAttribute('aria-expanded', 'false'); }
    if (inp && menu) {
      menu.addEventListener('mousedown', e => {
        const b = e.target.closest('.mo'); if (!b) return;
        e.preventDefault();
        if (b.dataset.add) { if (addMetric(inp.value)) inp.value = ''; }
        else { addMetric(b.dataset.name); inp.value = ''; }
        renderMenu(); inp.focus();
      });
      inp.addEventListener('focus', openMenu);
      inp.addEventListener('input', renderMenu);
      inp.addEventListener('blur', () => setTimeout(closeMenu, 140));
      inp.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); submit(); renderMenu(); }
        else if (e.key === 'Escape') { closeMenu(); }
      });
    } else if (inp) {
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); submit(); } });
    }

    return { pulse, addMetric, removeMetric, setMetrics };
  })();

  /* ============================================================
     SIMULATION
     ============================================================ */
  let target = TARGETS[0];
  let running = true;
  let nextId = 1021;
  let activeCount = 683;
  let totalAgents = target.agentScale;
  let currentReport = 'score';
  const store = [];
  const agg = { n: 0, pass: 0, rewardSum: 0, hist: new Array(10).fill(0), finishes: [] };
  const sparks = { ag: [], tp: [], rw: [], ps: [] };
  let reportTimer = 0;

  function scheduleReport() {
    if (reportTimer) return;
    reportTimer = window.setTimeout(() => {
      reportTimer = 0;
      renderReport();
    }, 180);
  }

  const popEl = $('#pop'), focusListEl = $('#focusList'), conFeed = $('#conFeed'), intelBody = $('#intelBody');

  /* ---- population grid (visual swarm) ---- */
  const POP_N = 168;
  const popCells = [];
  for (let i = 0; i < POP_N; i++) { const c = document.createElement('i'); popEl.appendChild(c); popCells.push(c); }
  const POP_STATES = ['spawn', 'sim', 'sim', 'sim', 'pass', 'pass', 'fail', ''];
  function popTick() {
    if (!running) return;
    const flips = 10 + ((Math.random() * 14) | 0);
    for (let k = 0; k < flips; k++) popCells[(Math.random() * POP_N) | 0].className = POP_STATES[(Math.random() * POP_STATES.length) | 0];
  }

  /* ---- behaviour factory + finalize ---- */
  function newBehavior() {
    const persona = samplePersona(), pen = personaPenalty(persona), base = target.steps, rewards = [], traj = [];
    let n = 1;
    for (let i = 0; i < base.length; i++) {
      if (Math.random() < 0.45) {                                   // optional pre-action — varies per agent
        const rr = clamp01(0.9 - pen * 0.4 + (Math.random() - 0.5) * 0.12);
        traj.push({ step: n++, observation: base[i], action: pick(telemetryFor(target).micro), reward: +rr.toFixed(3) }); rewards.push(rr);
      }
      const r = clamp01(0.88 - pen * (0.7 + Math.random() * 0.5) + (Math.random() - 0.5) * 0.14);
      traj.push({ step: n++, observation: base[i], action: pick(telemetryFor(target).actions), reward: +r.toFixed(3) }); rewards.push(r);
      if (Math.random() < 0.12 + pen * 0.7) {                       // friction retry — more likely for hard personas
        const rr = clamp01(0.5 - pen * 0.5 + (Math.random() - 0.5) * 0.16);
        traj.push({ step: n++, observation: base[i] + ' — error, retry', action: 'retry', reward: +rr.toFixed(3) }); rewards.push(rr);
      }
    }
    const score = rewards.reduce((a, b) => a + b, 0) / rewards.length;
    const verdict = score >= 0.7 ? 'pass' : score >= 0.5 ? 'watch' : 'fail';
    return { persona, pen, region: regionFor(persona), rewards, traj, score, verdict };
  }
  function finalize(b, id) {
    agg.n++; agg.rewardSum += b.score; if (b.verdict === 'pass') agg.pass++;
    agg.hist[Math.min(9, (b.score * 10) | 0)]++;
    agg.finishes.push(performance.now());
    if (agg.finishes.length > 300) agg.finishes = agg.finishes.filter(t => performance.now() - t < 8000);
    Brain.pulse(b.verdict);
    store.push({ id: `mx-${pad(id, 6)}`, target: target.id, persona: b.persona, trajectory: b.traj, score: +b.score.toFixed(4), verdict: b.verdict });
    if (store.length > 5000) store.shift();
    if (currentReport === 'score' || currentReport === 'heat') scheduleReport();
  }

  /* ---- console ---- */
  function nowStr() { const d = new Date(); return `${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}:${pad(d.getSeconds(), 2)}`; }
  function conLine(html, cls) {
    const div = document.createElement('div');
    div.className = 'con-line' + (cls ? ' ' + cls : '');
    div.innerHTML = html;
    conFeed.prepend(div);
    while (conFeed.childElementCount > 90) conFeed.lastElementChild.remove();
  }

  /* ---- background swarm: many agents finishing continuously ---- */
  let bgScored = 0, lastBatch = 0;
  function bgTick() {
    if (!running) return;
    const batch = 2 + ((Math.random() * 4) | 0);
    for (let i = 0; i < batch; i++) finalize(newBehavior(), nextId++);
    bgScored += batch;
    const now = performance.now();
    if (now - lastBatch > 2200) {
      lastBatch = now;
      conLine(`<span class="t">[${nowStr()}]</span> <span class="sum">· background: ${bgScored} agents scored · ${(agg.n ? agg.pass / agg.n * 100 : 0).toFixed(0)}% pass cumulative</span>`, 'dim');
      bgScored = 0;
    }
  }

  /* ---- in-focus agents: slow, readable trajectories ---- */
  const FOCUS_N = 8;
  let focus = [];
  let personaFileCursor = (Math.random() * 1000) | 0;
  function spawnFocus() { const personaFile=target.personaFiles[personaFileCursor++ % target.personaFiles.length]; return { id: nextId++, b: newBehavior(), step: 0, personaFile }; }
  function focusAgentNumber(f) { const match = f.personaFile.match(/persona_(\d+)\.yaml$/); return match ? match[1] : pad(f.id, 4); }
  function renderFocusCards() {
    focusListEl.innerHTML = focus.map(f => {
      if (!f) return '';
      const b = f.b, total = b.traj.length, done = f.step >= total;
      const cur = done ? null : b.traj[f.step];
      const lastR = f.step > 0 ? b.traj[f.step - 1].reward : null;
      const prog = Math.round(Math.min(f.step, total) / total * 100);
      return `<button class="focus" type="button" data-focus-id="${f.id}" aria-label="Open persona card for agent ${focusAgentNumber(f)}">
        <div class="f-top"><span class="f-id"><span class="foc">◉</span>AGENT#${focusAgentNumber(f)}</span><span class="f-step">step ${Math.min(f.step + (done ? 0 : 1), total)}/${total}</span></div>
        <div class="f-persona">${personaLabel(b.persona)}</div>
        <div class="f-now">▸ <b>${done ? 'complete' : cur.observation}</b>${cur ? ` · ${cur.action}` : ''}${lastR != null ? ` · r=${lastR.toFixed(2)}` : ''}</div>
        <div class="f-bar"><i style="width:${prog}%"></i></div>
        <span class="f-open">View persona ↗</span>
      </button>`;
    }).join('');
  }

  const personaScrim = $('#personaScrim'), personaCardBody = $('#personaCardBody'), personaClose = $('#personaClose');
  const esc = value => String(value == null ? '—' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const personaField = (label, value) => `<div class="persona-field"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
  function personaSourceUrl(file) {
    const path = `${target.personaFolder}/${file}`.split('/').map(encodeURIComponent).join('/');
    return `https://huggingface.co/datasets/MatrAIx2026/Demo_Application_Data/blob/main/${path}`;
  }
  function openPersona(f) {
    if (!f || !personaScrim || !personaCardBody) return;
    const p = f.b.persona, file = f.personaFile;
    personaCardBody.innerHTML = `<div class="persona-summary"><div class="persona-avatar">${esc(p.age_bracket)}</div><div><b>AGENT#${focusAgentNumber(f)}</b><span>${esc(target.label)}</span></div></div>
      <div class="persona-grid">
        ${personaField('Age',p.age_bracket)}${personaField('Region',p.region)}${personaField('Language',p.primary_language)}${personaField('Intent',p.intent)}
        ${personaField('Query style',p.query_complexity)}${personaField('Trust',p.trust_level)}${personaField('Safety context',p.safety_sensitivity)}${personaField('Prior context',p.prior_context)}
      </div>
      <div class="persona-source"><span>Selected task-matched YAML</span><a href="${personaSourceUrl(file)}" target="_blank" rel="noopener">${esc(file)} · View source ↗</a><small>MatrAIx2026 / Demo_Application_Data · Hugging Face access may be required</small></div>`;
    personaScrim.hidden = false;
    document.body.classList.add('persona-open');
    personaClose.focus();
  }
  function closePersona() { if (!personaScrim) return; personaScrim.hidden = true; document.body.classList.remove('persona-open'); }
  focusListEl.addEventListener('click', e => { const card=e.target.closest('[data-focus-id]'); if(card) openPersona(focus.find(f => f.id === +card.dataset.focusId)); });
  personaClose.addEventListener('click', closePersona);
  personaScrim.addEventListener('click', e => { if (e.target === personaScrim) closePersona(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !personaScrim.hidden) closePersona(); });
  function focusTick() {
    if (!running) return;
    for (let idx = 0; idx < FOCUS_N; idx++) {
      let f = focus[idx];
      if (!f) { focus[idx] = spawnFocus(); continue; }
      const b = f.b;
      if (f.step < b.traj.length) {
        const it = b.traj[f.step], r = it.reward;
        const rc = r >= 0.7 ? 'ok' : r >= 0.5 ? 'mid' : 'bad';
        conLine(`<span class="t">[${nowStr()}]</span> <span class="foc">◉</span> <span class="ag">AGENT#${focusAgentNumber(f)}</span> <span class="st">step ${f.step + 1}/${b.traj.length}</span> <span class="obs">obs:"${it.observation}"</span> → <span class="act">${it.action}</span> <span class="rw ${rc}">r=${r.toFixed(2)}</span>`);
        f.step++;
      } else {
        finalize(b, f.id);
        const vc = b.verdict === 'pass' ? 'done' : b.verdict === 'watch' ? 'rw mid' : 'rw bad';
        conLine(`<span class="t">[${nowStr()}]</span> <span class="foc">◉</span> <span class="ag">AGENT#${focusAgentNumber(f)}</span> <span class="${vc}">⮑ ${b.verdict.toUpperCase()}</span> score=${b.score.toFixed(2)} · ${b.traj.length} steps · region:${b.region}`);
        focus[idx] = spawnFocus();
      }
    }
    renderFocusCards();
  }

  /* ---- vitals + active count ---- */
  function setV(k, v) { const el = document.querySelector(`[data-v="${k}"]`); if (el) el.textContent = v; }
  function pushSpark(key, v, max) {
    const arr = sparks[key]; arr.push(v); if (arr.length > 18) arr.shift();
    const el = document.querySelector(`.spark[data-s="${key}"]`);
    if (el) el.innerHTML = arr.map(x => `<i style="height:${Math.max(8, Math.round(clamp01(x / max) * 100))}%"></i>`).join('');
  }
  function vitals() {
    activeCount = 620 + ((Math.random() * 141) | 0);
    const parallelBatches = Math.max(1, Math.ceil(totalAgents / activeCount));
    const recent = agg.finishes.filter(t => performance.now() - t < 4000).length;
    const tp = recent / 4, rw = agg.n ? agg.rewardSum / agg.n : 0, ps = agg.n ? agg.pass / agg.n * 100 : 0;
    setV('ag', compactFmt.format(totalAgents)); setV('tp', tp.toFixed(1) + '/s'); setV('rw', rw.toFixed(3)); setV('ps', ps.toFixed(1) + '%');
    pushSpark('ag', Math.log10(totalAgents), Math.log10(5.6e9)); pushSpark('tp', tp + 0.3, 22); pushSpark('rw', rw, 1); pushSpark('ps', ps / 100, 1);
    $('#swarmCount').textContent = compactFmt.format(totalAgents) + ' agents running';
    const batchMeta = $('#batchMeta');
    if (batchMeta) batchMeta.textContent = `${fmt.format(activeCount)} agents / batch · ${compactFmt.format(parallelBatches)} batches in parallel · ■ shows batch ratio`;
  }

  function resetSession() {
    store.length = 0; agg.n = 0; agg.pass = 0; agg.rewardSum = 0; agg.hist.fill(0); agg.finishes = [];
    focus = Array.from({ length: FOCUS_N }, spawnFocus); renderFocusCards();
    conFeed.innerHTML = ''; bgScored = 0;
    activeCount = 620 + ((Math.random() * 141) | 0);
    totalAgents = target.agentScale;
    Brain.setMetrics(TASK_METRICS[target.id]);
    const conMeta = $('#conMeta');
    if (conMeta) conMeta.textContent = telemetryFor(target).meta;
    const taskBlurb = $('#taskBlurb');
    if (taskBlurb) taskBlurb.textContent = target.blurb;
    renderReport();
    conLine(`<span class="t">▸ session reset · target = ${target.url}</span>`, 'dim');
  }

  /* ---- target select ---- */
  const sel = $('#target');
  sel.innerHTML = TARGETS.map(t => `<option value="${t.id}">${t.label} · ${t.url}</option>`).join('');
  const taskBlurb = $('#taskBlurb');
  if (taskBlurb) taskBlurb.textContent = target.blurb;
  sel.addEventListener('change', () => { target = TARGETS.find(t => t.id === sel.value) || TARGETS[0]; resetSession(); });

  /* ---- run / halt ---- */
  const runBtn = $('#run');
  runBtn.addEventListener('click', () => {
    running = !running;
    runBtn.textContent = running ? '■ Pause run' : '▶ Resume run';
    runBtn.classList.toggle('run', running);
    $('#scanTag').textContent = running ? '● LIVE' : '⏸ HALTED';
    $('#scanTag').style.color = running ? '' : 'var(--ink-dim)';
    document.querySelectorAll('.led').forEach(l => l.classList.toggle('on', running));
  });

  /* ============================================================
     REPORTS
     ============================================================ */
  $('#reportTabs').addEventListener('click', e => {
    const b = e.target.closest('.rtab'); if (!b) return;
    currentReport = b.dataset.r;
    [...e.currentTarget.children].forEach(c => c.classList.toggle('active', c === b));
    renderReport();
  });

  function hmColor(rate) {
    const stops = [[255, 92, 108], [255, 181, 71], [84, 246, 166]];
    const t = clamp01(rate) * 2, i = t < 1 ? 0 : 1, f = t < 1 ? t : t - 1;
    const a = stops[i], b = stops[i + 1], c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }
  function renderHeat() {
    const steps = target.steps.map(step => {
      let n = 0, pass = 0;
      for (const behavior of store) {
        for (const item of behavior.trajectory) {
          if (!item.observation.startsWith(step)) continue;
          n++; if (item.reward >= .7) pass++;
        }
      }
      return { step, n, rate: n ? pass / n : 0 };
    });
    const rows = steps.map((item, i) => item.n
      ? `<div class="hm-step"><span class="hm-step-name"><b>${i + 1}</b>${item.step}</span><span class="hm-step-cell" style="background:${hmColor(item.rate)}" title="${item.step} · ${Math.round(item.rate * 100)}% pass · n=${item.n}"><b>${Math.round(item.rate * 100)}%</b><small>${fmt.format(item.n)} checks</small></span></div>`
      : `<div class="hm-step"><span class="hm-step-name"><b>${i + 1}</b>${item.step}</span><span class="hm-step-cell empty">Waiting for runs</span></div>`
    ).join('');
    return `<div class="hm-cap">Live pass rate for the steps in <b>${target.label}</b></div>
      <div class="hm-steps">${rows}</div>
      <div class="hm-legend"><span>Needs attention</span><div class="hm-grad"></div><span>Passing</span></div>`;
  }

  function renderReport() {
    const r = target.report;
    const tgt = document.getElementById('rptTarget'); if (tgt) tgt.textContent = target.url;
    if (currentReport === 'ab') {
      const rows = r.segments.map(([s, a, b]) => {
        const d = b - a, cls = d > 0 ? 'up' : 'down';
        return `<tr><td class="seg">${s}</td><td>${a}%</td><td class="win">${b}%</td><td class="${cls}">${d > 0 ? '+' : ''}${d}</td></tr>`;
      }).join('');
      const finds = `<ul class="findings">${r.findings.map(([sev, t]) => `<li class="finding"><span class="sev ${sev}">${sev.toUpperCase()}</span>${t}</li>`).join('')}</ul>`;
      intelBody.innerHTML = `<div class="verdict">
        <div class="target">${target.label}</div>
        <div class="vrow"><span class="badge">Variant ${r.winner} wins</span><span class="lift">${r.lift}</span></div>
        <div class="metric">${r.metric}, population-weighted · ${fmt.format(r.agents)} agents</div>
        <div class="variants"><b>A</b> ${r.a} &nbsp;·&nbsp; <b>B</b> ${r.b}</div></div>
        <p class="ab-session">Live session: <b>${fmt.format(agg.n)}</b> behaviors scored, ${(agg.n ? agg.pass / agg.n * 100 : 0).toFixed(1)}% pass.</p>
        <div class="report-subhead">Performance by persona segment</div>
        <table class="seg-table"><thead><tr><th>Persona segment</th><th>A</th><th>B</th><th>Δ</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="report-subhead">What the agents found</div>${finds}`;
    } else if (currentReport === 'score') {
      const max = Math.max(1, ...agg.hist);
      const bars = agg.hist.map((v, i) => {
        const h = v / max * 100;
        const cls = i < 5 ? 'lo' : i < 7 ? 'mid' : '';
        return `<span class="hbar" title="score ${(i / 10).toFixed(1)}–${((i + 1) / 10).toFixed(1)} · n=${v}"><i class="${cls}" style="height:${h.toFixed(1)}%"></i></span>`;
      }).join('');
      intelBody.innerHTML = `<div class="histo" role="img" aria-label="Outcome distribution from ${target.scoreLabels[0]} to ${target.scoreLabels[1]}. Bar height shows relative behavior count.">${bars}</div>
        <div class="histo-axis outcome-axis"><span>${target.scoreLabels[0]}</span><span>${target.scoreLabels[1]}</span></div>
        <p class="histo-cap"><b>${fmt.format(agg.n)}</b> scored behaviors. Bar height shows how many fall in each score range, scaled to the busiest range.</p>`;
    } else if (currentReport === 'heat') {
      intelBody.innerHTML = renderHeat();
    }
  }

  /* ---- export ---- */
  $('#export').addEventListener('click', () => {
    if (!store.length) return;
    const blob = new Blob([store.map(b => JSON.stringify(b)).join('\n') + '\n'], { type: 'application/x-ndjson' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `matraix-trajectories-${target.id}-${store.length}.jsonl`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  });

  /* ---- clock ---- */
  function clock() { $('#clock').textContent = nowStr(); }

  /* ============================================================
     INIT
     ============================================================ */
  focus = Array.from({ length: FOCUS_N }, spawnFocus);
  renderFocusCards();
  vitals(); renderReport(); clock();
  let timerIds = [];
  function startTimers() {
    if (timerIds.length || document.hidden) return;
    timerIds = [
      setInterval(popTick, 460),
      setInterval(bgTick, 620),
      setInterval(focusTick, 1800),
      setInterval(vitals, 1150),
      setInterval(clock, 1000),
    ];
  }
  function stopTimers() {
    timerIds.forEach(clearInterval);
    timerIds = [];
    if (reportTimer) { clearTimeout(reportTimer); reportTimer = 0; }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopTimers();
    else { clock(); vitals(); scheduleReport(); startTimers(); }
  });
  window.addEventListener('pagehide', stopTimers);
  startTimers();
})();
