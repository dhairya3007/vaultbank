/* VaultBank Locker System – main.js */

// ── Sidebar Toggle (Mobile) ──────────────────────────────────────────────────
const menuToggle = document.getElementById('menuToggle');
const sidebar    = document.getElementById('sidebar');
const overlay    = document.getElementById('sidebarOverlay');

function openSidebar() {
  sidebar.classList.add('open');
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('open');
  document.body.style.overflow = '';
}

if (menuToggle) menuToggle.addEventListener('click', openSidebar);
if (overlay)    overlay.addEventListener('click', closeSidebar);

// Close on ESC
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSidebar();
});

// ── Auto-dismiss Flash Messages ──────────────────────────────────────────────
document.querySelectorAll('.alert').forEach(alert => {
  setTimeout(() => {
    alert.style.transition = 'opacity 0.4s, transform 0.4s';
    alert.style.opacity    = '0';
    alert.style.transform  = 'translateY(-8px)';
    setTimeout(() => alert.remove(), 400);
  }, 5000);
});

// ── Check-In Form Validation ─────────────────────────────────────────────────
const checkinForm = document.getElementById('checkinForm');
if (checkinForm) {
  checkinForm.addEventListener('submit', function (e) {
    const selected = this.querySelector('input[name="customer_id"]:checked');
    if (!selected) {
      e.preventDefault();
      // Show inline error
      let err = this.querySelector('.radio-error');
      if (!err) {
        err = document.createElement('p');
        err.className = 'scan-error radio-error';
        err.textContent = '⚠️ Please select a customer before processing entry.';
        this.querySelector('.customer-radio-list').before(err);
      }
      err.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}

// ── Scan Input Auto-Focus ─────────────────────────────────────────────────────
const scanInput = document.querySelector('.scan-input');
if (scanInput) {
  scanInput.focus();
  // Prevent rapid repeated scans (debounce 2s)
  let lastScan = 0;
  const scanForm = document.getElementById('scanForm');
  if (scanForm) {
    scanForm.addEventListener('submit', function (e) {
      const now = Date.now();
      if (now - lastScan < 2000) {
        e.preventDefault();
        return;
      }
      lastScan = now;
    });
  }
}

// ── Capacity Bar Animation ────────────────────────────────────────────────────
// Width is stored in data-pct (not inline style) to avoid CSS linter errors
// caused by Django template tags inside style attributes.
document.querySelectorAll('.capacity-fill[data-pct]').forEach(bar => {
  const pct = bar.dataset.pct || '0';
  bar.style.width = '0%';
  requestAnimationFrame(() => {
    setTimeout(() => { bar.style.width = pct + '%'; }, 120);
  });
});

// ── Active Nav Highlight Fix ──────────────────────────────────────────────────
// Remove active from parent when a child nav-item is also active-ish
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', function () {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    this.classList.add('active');
  });
});

// ── Table Row Click (locker cards) ───────────────────────────────────────────
document.querySelectorAll('.locker-card').forEach(card => {
  card.addEventListener('mouseenter', () => {
    card.style.cursor = 'pointer';
  });
});

// ── Confirm Dangerous Actions ─────────────────────────────────────────────────
document.querySelectorAll('form[action*="delete"]').forEach(form => {
  form.addEventListener('submit', function (e) {
    if (!confirm('Are you sure? This action cannot be undone.')) {
      e.preventDefault();
    }
  });
});
