'use strict';

// OPTIONAL: paste the real URL of your existing repository between the quotes.
// If left empty, the app reads GitHub repository metadata from Vercel.
const GITHUB_REPOSITORY_URL = '';

const $ = id => document.getElementById(id);
let running = false;
let revision = 0;
const figureMap = new Map();

function payload() {
  return {
    tickers: $('tickers').value,
    weights: $('weights').value,
    initial_investment: Number($('investment').value),
    scenario: $('scenario').value,
    days: Number($('days').value),
    paths: Number($('paths').value)
  };
}

function status(text, error = false) {
  $('status').hidden = false;
  $('status').textContent = text;
  $('status').classList.toggle('error', error);
}

function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}

async function plotVisible() {
  for (const [key, fig] of figureMap) {
    const el = $(key);
    if (el && !el.closest('[hidden]')) {
      await Plotly.react(el, fig.data, fig.layout, {
        responsive: true,
        displaylogo: false,
        toImageButtonOptions: { format: 'png' }
      });
    }
  }
}

function metricCard(metric) {
  const card = node('div', undefined, 'metric');
  card.append(
    node('div', metric.label, 'metric-label'),
    node('div', metric.value, 'metric-value')
  );

  // Presentation only: do not display Safe/Danger or replace them with a verdict.
  // The original Python probability calculation remains untouched.
  const isProbability = metric.label === 'Probability of Loss';
  if (!isProbability && metric.delta !== null && metric.delta !== undefined) {
    const negative = String(metric.delta).startsWith('-');
    card.append(node('div', metric.delta, 'metric-delta ' + (negative ? 'red' : 'green')));
  }

  const explanations = {
    'Expected Value (Mean)': 'Average simulated portfolio value at the end of the selected horizon.',
    'VaR 95%': 'Portfolio value at the 5th percentile of simulated outcomes.',
    'CVaR 95% (Expected Shortfall)': 'Average portfolio value among outcomes at or below the 5th-percentile threshold.',
    'Probability of Loss': 'Share of simulations ending below your initial investment.'
  };
  if (explanations[metric.label]) {
    card.append(node('p', explanations[metric.label], 'metric-help'));
  }
  return card;
}

async function render(data) {
  // Keep the existing introduction; this update changes sections 2–5 only.
  $('description').textContent = data.description;
  $('metrics').replaceChildren(...data.metrics.map(metricCard));

  const report = data.tables[0];
  const table = node('table');
  const head = node('thead');
  const row = node('tr');
  const body = node('tbody');
  report.columns.forEach(x => row.append(node('th', x)));
  head.append(row);
  report.data.forEach(values => {
    const tr = node('tr');
    values.forEach(x => tr.append(node('td', String(x))));
    body.append(tr);
  });
  table.append(head, body);
  $('classification').replaceChildren(table);

  figureMap.clear();
  data.charts.forEach(c => figureMap.set(c.key, c.figure));
  $('results').hidden = false;
  await plotVisible();
}

async function run() {
  if (running || !$('settings').reportValidity()) return;
  const submittedRevision = revision;
  const submittedPayload = payload();
  running = true;
  $('run').disabled = true;
  $('run').textContent = 'Running…';
  $('results').hidden = true;
  status('Fetching market data and running your simulation…');

  try {
    if (typeof Plotly === 'undefined') {
      throw new Error('The chart library could not load. Please refresh the page.');
    }
    const response = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(submittedPayload)
    });
    const raw = await response.text();
    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error(`The server could not complete this run (HTTP ${response.status}). Please try again.`);
    }
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);

    // An input edit during a request never queues another paid computation.
    // Its old response must not appear to belong to the new settings.
    if (submittedRevision === revision) {
      await render(data);
      if (submittedRevision === revision) {
        $('status').hidden = true;
      }
    }
  } catch (error) {
    if (submittedRevision === revision) status(error.message, true);
  } finally {
    running = false;
    $('run').disabled = false;
    $('run').textContent = 'Run simulation';
    if (submittedRevision !== revision) {
      $('results').hidden = true;
      status('Settings changed — click Run simulation to update the results.');
    }
  }
}

function changed() {
  revision += 1;
  $('results').hidden = true;
  status(running
    ? 'Settings changed while a simulation is running. When it finishes, click Run simulation to use your new settings.'
    : 'Settings changed — click Run simulation to update the results.');
}

$('settings').addEventListener('submit', event => {
  event.preventDefault();
  run();
});
// No initial run, debounce, queued run, or automatic rerun on input changes.
$('settings').addEventListener('input', changed);
$('settings').addEventListener('change', changed);

for (const [id, output] of [['days', 'daysValue'], ['paths', 'pathsValue']]) {
  $(id).addEventListener('input', () => {
    $(output).textContent = Number($(id).value).toLocaleString('en-US');
  });
}
$('minus').onclick = () => {
  $('investment').value = Math.max(1000000, Number($('investment').value) - 5000000);
  changed();
};
$('plus').onclick = () => {
  $('investment').value = Number($('investment').value) + 5000000;
  changed();
};

document.querySelectorAll('[role=tab]').forEach(button => {
  button.addEventListener('click', async () => {
    document.querySelectorAll('[role=tab]').forEach(b => {
      b.setAttribute('aria-selected', String(b === button));
    });
    document.querySelectorAll('[role=tabpanel]').forEach(panel => {
      panel.hidden = panel.id !== 'panel-' + button.dataset.panel;
    });
    await plotVisible();
  });
});

const resizeObserver = new ResizeObserver(entries => {
  for (const { target } of entries) {
    if (target.data && !target.closest('[hidden]')) Plotly.Plots.resize(target);
  }
});
document.querySelectorAll('.chart').forEach(el => resizeObserver.observe(el));

function validRepositoryURL(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== 'https:' || url.hostname !== 'github.com' ||
        url.username || url.password || url.port || url.search || url.hash ||
        !/^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(url.pathname)) return null;
    return url.href;
  } catch {
    return null;
  }
}

async function loadGitHubLink() {
  const link = $('github-link');
  let repositoryURL = validRepositoryURL(GITHUB_REPOSITORY_URL);
  // Never silently replace an explicitly configured but invalid URL.
  if (!GITHUB_REPOSITORY_URL.trim()) {
    try {
      const response = await fetch('/api/project', { cache: 'no-store' });
      if (response.ok) repositoryURL = validRepositoryURL((await response.json()).github_url);
    } catch {
      // Missing deployment metadata should not block the simulation.
    }
  }
  if (repositoryURL) {
    link.href = repositoryURL;
    link.removeAttribute('aria-disabled');
    link.removeAttribute('tabindex');
    $('github-status').hidden = true;
  } else {
    $('github-status').textContent = 'Source link is not available yet.';
  }
}
loadGitHubLink();
