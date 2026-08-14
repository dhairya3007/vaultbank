/* ==========================================================================
   VaultBank SaaS – main.js
   Alpine.js Stores, Global Utilities, QR Scanner & Clipboard Helpers
   Tech Stack: Tailwind CSS + Flowbite + Alpine.js + Heroicons
   ========================================================================== */

// ── Alpine.js Global State & Directives ─────────────────────────────────
document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    sidebarOpen: false,
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    },
    closeSidebar() {
      this.sidebarOpen = false;
    }
  });
});

// ── Toast Messages Auto-Dismiss ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.vb-toast').forEach(toast => {
    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-6px)';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  });
});

// ── Copy to Clipboard Helper with Visual Feedback ───────────────────────
function copyToClipboard(text, btnEl, successLabel = 'Copied!') {
  if (!navigator.clipboard) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
      renderCopySuccess(btnEl, successLabel);
    } catch (err) {
      alert('Could not copy token: ' + text);
    }
    document.body.removeChild(textArea);
    return;
  }

  navigator.clipboard.writeText(text).then(() => {
    renderCopySuccess(btnEl, successLabel);
  }).catch(() => {
    alert('Copy failed – token: ' + text);
  });
}

function renderCopySuccess(btnEl, successLabel) {
  if (!btnEl) return;
  const originalHtml = btnEl.innerHTML;
  btnEl.innerHTML = `<span class="inline-flex items-center gap-1 text-green-400 font-semibold">
    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
    ${successLabel}
  </span>`;
  btnEl.disabled = true;
  setTimeout(() => {
    btnEl.innerHTML = originalHtml;
    btnEl.disabled = false;
  }, 2000);
}

// ── QR Scanner Management (html5-qrcode) ────────────────────────────────
let _html5ScannerInstance = null;

function startQrScanner(readerContainerId, hiddenInputId, submitFormId) {
  const startBtn = document.getElementById('startScanBtn');
  const stopBtn  = document.getElementById('stopScanBtn');
  const hintEl   = document.getElementById('cameraHint');

  if (startBtn) startBtn.classList.add('hidden');
  if (stopBtn)  stopBtn.classList.remove('hidden');
  if (hintEl)   hintEl.textContent = 'Initialising camera feed…';

  try {
    _html5ScannerInstance = new Html5Qrcode(readerContainerId);
    _html5ScannerInstance.start(
      { facingMode: 'environment' },
      { fps: 15, qrbox: { width: 220, height: 220 } },
      (decodedText) => {
        stopQrScanner();
        const input = document.getElementById(hiddenInputId);
        if (input) input.value = decodedText.trim();
        const form = document.getElementById(submitFormId);
        if (form) form.submit();
      },
      () => {} // ignore interim frame read errors
    ).then(() => {
      if (hintEl) hintEl.textContent = 'Camera active. Center the locker QR code inside the box.';
    }).catch(err => {
      if (hintEl) hintEl.textContent = 'Camera permission required or device unavailable (' + err + ')';
      if (startBtn) startBtn.classList.remove('hidden');
      if (stopBtn)  stopBtn.classList.add('hidden');
    });
  } catch (e) {
    if (hintEl) hintEl.textContent = 'Scanner library loading error. Please use manual entry.';
    if (startBtn) startBtn.classList.remove('hidden');
    if (stopBtn)  stopBtn.classList.add('hidden');
  }
}

function stopQrScanner() {
  if (_html5ScannerInstance) {
    _html5ScannerInstance.stop().then(() => {
      _html5ScannerInstance.clear();
      _html5ScannerInstance = null;
      const startBtn = document.getElementById('startScanBtn');
      const stopBtn  = document.getElementById('stopScanBtn');
      const hintEl   = document.getElementById('cameraHint');
      if (startBtn) startBtn.classList.remove('hidden');
      if (stopBtn)  stopBtn.classList.add('hidden');
      if (hintEl)   hintEl.textContent = 'Point camera at locker QR code';
    }).catch(console.error);
  }
}
