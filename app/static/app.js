/**
 * sunsyscon — 入金照合システム フロントエンドJS
 */

// ── ステップ管理 ─────────────────────────────
let currentStep = 1;
const totalSteps = 5;

function updateStepIndicator(step) {
  currentStep = step;
  document.querySelectorAll('.step-item').forEach((el, i) => {
    const s = i + 1;
    el.classList.remove('active', 'done');
    if (s < step) el.classList.add('done');
    else if (s === step) el.classList.add('active');
  });
  document.querySelectorAll('.step-connector').forEach((el, i) => {
    el.classList.toggle('done', i + 1 < step);
  });
}

// ── ファイルアップロード ─────────────────────
function setupUpload(inputId, dropId, resultId, endpoint, onSuccess) {
  const fileInput = document.getElementById(inputId);
  const dropArea = document.getElementById(dropId);
  const resultDiv = document.getElementById(resultId);

  // クリックでのファイル選択
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) uploadFile(e.target.files[0]);
  });

  // ドラッグ&ドロップ
  dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.classList.add('dragover'); });
  dropArea.addEventListener('dragleave', () => dropArea.classList.remove('dragover'));
  dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dropArea.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
  });

  async function uploadFile(file) {
    dropArea.innerHTML = `<div class="upload-icon loading">⏳</div><p>アップロード中...</p>`;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(endpoint, { method: 'POST', body: formData });
      const data = await res.json();

      if (data.status === 'ok') {
        dropArea.innerHTML = `<div class="upload-icon">✅</div><p><strong>${file.name}</strong> アップロード完了</p>`;
        resultDiv.style.display = 'block';
        onSuccess(data, resultDiv);
      } else {
        dropArea.innerHTML = `<div class="upload-icon">❌</div><p>エラーが発生しました</p>`;
      }
    } catch (err) {
      dropArea.innerHTML = `<div class="upload-icon">❌</div><p>通信エラー: ${err.message}</p>`;
    }
  }
}

// ── 初期化 ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // STEP 1: 楽天銀行CSV
  setupUpload('file-bank', 'drop-bank', 'result-bank', '/api/upload/bank', (data, div) => {
    div.innerHTML = `
      ✅ <strong>${data.deposit_count}件</strong>の入金データを読み込みました
      （除外: ${data.skipped_count}件）
    `;
    document.getElementById('stat-bank').textContent = data.deposit_count;
    updateStepIndicator(2);
    checkMatchReady();
  });

  // STEP 2: 顧客データCSV
  setupUpload('file-customer', 'drop-customer', 'result-customer', '/api/upload/customer', (data, div) => {
    div.innerHTML = `
      ✅ <strong>${data.count}件</strong>の顧客データを読み込みました
    `;
    document.getElementById('stat-customer').textContent = data.count;
    updateStepIndicator(3);
    checkMatchReady();
  });

  // STEP 3: 照合ボタン
  document.getElementById('btn-match').addEventListener('click', runMatch);

  // タブ切り替え
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // STEP 5: ダウンロード
  document.getElementById('btn-download').addEventListener('click', () => {
    window.location.href = '/api/download/csv';
  });
});

function checkMatchReady() {
  const bankVal = document.getElementById('stat-bank').textContent;
  const custVal = document.getElementById('stat-customer').textContent;
  const ready = bankVal !== '-' && custVal !== '-';
  document.getElementById('btn-match').disabled = !ready;
}

// ── 照合実行 ────────────────────────────────
async function runMatch() {
  const btn = document.getElementById('btn-match');
  const resultDiv = document.getElementById('result-match');
  btn.disabled = true;
  btn.textContent = '照合中...';
  btn.classList.add('loading');

  try {
    const res = await fetch('/api/match', { method: 'POST' });
    const data = await res.json();

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = `
      ✅ 照合完了 — 入金済み: <strong>${data.matched_count}</strong>件 / 要確認: <strong>${data.review_count}</strong>件
    `;

    updateStepIndicator(4);

    // STEP 4 パネルを表示
    document.getElementById('panel-step4').style.display = 'block';
    document.getElementById('panel-step5').style.display = 'block';

    // バッジ更新
    document.getElementById('badge-matched').textContent = data.matched_count;
    document.getElementById('badge-review').textContent = data.review_count;
    document.getElementById('download-count').textContent = data.matched_count;

    // テーブル更新
    await loadMatched();
    await loadReview();

    // スクロール
    document.getElementById('panel-step4').scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    resultDiv.style.display = 'block';
    resultDiv.style.borderColor = 'rgba(225, 112, 85, 0.3)';
    resultDiv.style.background = 'rgba(225, 112, 85, 0.08)';
    resultDiv.style.color = '#e17055';
    resultDiv.innerHTML = `❌ エラー: ${err.message}`;
  } finally {
    btn.classList.remove('loading');
    btn.textContent = '照合を実行する';
    btn.disabled = false;
  }
}

