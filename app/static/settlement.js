import {request, element, pretty} from './client.js';

const form = document.querySelector('#settle-source');
const file = document.querySelector('#settle-file');
const profile = document.querySelector('#settle-profile');
const notice = document.querySelector('#settle-notice');
const detail = document.querySelector('#settle-detail');
const evidence = document.querySelector('#settle-evidence');
const table = document.querySelector('#settle-departments');
const period = document.querySelector('#settle-period');
const historyBox = document.querySelector('#settle-history');
const reviewForm = document.querySelector('#settle-review');
let selected = null;
let busy = false;

function announce(text, failure = false) {
  notice.textContent = text;
  notice.dataset.failure = String(failure);
}

function source() {
  const data = new FormData();
  if (file.files.length) data.append('file', file.files[0]);
  else data.append('sample', profile.value);
  return data;
}

function fillKpis(totals) {
  document.querySelector('#kpi-returned').textContent = totals?.returned_bytes ?? '—';
  document.querySelector('#kpi-items').textContent = totals?.returned_items ?? '—';
  document.querySelector('#kpi-retained').textContent = totals?.retained ?? '—';
  document.querySelector('#kpi-skipped').textContent = totals?.skipped ?? '—';
}

function drawReport(report, committed = false) {
  fillKpis(report.totals);
  period.textContent = committed ? `期次 ${report.period ?? '—'}` : '预览（未入库）';
  table.replaceChildren();
  const head = element('thead');
  const hr = element('tr');
  ['部门', '返还容量', '返还条目', '历史跳过'].forEach((t) => hr.append(element('th', t)));
  head.append(hr);
  const body = element('tbody');
  for (const dept of report.departments) {
    const tr = element('tr');
    tr.append(
      element('td', dept.department),
      element('td', String(dept.returned_bytes)),
      element('td', dept.items.map((i) => `${i.kind}:${i.id}`).join('，') || '—'),
      element('td', dept.skipped.map((s) => s.id).join('，') || '—'),
    );
    body.append(tr);
  }
  table.append(head, body);
  const lines = [];
  lines.push('共用保留：');
  for (const r of report.retained) {
    lines.push(`- [${r.kind}] ${r.id}（${r.department}，${r.size_bytes} 字节）${r.reason}`
      + (r.leased_members ? ` 未退成员=${r.leased_members.join(',')}` : ''));
  }
  if (!report.retained.length) lines.push('- 无');
  lines.push('', `对账 balanced=${report.balance?.balanced}`);
  detail.textContent = lines.join('\n');
}

function showError(error) {
  fillKpis(null);
  period.textContent = '整批阻断';
  table.replaceChildren();
  detail.textContent = `阻断：${error.message}\n${pretty(error)}`;
  announce(error.message, true);
}

async function refreshHistory() {
  const data = await request('/api/settlements');
  historyBox.replaceChildren();
  for (const item of data.items) {
    const li = element('li');
    const btn = element('button', `P${item.period} · ${item.status} · r${item.revision}`);
    btn.dataset.settlement = item.id;
    li.append(btn);
    historyBox.append(li);
  }
}

async function runAction(action) {
  if (busy) return;
  busy = true;
  document.body.setAttribute('aria-busy', 'true');
  try {
    await action();
  } catch (error) {
    showError(error);
  } finally {
    busy = false;
    document.body.removeAttribute('aria-busy');
  }
}

document.querySelector('#settle-preview').addEventListener('click', () => runAction(async () => {
  const report = await request('/api/settlements/preview', {method: 'POST', body: source()});
  selected = null;
  reviewForm.hidden = true;
  drawReport(report);
  announce('裁决预览已更新（未入库）');
}));

form.addEventListener('submit', (event) => {
  event.preventDefault();
  runAction(async () => {
    const run = await request('/api/settlements', {method: 'POST', body: source()});
    selected = run;
    drawReport(run.report, true);
    reviewForm.hidden = false;
    document.querySelector('#settle-run-status').textContent =
      `${run.id.slice(0, 10)} · P${run.period} · ${run.status} · r${run.revision}`;
    reviewForm.elements['settle-note'].value = run.note || '';
    evidence.href = `/api/settlements/${run.id}/evidence`;
    announce('结算期次已保存');
    await refreshHistory();
  });
});

historyBox.addEventListener('click', (event) => {
  const btn = event.target.closest('[data-settlement]');
  if (!btn) return;
  runAction(async () => {
    selected = await request(`/api/settlements/${btn.dataset.settlement}`);
    drawReport(selected.report, true);
    reviewForm.hidden = false;
    document.querySelector('#settle-run-status').textContent =
      `${selected.id.slice(0, 10)} · P${selected.period} · ${selected.status} · r${selected.revision}`;
    reviewForm.elements['settle-note'].value = selected.note || '';
    evidence.href = `/api/settlements/${selected.id}/evidence`;
    announce('已载入历史期次');
  });
});

reviewForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!selected) return;
  runAction(async () => {
    const payload = {
      status: event.submitter.value,
      revision: selected.revision,
      note: reviewForm.elements['settle-note'].value,
    };
    selected = await request(`/api/settlements/${selected.id}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    drawReport(selected.report, true);
    document.querySelector('#settle-run-status').textContent =
      `${selected.id.slice(0, 10)} · P${selected.period} · ${selected.status} · r${selected.revision}`;
    reviewForm.elements['settle-note'].value = selected.note;
    announce(selected.status === 'APPROVED' ? '清单已签发' : '清单已暂缓');
    await refreshHistory();
  });
});

profile.addEventListener('change', () => { file.value = ''; });
file.addEventListener('change', () => {
  document.querySelector('#settle-file-name').textContent = file.files[0]?.name || '';
});

// 初始载入 Q1 预览。
runAction(async () => {
  const report = await request('/api/settlements/preview', {
    method: 'POST', body: source(),
  });
  drawReport(report);
  announce('已载入 Q1 预览');
  await refreshHistory();
});
