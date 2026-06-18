const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');
const hamburger = document.getElementById('hamburger');

function openSidebar() {
  sidebar?.classList.add('open');
  sidebarOverlay?.classList.add('open');
}
function closeSidebar() {
  sidebar?.classList.remove('open');
  sidebarOverlay?.classList.remove('open');
}

hamburger?.addEventListener('click', openSidebar);
sidebarOverlay?.addEventListener('click', closeSidebar);

document.querySelectorAll('.message-toast').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(40px)';
    el.style.transition = 'all .4s ease';
    setTimeout(() => el.remove(), 400);
  }, 3500);
});

const catModalBtn   = document.getElementById('open-cat-modal');
const catModal      = document.getElementById('cat-modal');
const catModalClose = document.getElementById('close-cat-modal');

catModalBtn?.addEventListener('click', () => catModal?.classList.add('open'));
catModalClose?.addEventListener('click', () => catModal?.classList.remove('open'));
catModal?.addEventListener('click', e => {
  if (e.target === catModal) catModal.classList.remove('open');
});

const valueInput = document.getElementById('value-input');
if (valueInput) {
  function formatBR(raw) {
    const num = parseFloat(raw.replace(',', '.'));
    if (isNaN(num)) return '0,00';
    return num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  valueInput.addEventListener('input', e => {
    let digits = e.target.value.replace(/\D/g, '');
    if (!digits) digits = '0';
    const num = parseInt(digits, 10) / 100;
    e.target.value = num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  });

  valueInput.addEventListener('focus', e => {
    e.target.select();
  });
}

const typeSelect    = document.getElementById('id_type');
const formHeader    = document.getElementById('form-header');
const toggleTypeBtn = document.getElementById('toggle-type');

function updateTypeUI(type) {
  if (!type) return;
  if (formHeader) {
    formHeader.className = 'form-page-header ' + type;
  }
  if (toggleTypeBtn) {
    toggleTypeBtn.textContent = type;
    toggleTypeBtn.className = 'type-toggle-btn ' + type;
  }
}

toggleTypeBtn?.addEventListener('click', () => {
  if (!typeSelect) return;
  typeSelect.value = typeSelect.value === 'receita' ? 'despesa' : 'receita';
  updateTypeUI(typeSelect.value);
});

typeSelect?.addEventListener('change', () => updateTypeUI(typeSelect.value));

if (typeSelect) updateTypeUI(typeSelect.value);

const freqSelect  = document.getElementById('id_frequency');
const recurrentTo = document.getElementById('recurrent-to-wrapper');

function updateFrequencyUI(val) {
  if (!recurrentTo) return;
  recurrentTo.style.display = val === 'recurrent' ? 'block' : 'none';
}

freqSelect?.addEventListener('change', e => updateFrequencyUI(e.target.value));
if (freqSelect) updateFrequencyUI(freqSelect.value);

const calcBtn    = document.getElementById('calculator-btn');
const calcModal  = document.getElementById('calculator-modal');
const calcClose  = document.getElementById('close-calc');
const calcDisplay = document.getElementById('calc-display');
const calcExpr   = document.getElementById('calc-expression');
const calcResult = document.getElementById('calc-result');

let calcExpression = '';
let calcValue = '0';

function calcUpdate() {
  if (calcExpr) calcExpr.textContent = calcExpression;
  if (calcResult) calcResult.textContent = calcValue;
}

calcBtn?.addEventListener('click', () => {
  calcModal?.classList.add('open');
});

calcClose?.addEventListener('click', () => {
  calcModal?.classList.remove('open');
});

calcModal?.addEventListener('click', e => {
  if (e.target === calcModal) calcModal.classList.remove('open');
});

document.querySelectorAll('[data-calc]').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.dataset.calc;

    if (action === 'clear') {
      calcExpression = '';
      calcValue = '0';
    } else if (action === 'backspace') {
      calcExpression = calcExpression.slice(0, -1);
      calcValue = calcExpression || '0';
    } else if (action === 'equals') {
      try {
        const sanitised = calcExpression.replace(/[^0-9+\-*/().]/g, '');
        const result = Function('"use strict"; return (' + sanitised + ')')();
        calcValue = parseFloat(result.toFixed(2)).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (valueInput) {
          valueInput.value = calcValue;
        }
        calcExpression = result.toFixed(2);
      } catch {
        calcValue = 'Erro';
      }
    } else if (['+', '-', '*', '/'].includes(action)) {
      calcExpression += ' ' + action + ' ';
      calcValue = action;
    } else {
      calcExpression += action;
      calcValue = calcExpression;
    }
    calcUpdate();
  });
});

const chartCanvas = document.getElementById('analysis-chart');
if (chartCanvas && typeof Chart !== 'undefined') {
  const raw = chartCanvas.dataset.chartData;
  let chartData = [];
  try { chartData = JSON.parse(raw); } catch {}

  const labels  = chartData.map(d => d.label);
  const values  = chartData.map(d => d.value);
  const colors  = chartData.map(d => d.color);

  new Chart(chartCanvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#191919',
        borderWidth: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      cutout: '72%',
      animation: { animateRotate: true, duration: 800 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const d = chartData[ctx.dataIndex];
              return ` ${d.label}: ${d.percent}%`;
            }
          },
          backgroundColor: '#191919',
          borderColor: '#2a2a2a',
          borderWidth: 1,
          titleColor: '#fafafa',
          bodyColor: '#9d9d9d',
        }
      }
    }
  });
}

const filterToggle = document.getElementById('filter-toggle');
const filterBar    = document.getElementById('filter-bar');
filterToggle?.addEventListener('click', () => {
  filterBar?.classList.toggle('open');
});