// ── 入金済みテーブル読み込み ────────────────
async function loadMatched() {
  const res = await fetch('/api/matched');
  const data = await res.json();

  const tbody = document.querySelector('#table-matched tbody');
  tbody.innerHTML = '';

  data.forEach(m => {
    const excessClass = m.new_excess_deficit > 0 ? 'amount-positive'
      : m.new_excess_deficit < 0 ? 'amount-negative' : 'amount-zero';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${m.record_no}</td>
      <td>${m.customer_id}</td>
      <td>${m.name}</td>
      <td>${m.furigana}</td>
      <td>${m.contract_months}</td>
      <td class="amount-positive">¥${Number(m.deposit_amount).toLocaleString()}</td>
      <td>¥${Number(m.adjusted_charge).toLocaleString()}</td>
      <td class="${excessClass}">¥${Number(m.new_excess_deficit).toLocaleString()}</td>
      <td style="font-size:0.75rem;color:var(--text-muted)">${m.fee_note}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('badge-matched').textContent = data.length;
  document.getElementById('download-count').textContent = data.length;
}

// ── 要確認リスト読み込み ────────────────────
async function loadReview() {
  const res = await fetch('/api/review');
  const data = await res.json();
  const container = document.getElementById('review-list');
  container.innerHTML = '';

  document.getElementById('badge-review').textContent = data.length;

  if (data.length === 0) {
    container.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:2rem;">要確認データはありません 🎉</p>';
    return;
  }

  data.forEach((item, reviewIdx) => {
    const typeClass = item.type === 'NA' ? 'na' : item.type === '複数ヒット' ? 'multi' : 'mismatch';
    const card = document.createElement('div');
    card.className = 'review-card';
    card.innerHTML = `
      <div class="review-header">
        <span class="review-type ${typeClass}">${item.type}</span>
        <span class="review-bank-info">
          ${item.bank.date} | <strong>¥${Number(item.bank.amount).toLocaleString()}</strong> | 
          ${item.bank.name_raw} → <strong>${item.bank.name_converted || '(空欄)'}</strong>
        </span>
      </div>
      <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.5rem;">
        ${item.reason}
      </div>
      ${item.candidates.length > 0 ? item.candidates.map((c, cidx) => `
        <div class="candidate-row">
          <div class="candidate-info">
            <span>ID: <strong>${c.customer_id}</strong></span>
            <span>氏名: <strong>${c.name}</strong></span>
            <span>請求: <strong>¥${Number(c.adjusted_charge).toLocaleString()}</strong></span>
            <span>過不足: <strong class="${c.new_excess_deficit === 0 ? 'amount-zero' : 'amount-negative'}">¥${Number(c.new_excess_deficit).toLocaleString()}</strong></span>
            <span style="font-size:0.72rem;color:var(--text-muted)">${c.fee_note}</span>
          </div>
          <button class="btn btn-outline btn-small" onclick="resolveItem(${reviewIdx}, ${cidx})">
            この顧客で確定
          </button>
        </div>
      `).join('') : '<p style="color:var(--text-muted);font-size:0.82rem;">候補なし</p>'}
    `;
    container.appendChild(card);
  });
}

// ── 手動紐付け ──────────────────────────────
async function resolveItem(reviewIndex, candidateIndex) {
  try {
    const res = await fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_index: reviewIndex, candidate_index: candidateIndex }),
    });
    const data = await res.json();

    if (data.status === 'ok') {
      await loadMatched();
      await loadReview();
    }
  } catch (err) {
    alert('紐付けエラー: ' + err.message);
  }
}
