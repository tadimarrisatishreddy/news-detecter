/**
 * NewsDetector - Frontend Application
 * Module 6: Frontend & System Integration
 */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // --------------------------------------------------------------------------
  // Application State & Smart API Base
  // --------------------------------------------------------------------------
  const API_BASE = (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000'))
    ? 'http://127.0.0.1:8000'
    : '';

  const state = {
    user: null,
    accessToken: localStorage.getItem('access_token') || null,
    refreshToken: localStorage.getItem('refresh_token') || null,
    historyDetections: [],
  };

  // --------------------------------------------------------------------------
  // Toast Notification System
  // --------------------------------------------------------------------------
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s, transform 0.3s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(50px)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // --------------------------------------------------------------------------
  // API Client with Automatic Authentication & Refresh
  // --------------------------------------------------------------------------
  async function apiRequest(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const headers = options.headers || {};
    if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    if (state.accessToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${state.accessToken}`;
    }

    options.headers = headers;

    let response = await fetch(url, options);

    // Auto-refresh token on 401 if refresh token is available
    if (response.status === 401 && state.refreshToken && !endpoint.includes('/auth/refresh')) {
      const refreshed = await attemptTokenRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${state.accessToken}`;
        options.headers = headers;
        response = await fetch(url, options);
      }
    }

    if (!response.ok) {
      let errDetail = 'Request failed';
      try {
        const errorData = await response.json();
        if (typeof errorData.detail === 'string') {
          errDetail = errorData.detail;
        } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
          errDetail = errorData.detail.map(d => d.msg || JSON.stringify(d)).join(', ');
        } else {
          errDetail = errorData.detail || errorData.message || JSON.stringify(errorData);
        }
      } catch (e) {
        errDetail = `${response.status} ${response.statusText}`;
      }
      throw new Error(errDetail);
    }

    return await response.json();
  }

  async function attemptTokenRefresh() {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      if (res.ok) {
        const data = await res.json();
        state.accessToken = data.access_token;
        state.refreshToken = data.refresh_token || state.refreshToken;
        localStorage.setItem('access_token', state.accessToken);
        localStorage.setItem('refresh_token', state.refreshToken);
        return true;
      }
    } catch (e) {
      console.warn('Failed to refresh session', e);
    }
    // If refresh failed, clear credentials
    clearAuthSession();
    return false;
  }

  function setAuthSession(data) {
    state.accessToken = data.access_token;
    state.refreshToken = data.refresh_token;
    localStorage.setItem('access_token', state.accessToken);
    localStorage.setItem('refresh_token', state.refreshToken);
    fetchUserProfile();
  }

  function clearAuthSession() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    state.historyDetections = [];
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    updateAuthUI();
    renderHistoryTable([]);
    updateHistoryMetrics([]);
  }

  async function fetchUserProfile() {
    if (!state.accessToken) {
      updateAuthUI();
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
      return;
    }
    try {
      const user = await apiRequest('/auth/me');
      state.user = user;
      updateAuthUI();
      loadDetectionHistory();
    } catch (e) {
      console.warn('Session expired or invalid:', e.message);
      clearAuthSession();
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
  }

  function updateAuthUI() {
    const guestSection = document.getElementById('auth-guest-section');
    const userSection = document.getElementById('auth-user-section');
    const adminNavBtn = document.getElementById('nav-btn-admin');
    const adminNavItem = document.getElementById('nav-item-admin');

    if (state.user) {
      if (guestSection) guestSection.style.display = 'none';
      if (userSection) userSection.style.display = 'flex';

      const avatar = document.getElementById('header-user-avatar');
      const name = document.getElementById('header-user-name');
      const role = document.getElementById('header-user-role');

      if (avatar) avatar.textContent = (state.user.full_name || 'U').charAt(0).toUpperCase();
      if (name) name.textContent = state.user.full_name || state.user.email;
      if (role) role.textContent = (state.user.role || 'user').toUpperCase();

      if (adminNavBtn) {
        adminNavBtn.style.display = state.user.role === 'admin' ? 'inline-flex' : 'none';
      }
      if (adminNavItem) {
        adminNavItem.style.display = state.user.role === 'admin' ? 'inline-block' : 'none';
      }
    } else {
      if (guestSection) guestSection.style.display = 'flex';
      if (userSection) userSection.style.display = 'none';
      if (adminNavBtn) adminNavBtn.style.display = 'none';
      if (adminNavItem) adminNavItem.style.display = 'none';
    }
  }

  // --------------------------------------------------------------------------
  // Tab Switching
  // --------------------------------------------------------------------------
  function setupTabs() {
    const buttons = document.querySelectorAll('.nav-tab-btn');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        if (!targetId) return;

        buttons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.tab-pane').forEach((pane) => {
          pane.classList.remove('active');
        });

        const targetPane = document.getElementById(targetId);
        if (targetPane) {
          targetPane.classList.add('active');
        }

        // Lazy-load data when navigating into History, Dashboard or Admin
        if (targetId === 'tab-history') {
          loadDetectionHistory();
        } else if (targetId === 'tab-dashboard') {
          loadUserDashboard();
        } else if (targetId === 'tab-admin') {
          loadAdminDashboard();
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // Dialog Modals (Sign In / Register)
  // --------------------------------------------------------------------------
  function setupModals() {
    const modalLogin = document.getElementById('modal-login');
    const modalRegister = document.getElementById('modal-register');

    document.getElementById('btn-open-login')?.addEventListener('click', () => {
      modalLogin?.showModal();
    });

    document.getElementById('btn-open-register')?.addEventListener('click', () => {
      modalRegister?.showModal();
    });

    document.getElementById('link-switch-to-register')?.addEventListener('click', (e) => {
      e.preventDefault();
      modalLogin?.close();
      modalRegister?.showModal();
    });

    document.querySelectorAll('.dialog-close').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-close');
        if (id) document.getElementById(id)?.close();
      });
    });

    // Close on backdrop click
    [modalLogin, modalRegister].forEach((modal) => {
      modal?.addEventListener('click', (e) => {
        const rect = modal.getBoundingClientRect();
        if (
          e.clientX < rect.left ||
          e.clientX > rect.right ||
          e.clientY < rect.top ||
          e.clientY > rect.bottom
        ) {
          modal.close();
        }
      });
    });

    // Live password validator in registration modal
    const regPwdInput = document.getElementById('reg-password');
    if (regPwdInput) {
      regPwdInput.addEventListener('input', () => {
        const val = regPwdInput.value;
        setPolicy('p-len', val.length >= 8);
        setPolicy('p-upper', /[A-Z]/.test(val));
        setPolicy('p-lower', /[a-z]/.test(val));
        setPolicy('p-num', /[0-9]/.test(val));
        setPolicy('p-special', /[!@#$%^&*(),.?":{}|<>]/.test(val));
      });
    }

    function setPolicy(elementId, isValid) {
      const el = document.getElementById(elementId);
      if (!el) return;
      if (isValid) {
        el.classList.add('valid');
        el.querySelector('span').textContent = '✓';
      } else {
        el.classList.remove('valid');
        el.querySelector('span').textContent = '•';
      }
    }

    // Login Form Submit
    document.getElementById('form-login')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('login-email').value;
      const password = document.getElementById('login-password').value;
      const submitBtn = document.getElementById('btn-submit-login');

      try {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Signing in...';

        const data = await apiRequest('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        });

        setAuthSession(data);
        modalLogin.close();
        showToast('Successfully signed in!', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
      }
    });

    // Register Form Submit
    document.getElementById('form-register')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const full_name = document.getElementById('reg-name').value;
      const email = document.getElementById('reg-email').value;
      const password = document.getElementById('reg-password').value;
      const password_confirm = document.getElementById('reg-confirm').value;
      const submitBtn = document.getElementById('btn-submit-register');

      if (password !== password_confirm) {
        showToast('Password confirmation does not match.', 'error');
        return;
      }

      try {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating account...';

        await apiRequest('/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            full_name,
            email,
            password,
            confirm_password: password_confirm,
            password_confirm,
          }),
        });

        modalRegister.close();
        showToast('Registration successful! You can now sign in.', 'success');
        modalLogin.showModal();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Account';
      }
    });

    // Logout
    document.getElementById('btn-logout')?.addEventListener('click', async () => {
      if (confirm('Are you sure you want to sign out?')) {
        try {
          if (state.refreshToken) {
            await apiRequest('/auth/logout', {
              method: 'POST',
              body: JSON.stringify({ refresh_token: state.refreshToken }),
            });
          }
        } catch (e) {
          // ignore logout network errors
        }
        clearAuthSession();
        showToast('Signed out successfully', 'info');
        window.location.href = '/login';
      }
    });
  }

  // Helper to run fact check automatically in sequential pipeline
  async function runFactCheckForClaim(claim) {
    const fcBtn = document.getElementById('btn-run-factcheck');
    const sourcesSlider = document.getElementById('fc-max-sources');
    const govOnlyCheck = document.getElementById('fc-gov-only');
    if (!claim) return;
    try {
      if (fcBtn) {
        fcBtn.disabled = true;
        fcBtn.innerHTML = 'Verifying sources...';
      }
      const result = await apiRequest('/fact-check/verify', {
        method: 'POST',
        body: JSON.stringify({
          claim,
          max_sources: sourcesSlider ? parseInt(sourcesSlider.value, 10) : 5,
          check_government_only: govOnlyCheck ? govOnlyCheck.checked : false,
        }),
      });
      displayFactCheckResult(result);
    } catch (e) {
      console.warn('Fact check auto-run error:', e);
    } finally {
      if (fcBtn) {
        fcBtn.disabled = false;
        fcBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 12 2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>
          Run Multi-Source Fact Check
        `;
      }
    }
  }

  // --------------------------------------------------------------------------
  // Module 3: AI Fake News Detection
  // --------------------------------------------------------------------------
  function setupDetection() {
    const form = document.getElementById('form-detect');
    const claimInput = document.getElementById('detect-claim-input');
    const runBtn = document.getElementById('btn-run-detect');

    // Quick Preprocessing Button
    document.getElementById('btn-quick-preprocess')?.addEventListener('click', async () => {
      const claim = claimInput.value.trim();
      if (!claim) {
        showToast('Please enter text to preprocess.', 'warning');
        return;
      }
      try {
        const data = await apiRequest('/preprocess', {
          method: 'POST',
          body: JSON.stringify({
            text: claim,
            lowercase: true,
            strip_html: document.getElementById('nlp-opt-html')?.checked ?? true,
            expand_contractions: document.getElementById('nlp-opt-contractions')?.checked ?? true,
            remove_urls: document.getElementById('nlp-opt-urls')?.checked ?? true,
            remove_stopwords: document.getElementById('nlp-opt-stopwords')?.checked ?? false,
            preserve_sentence_punct: true,
          }),
        });
        const previewBox = document.getElementById('preprocess-preview-box');
        const previewText = document.getElementById('preprocess-preview-text');
        const tokenBadge = document.getElementById('preprocess-token-badge');
        if (previewBox && previewText && tokenBadge) {
          previewBox.style.display = 'block';
          previewText.textContent = data.cleaned_text;
          tokenBadge.textContent = `${data.word_count} words • ${data.tokens.length} tokens`;
        }
        showToast('Text preprocessed successfully!', 'success');
      } catch (e) {
        showToast(`Preprocessing error: ${e.message}`, 'error');
      }
    });

    // Sample Chips
    document.querySelectorAll('.sample-chip[data-sample]').forEach((chip) => {
      chip.addEventListener('click', () => {
        claimInput.value = chip.getAttribute('data-sample');
        claimInput.focus();
        updateDetectCounter();
      });
    });

    // Live character/word counter
    function updateDetectCounter() {
      const text = claimInput.value;
      const chars = text.length;
      const words = text.trim() === '' ? 0 : text.trim().split(/\s+/).length;
      const readSecs = Math.ceil(words / 4);
      const counterEl = document.getElementById('detect-char-count');
      const readEl = document.getElementById('detect-read-time');
      if (counterEl) counterEl.textContent = `${chars} characters • ${words} words`;
      if (readEl) readEl.textContent = readSecs < 60 ? `~${readSecs}s reading time` : `~${Math.ceil(readSecs / 60)}m reading time`;
    }
    claimInput?.addEventListener('input', updateDetectCounter);

    // Single Claim Detection Submit
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const claim = claimInput.value.trim();
      if (!claim) return;

      if (!state.accessToken) {
        showToast('Please sign in or create an account to run AI Detection.', 'warning');
        window.location.href = '/login';
        return;
      }

      try {
        runBtn.disabled = true;
        runBtn.innerHTML = 'Analyzing with Gemma 3...';

        const result = await apiRequest('/detect', {
          method: 'POST',
          body: JSON.stringify({ claim }),
        });

        displayDetectionResult(result);
        showToast('Gemma 3 detection completed & stored!', 'success');
        loadDetectionHistory();

        // Sequential Pipeline Step 3: Populate & trigger Fact-Checking verification
        const fcInput = document.getElementById('fc-claim-input');
        if (fcInput) {
          fcInput.value = claim;
          runFactCheckForClaim(claim);
        }
      } catch (err) {
        showToast(`Detection error: ${err.message}`, 'error');
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          Process Text & Verify News
        `;
      }
    });

    // Batch Detection Toggle & Execution
    const batchDrawer = document.getElementById('batch-detect-drawer');
    const batchToggleBtn = document.getElementById('btn-switch-batch-detect');
    batchToggleBtn?.addEventListener('click', () => {
      if (batchDrawer.style.display === 'none') {
        batchDrawer.style.display = 'block';
        batchToggleBtn.textContent = 'Hide Batch';
      } else {
        batchDrawer.style.display = 'none';
        batchToggleBtn.textContent = 'Batch Detection';
      }
    });

    document.getElementById('btn-run-batch-detect')?.addEventListener('click', async () => {
      const text = document.getElementById('batch-detect-input').value.trim();
      const claims = text.split('\n').map((c) => c.trim()).filter((c) => c.length >= 5);

      if (claims.length === 0) {
        showToast('Please enter at least one valid claim (minimum 5 chars).', 'warning');
        return;
      }

      if (!state.accessToken) {
        showToast('Please sign in to run batch detection.', 'warning');
        document.getElementById('modal-login')?.showModal();
        return;
      }

      const btn = document.getElementById('btn-run-batch-detect');
      try {
        btn.disabled = true;
        btn.textContent = `Processing ${claims.length} claims...`;

        const data = await apiRequest('/detect/batch', {
          method: 'POST',
          body: JSON.stringify({ claims }),
        });

        displayBatchResults(data.results);
        showToast(`Batch completed: ${data.total_processed} claims saved to database!`, 'success');
        loadDetectionHistory();
      } catch (err) {
        showToast(`Batch error: ${err.message}`, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Process Batch';
      }
    });
  }

  function displayDetectionResult(res) {
    document.getElementById('detect-empty-state').style.display = 'none';
    document.getElementById('detect-output-container').style.display = 'block';

    const verdict = (res.verdict || 'UNCERTAIN').toUpperCase();
    const confidence = Math.round(res.confidence || 0);

    const banner = document.getElementById('detect-verdict-banner');
    const verdictText = document.getElementById('detect-verdict-text');
    const confVal = document.getElementById('detect-confidence-pct');
    const confFill = document.getElementById('detect-confidence-fill');
    const indicator = document.getElementById('detect-status-indicator');

    banner.className = 'verdict-banner';
    confFill.className = 'progress-bar-fill';

    if (verdict === 'LIKELY_REAL') {
      banner.classList.add('real');
      confFill.classList.add('real');
      verdictText.innerHTML = '🛡️ LIKELY REAL';
      indicator.textContent = 'Verified Real';
      indicator.style.borderColor = 'var(--verdict-real)';
    } else if (verdict === 'LIKELY_FAKE') {
      banner.classList.add('fake');
      confFill.classList.add('fake');
      verdictText.innerHTML = '⚠️ LIKELY FAKE';
      indicator.textContent = 'Detected Fake';
      indicator.style.borderColor = 'var(--verdict-fake)';
    } else {
      banner.classList.add('uncertain');
      confFill.classList.add('uncertain');
      verdictText.innerHTML = '❓ UNCERTAIN';
      indicator.textContent = 'Inconclusive';
      indicator.style.borderColor = 'var(--verdict-uncertain)';
    }

    confVal.textContent = `${confidence}%`;
    confFill.style.width = `${confidence}%`;

    document.getElementById('detect-explanation-text').textContent =
      res.explanation || 'No explanation provided.';

    // Meta
    document.getElementById('detect-meta-id').textContent = `#${res.detection_id || '--'}`;
    document.getElementById('detect-meta-time').textContent = res.created_at
      ? new Date(res.created_at).toLocaleString()
      : 'Just now';

    // Signals
    const signalsBox = document.getElementById('detect-signals-container');
    signalsBox.innerHTML = '';
    const signals = res.key_signals || [];
    if (signals.length > 0) {
      signals.forEach((s) => {
        const pill = document.createElement('span');
        pill.className = 'signal-pill';
        pill.textContent = s;
        signalsBox.appendChild(pill);
      });
    } else {
      signalsBox.innerHTML = '<span style="font-size:0.8rem; color:var(--text-dim);">No distinct manipulation signals detected.</span>';
    }
  }

  function displayBatchResults(results) {
    const container = document.getElementById('batch-results-container');
    const tbody = document.querySelector('#batch-results-table tbody');
    tbody.innerHTML = '';

    results.forEach((item) => {
      const tr = document.createElement('tr');
      const v = (item.verdict || 'UNCERTAIN').toUpperCase();
      let color = 'var(--verdict-uncertain)';
      if (v === 'LIKELY_REAL') color = 'var(--verdict-real)';
      if (v === 'LIKELY_FAKE') color = 'var(--verdict-fake)';

      tr.innerHTML = `
        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(item.claim)}</td>
        <td><strong style="color: ${color};">${v}</strong></td>
        <td>${Math.round(item.confidence || 0)}%</td>
      `;
      tbody.appendChild(tr);
    });

    container.style.display = 'block';
  }

  // --------------------------------------------------------------------------
  // Detection History & Database Records
  // --------------------------------------------------------------------------
  function setupHistory() {
    const searchInput = document.getElementById('hist-search-input');
    const verdictFilter = document.getElementById('hist-filter-verdict');
    const refreshBtn = document.getElementById('btn-refresh-history');
    const clearBtn = document.getElementById('btn-clear-history');
    const gotoDetectBtn = document.getElementById('btn-goto-detect');
    const gotoHistBtn = document.getElementById('btn-goto-history');

    searchInput?.addEventListener('input', () => {
      filterAndRenderHistory();
    });

    verdictFilter?.addEventListener('change', () => {
      filterAndRenderHistory();
    });

    refreshBtn?.addEventListener('click', () => {
      loadDetectionHistory(true);
    });

    clearBtn?.addEventListener('click', async () => {
      if (!state.accessToken) {
        showToast('Please sign in to manage your history.', 'warning');
        return;
      }
      if (confirm('Are you sure you want to delete all your saved detection records from the database?')) {
        try {
          const res = await apiRequest('/history', { method: 'DELETE' });
          showToast(res.message || 'Detection history cleared from database.', 'success');
          state.historyDetections = [];
          renderHistoryTable([]);
          updateHistoryMetrics([]);
        } catch (e) {
          showToast(`Failed to clear history: ${e.message}`, 'error');
        }
      }
    });

    gotoDetectBtn?.addEventListener('click', () => {
      switchToTab('tab-detect');
    });

    gotoHistBtn?.addEventListener('click', () => {
      switchToTab('tab-history');
    });

    // Login activity modal trigger
    document.getElementById('btn-open-logins')?.addEventListener('click', () => {
      openLoginHistoryModal();
    });
  }

  function switchToTab(tabId) {
    const targetBtn = document.querySelector(`.nav-tab-btn[data-tab="${tabId}"]`);
    if (targetBtn) {
      targetBtn.click();
    }
  }

  async function loadDetectionHistory(isManualRefresh = false) {
    if (!state.accessToken) {
      state.historyDetections = [];
      renderHistoryTable([]);
      updateHistoryMetrics([]);
      return;
    }

    try {
      const records = await apiRequest('/history?limit=100');
      state.historyDetections = Array.isArray(records) ? records : [];
      filterAndRenderHistory();
      updateHistoryMetrics(state.historyDetections);
      if (isManualRefresh) {
        showToast('Detection history refreshed from database.', 'info');
      }
    } catch (e) {
      console.warn('Failed to load detection history:', e);
    }
  }

  function filterAndRenderHistory() {
    const searchVal = (document.getElementById('hist-search-input')?.value || '').toLowerCase().trim();
    const verdictVal = (document.getElementById('hist-filter-verdict')?.value || '').toUpperCase().trim();

    let list = state.historyDetections || [];
    if (verdictVal) {
      list = list.filter((item) => (item.verdict || '').toUpperCase() === verdictVal);
    }
    if (searchVal) {
      list = list.filter((item) =>
        (item.claim || '').toLowerCase().includes(searchVal) ||
        (item.explanation || '').toLowerCase().includes(searchVal)
      );
    }
    renderHistoryTable(list);
  }

  function updateHistoryMetrics(records) {
    const total = records.length;
    let real = 0;
    let fake = 0;
    let unc = 0;

    records.forEach((r) => {
      const v = (r.verdict || '').toUpperCase();
      if (v.includes('REAL')) real++;
      else if (v.includes('FAKE')) fake++;
      else unc++;
    });

    const elTotal = document.getElementById('hist-stat-total');
    const elReal = document.getElementById('hist-stat-real');
    const elFake = document.getElementById('hist-stat-fake');
    const elUnc = document.getElementById('hist-stat-uncertain');
    const elBadge = document.getElementById('hist-records-count');

    if (elTotal) elTotal.textContent = total;
    if (elReal) elReal.textContent = real;
    if (elFake) elFake.textContent = fake;
    if (elUnc) elUnc.textContent = unc;
    if (elBadge) elBadge.textContent = `${total} Records`;
  }

  function renderHistoryTable(records) {
    const tbody = document.getElementById('hist-tbody');
    const emptyState = document.getElementById('hist-empty-state');
    const tableContainer = document.getElementById('hist-table-container');

    if (!tbody) return;

    tbody.innerHTML = '';
    if (!records || records.length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      if (tableContainer) tableContainer.style.display = 'none';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';

    records.forEach((rec) => {
      const tr = document.createElement('tr');
      const v = (rec.verdict || 'UNCERTAIN').toUpperCase();
      let pillClass = 'stance-neutral';
      if (v.includes('REAL')) pillClass = 'stance-supports';
      if (v.includes('FAKE')) pillClass = 'stance-refutes';

      const conf = rec.confidence != null ? Math.round(rec.confidence) : 0;
      const dateStr = rec.created_at ? new Date(rec.created_at).toLocaleString() : '--';

      tr.innerHTML = `
        <td style="color:var(--text-dim); font-size:0.8rem;">#${rec.id}</td>
        <td>
          <div style="font-weight:600; color:var(--text-main); margin-bottom:0.2rem; max-width:420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escapeHtml(rec.claim)}
          </div>
          <div style="font-size:0.75rem; color:var(--text-muted); max-width:420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escapeHtml(rec.explanation || '')}
          </div>
        </td>
        <td><span class="stance-pill ${pillClass}">${v}</span></td>
        <td>
          <div style="display:flex; align-items:center; gap:0.4rem;">
            <span style="font-size:0.85rem; font-weight:600;">${conf}%</span>
          </div>
        </td>
        <td style="font-size:0.75rem; color:var(--text-muted);">${dateStr}</td>
        <td style="text-align:right;">
          <div style="display:flex; justify-content:flex-end; gap:0.4rem;">
            <button class="btn btn-secondary btn-sm btn-hist-view" data-id="${rec.id}" title="View Details" style="padding:0.25rem 0.5rem; font-size:0.75rem;">
              View
            </button>
            <button class="btn btn-secondary btn-sm btn-hist-del" data-id="${rec.id}" title="Delete" style="padding:0.25rem 0.5rem; font-size:0.75rem; color:#ef4444;">
              &times;
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Attach row events
    tbody.querySelectorAll('.btn-hist-view').forEach((b) => {
      b.addEventListener('click', () => {
        const id = parseInt(b.getAttribute('data-id'), 10);
        const item = (state.historyDetections || []).find((r) => r.id === id);
        if (item) openDetectionDetailModal(item);
      });
    });

    tbody.querySelectorAll('.btn-hist-del').forEach((b) => {
      b.addEventListener('click', async () => {
        const id = parseInt(b.getAttribute('data-id'), 10);
        if (confirm(`Delete detection record #${id} from database?`)) {
          try {
            await apiRequest(`/history/${id}`, { method: 'DELETE' });
            showToast(`Detection #${id} deleted from database.`, 'info');
            state.historyDetections = (state.historyDetections || []).filter((r) => r.id !== id);
            filterAndRenderHistory();
            updateHistoryMetrics(state.historyDetections);
          } catch (e) {
            showToast(`Delete failed: ${e.message}`, 'error');
          }
        }
      });
    });
  }

  function openDetectionDetailModal(item) {
    const modal = document.getElementById('modal-detection-detail');
    if (!modal) return;

    document.getElementById('modal-detail-claim').textContent = item.claim || '--';
    const verdictEl = document.getElementById('modal-detail-verdict');
    const v = (item.verdict || 'UNCERTAIN').toUpperCase();
    let pillClass = 'stance-neutral';
    if (v.includes('REAL')) pillClass = 'stance-supports';
    if (v.includes('FAKE')) pillClass = 'stance-refutes';
    verdictEl.innerHTML = `<span class="stance-pill ${pillClass}">${v}</span>`;

    document.getElementById('modal-detail-confidence').textContent = `${Math.round(item.confidence || 0)}%`;
    document.getElementById('modal-detail-date').textContent = item.created_at ? new Date(item.created_at).toLocaleString() : '--';
    document.getElementById('modal-detail-explanation').textContent = item.explanation || 'No explanation recorded.';

    modal.showModal();
  }

  async function openLoginHistoryModal() {
    const modal = document.getElementById('modal-login-history');
    if (!modal) return;
    modal.showModal();

    const tbody = document.getElementById('tbody-user-logins');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-dim);">Loading login records from database...</td></tr>';

    try {
      const records = await apiRequest('/auth/login-history');
      if (!records || records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-dim);">No login records recorded yet.</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      records.forEach((r) => {
        const tr = document.createElement('tr');
        const isSuccess = r.status === 'success';
        tr.innerHTML = `
          <td>
            <span class="stance-pill ${isSuccess ? 'stance-supports' : 'stance-refutes'}">
              ${isSuccess ? 'Success' : 'Failed'}
            </span>
          </td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${new Date(r.login_time).toLocaleString()}</td>
          <td style="font-family:var(--font-mono); font-size:0.8rem;">${escapeHtml(r.ip_address || '127.0.0.1')}</td>
          <td style="font-size:0.75rem; color:var(--text-dim); max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(r.user_agent || '')}">
            ${escapeHtml(r.user_agent || '--')}
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="color:var(--verdict-fake); text-align:center;">${escapeHtml(e.message)}</td></tr>`;
    }
  }

  // --------------------------------------------------------------------------
  // Module 4: Fact-Checking & Trusted Source Verification
  // --------------------------------------------------------------------------
  function setupFactChecking() {
    const form = document.getElementById('form-factcheck');
    const claimInput = document.getElementById('fc-claim-input');
    const sourcesSlider = document.getElementById('fc-max-sources');
    const sourcesVal = document.getElementById('fc-sources-val');
    const govOnlyCheck = document.getElementById('fc-gov-only');
    const runBtn = document.getElementById('btn-run-factcheck');

    sourcesSlider?.addEventListener('input', () => {
      sourcesVal.textContent = sourcesSlider.value;
    });

    // Sample Chips
    document.querySelectorAll('.sample-chip[data-fc-sample]').forEach((chip) => {
      chip.addEventListener('click', () => {
        claimInput.value = chip.getAttribute('data-fc-sample');
        claimInput.focus();
      });
    });

    // Whitelist drawer toggle
    const wlDrawer = document.getElementById('whitelist-drawer');
    const wlToggleBtn = document.getElementById('btn-toggle-whitelist');
    wlToggleBtn?.addEventListener('click', async () => {
      if (wlDrawer.style.display === 'none') {
        wlDrawer.style.display = 'block';
        wlToggleBtn.textContent = 'Hide Whitelist';
        await loadWhitelist();
      } else {
        wlDrawer.style.display = 'none';
        wlToggleBtn.textContent = 'View Whitelist';
      }
    });

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const claim = claimInput.value.trim();
      if (!claim) return;

      if (!state.accessToken) {
        showToast('Please sign in to verify claims against trusted registries.', 'warning');
        document.getElementById('modal-login')?.showModal();
        return;
      }

      try {
        runBtn.disabled = true;
        runBtn.innerHTML = 'Verifying with registries...';

        const result = await apiRequest('/fact-check/verify', {
          method: 'POST',
          body: JSON.stringify({
            claim,
            max_sources: parseInt(sourcesSlider.value, 10),
            check_government_only: govOnlyCheck.checked,
          }),
        });

        displayFactCheckResult(result);
        showToast('Fact check completed!', 'success');
      } catch (err) {
        showToast(`Verification error: ${err.message}`, 'error');
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 12 2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>
          Run Multi-Source Verification
        `;
      }
    });
  }

  async function loadWhitelist() {
    const list = document.getElementById('whitelist-list');
    try {
      list.innerHTML = '<span style="color:var(--text-dim);">Loading trusted registries...</span>';
      const data = await apiRequest('/fact-check/sources/whitelist');
      list.innerHTML = '';

      document.getElementById('stat-whitelist-count').textContent = `${data.total_sources}+`;

      data.trusted_domains.forEach((item) => {
        const itemEl = document.createElement('div');
        itemEl.style.display = 'flex';
        itemEl.style.justifyContent = 'space-between';
        itemEl.style.alignItems = 'center';
        itemEl.style.padding = '0.25rem 0';
        itemEl.style.borderBottom = '1px solid rgba(255,255,255,0.03)';

        itemEl.innerHTML = `
          <span><strong>${item.domain}</strong> <small style="color:var(--text-dim);">(${item.name})</small></span>
          <span class="tier-badge ${item.tier.toLowerCase()}">${item.tier}</span>
        `;
        list.appendChild(itemEl);
      });
    } catch (e) {
      list.innerHTML = `<span style="color:var(--verdict-fake);">${e.message}</span>`;
    }
  }

  function displayFactCheckResult(res) {
    document.getElementById('fc-empty-state').style.display = 'none';
    document.getElementById('fc-output-container').style.display = 'block';

    const status = (res.status || 'UNPROVEN').toUpperCase();
    const verdict = (res.verdict || 'UNVERIFIED').toUpperCase();
    const trustScore = Math.round(res.trust_score || 0);

    const banner = document.getElementById('fc-verdict-banner');
    const verdictText = document.getElementById('fc-verdict-text');
    const subText = document.getElementById('fc-verdict-subtext');
    const scoreVal = document.getElementById('fc-trust-score-val');
    const scoreFill = document.getElementById('fc-trust-score-fill');
    const badge = document.getElementById('fc-status-badge');

    banner.className = 'verdict-banner';
    scoreFill.className = 'progress-bar-fill';

    if (status === 'VERIFIED') {
      banner.classList.add('real');
      scoreFill.classList.add('real');
      verdictText.textContent = '✅ VERIFIED';
      badge.textContent = 'Evidence Confirmed';
    } else if (status === 'REFUTED') {
      banner.classList.add('fake');
      scoreFill.classList.add('fake');
      verdictText.textContent = '❌ REFUTED (HOAX)';
      badge.textContent = 'Debunked by Evidence';
    } else {
      banner.classList.add('uncertain');
      scoreFill.classList.add('uncertain');
      verdictText.textContent = `⚠️ ${status}`;
      badge.textContent = status;
    }

    subText.textContent = `Truth Assessment: ${verdict}`;
    scoreVal.textContent = `${trustScore} / 100`;
    scoreFill.style.width = `${trustScore}%`;

    document.getElementById('fc-summary-text').textContent = res.summary || 'No summary available.';
    document.getElementById('fc-evidence-count').textContent = res.evidence_count || 0;

    // Citations
    const list = document.getElementById('fc-evidence-items');
    list.innerHTML = '';

    const sources = res.evidence_sources || [];
    if (sources.length === 0) {
      list.innerHTML = '<p style="color:var(--text-dim); font-size:0.85rem;">No citations available.</p>';
      return;
    }

    sources.forEach((s) => {
      const card = document.createElement('div');
      card.className = 'evidence-card';

      let stanceClass = 'stance-neutral';
      if (s.stance === 'SUPPORTS') stanceClass = 'stance-supports';
      if (s.stance === 'REFUTES') stanceClass = 'stance-refutes';

      let tierBadgeClass = (s.tier || 'tier-4').toLowerCase().replace(' ', '-');

      card.innerHTML = `
        <div class="evidence-meta">
          <a href="${escapeHtml(s.source_url)}" target="_blank" rel="noopener noreferrer" class="evidence-source">
            ${escapeHtml(s.source_name)} ↗
          </a>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <span class="tier-badge ${tierBadgeClass}">${escapeHtml(s.tier || 'TIER 3')}</span>
            <span class="stance-pill ${stanceClass}">${escapeHtml(s.stance)}</span>
          </div>
        </div>
        ${s.snippet ? `<div class="evidence-snippet">“${escapeHtml(s.snippet)}”</div>` : ''}
      `;
      list.appendChild(card);
    });
  }

  // --------------------------------------------------------------------------
  // Module 2: NLP Studio & Linguistic Processing
  // --------------------------------------------------------------------------
  function setupNLP() {
    const form = document.getElementById('form-nlp');
    const textInput = document.getElementById('nlp-text-input');
    const cleanOnlyBtn = document.getElementById('btn-clean-only');
    const runBtn = document.getElementById('btn-run-nlp');

    // Samples
    document.querySelectorAll('.sample-chip[data-nlp-sample]').forEach((chip) => {
      chip.addEventListener('click', () => {
        textInput.value = chip.getAttribute('data-nlp-sample');
        textInput.focus();
      });
    });

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const news_text = textInput.value.trim();
      if (news_text.length < 20) {
        showToast('Text must be at least 20 characters long.', 'warning');
        return;
      }

      try {
        runBtn.disabled = true;
        runBtn.textContent = 'Analyzing...';

        const data = await apiRequest('/news/analyze', {
          method: 'POST',
          body: JSON.stringify({ news_text }),
        });

        displayNLPResult(data);
        showToast('Linguistic analysis completed!', 'success');
      } catch (err) {
        showToast(`NLP error: ${err.message}`, 'error');
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = 'Analyze Text';
      }
    });

    cleanOnlyBtn?.addEventListener('click', async () => {
      const text = textInput.value.trim();
      if (!text) {
        showToast('Enter text to clean.', 'warning');
        return;
      }

      try {
        cleanOnlyBtn.disabled = true;
        const res = await apiRequest('/news/preprocess', {
          method: 'POST',
          body: JSON.stringify({
            text,
            strip_html: document.getElementById('nlp-opt-html').checked,
            expand_contractions: document.getElementById('nlp-opt-contractions').checked,
            remove_urls: document.getElementById('nlp-opt-urls').checked,
            remove_stopwords: document.getElementById('nlp-opt-stopwords').checked,
          }),
        });

        document.getElementById('nlp-empty-state').style.display = 'none';
        document.getElementById('nlp-output-container').style.display = 'block';
        document.getElementById('nlp-cleaned-preview').value = res.cleaned_text;
        document.getElementById('metric-word-count').textContent = res.word_count;
        showToast('Text cleaned & normalized!', 'success');
      } catch (err) {
        showToast(`Cleaning error: ${err.message}`, 'error');
      } finally {
        cleanOnlyBtn.disabled = false;
      }
    });
  }

  function displayNLPResult(data) {
    document.getElementById('nlp-empty-state').style.display = 'none';
    document.getElementById('nlp-output-container').style.display = 'block';

    const stats = data.statistics || {};
    const read = data.readability || {};
    const sens = data.sensationalism || {};

    document.getElementById('metric-word-count').textContent = stats.word_count || 0;
    document.getElementById('metric-sentence-count').textContent = stats.sentence_count || 0;
    document.getElementById('metric-flesch-score').textContent = Math.round(read.flesch_reading_ease || 0);
    document.getElementById('metric-sensational-score').textContent = (sens.sensationalism_score || 0).toFixed(2);

    document.getElementById('nlp-reading-level').textContent = `${read.reading_level || 'Standard'} (Grade ${read.grade_level || 0})`;

    const sensStatus = document.getElementById('nlp-sensational-status');
    if (sens.is_sensational) {
      sensStatus.textContent = '⚠️ High Clickbait';
      sensStatus.style.color = 'var(--verdict-fake)';
    } else {
      sensStatus.textContent = '✅ Objective Tone';
      sensStatus.style.color = 'var(--verdict-real)';
    }

    // Keywords
    const kwBox = document.getElementById('nlp-keywords-list');
    kwBox.innerHTML = '';
    const keywords = data.top_keywords_with_freq || [];
    if (keywords.length > 0) {
      keywords.slice(0, 10).forEach((item) => {
        const chip = document.createElement('span');
        chip.className = 'keyword-chip';
        chip.innerHTML = `${escapeHtml(item.keyword)} <span class="keyword-count">${item.count}</span>`;
        kwBox.appendChild(chip);
      });
    } else {
      kwBox.innerHTML = '<span style="color:var(--text-dim); font-size:0.8rem;">No keywords extracted.</span>';
    }

    document.getElementById('nlp-cleaned-preview').value = data.cleaned_text || '';
  }

  // --------------------------------------------------------------------------
  // Module 5: User Dashboard & Exportable Reports
  // --------------------------------------------------------------------------
  async function loadUserDashboard() {
    if (!state.accessToken) {
      showToast('Sign in to view your dashboard.', 'info');
      return;
    }

    try {
      const data = await apiRequest('/dashboard/me');

      document.getElementById('dash-total-detections').textContent = data.total_detections || 0;
      document.getElementById('dash-total-factchecks').textContent = data.total_fact_checks || 0;
      document.getElementById('dash-total-submissions').textContent = data.total_submissions || 0;
      document.getElementById('dash-avg-confidence').textContent = `${Math.round((data.avg_detection_confidence || 0) * 100)}%`;
      document.getElementById('dash-avg-trust').textContent = Math.round(data.avg_trust_score || 0);

      // Verdict bars
      const vb = data.verdict_breakdown || {};
      const totalV = (vb.LIKELY_REAL || 0) + (vb.LIKELY_FAKE || 0) + (vb.UNCERTAIN || 0);

      document.getElementById('dash-cnt-real').textContent = vb.LIKELY_REAL || 0;
      document.getElementById('dash-cnt-fake').textContent = vb.LIKELY_FAKE || 0;
      document.getElementById('dash-cnt-uncertain').textContent = vb.UNCERTAIN || 0;

      const pReal = totalV > 0 ? ((vb.LIKELY_REAL || 0) / totalV) * 100 : 0;
      const pFake = totalV > 0 ? ((vb.LIKELY_FAKE || 0) / totalV) * 100 : 0;
      const pUnc = totalV > 0 ? ((vb.UNCERTAIN || 0) / totalV) * 100 : 0;

      document.getElementById('dash-bar-real').style.width = `${pReal}%`;
      document.getElementById('dash-bar-fake').style.width = `${pFake}%`;
      document.getElementById('dash-bar-uncertain').style.width = `${pUnc}%`;

      // Recent feed
      const feed = document.getElementById('dash-recent-list');
      feed.innerHTML = '';
      const recent = data.recent_detections || [];
      if (recent.length === 0) {
        feed.innerHTML = '<p style="color:var(--text-dim); font-size:0.85rem;">No recent detections recorded yet.</p>';
      } else {
        recent.forEach((item) => {
          const div = document.createElement('div');
          div.style.padding = '0.5rem';
          div.style.background = 'rgba(255,255,255,0.02)';
          div.style.borderRadius = 'var(--radius-sm)';
          div.style.fontSize = '0.8rem';
          div.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:0.2rem;">
              <strong style="color:#e2e8f0;">${escapeHtml(item.claim)}</strong>
              <span class="stance-pill ${item.verdict === 'LIKELY_REAL' ? 'stance-supports' : item.verdict === 'LIKELY_FAKE' ? 'stance-refutes' : 'stance-neutral'}">${item.verdict}</span>
            </div>
            <div style="color:var(--text-dim); font-size:0.7rem;">${new Date(item.created_at).toLocaleString()}</div>
          `;
          feed.appendChild(div);
        });
      }
    } catch (e) {
      showToast(`Dashboard error: ${e.message}`, 'error');
    }
  }

  function setupDashboardReports() {
    document.getElementById('btn-export-user-report')?.addEventListener('click', async () => {
      if (!state.accessToken) {
        showToast('Sign in to export reports.', 'warning');
        return;
      }
      try {
        const report = await apiRequest('/dashboard/me/report');
        downloadJsonFile(report, `newsdetector-user-report-${Date.now()}.json`);
        showToast('Personal report exported!', 'success');
      } catch (e) {
        showToast(`Report export error: ${e.message}`, 'error');
      }
    });

    document.getElementById('btn-export-admin-report')?.addEventListener('click', async () => {
      try {
        const report = await apiRequest('/dashboard/admin/report');
        downloadJsonFile(report, `newsdetector-system-report-${Date.now()}.json`);
        showToast('System report exported!', 'success');
      } catch (e) {
        showToast(`Admin report export error: ${e.message}`, 'error');
      }
    });
  }

  // --------------------------------------------------------------------------
  // Module 5 Admin: Control Panel
  // --------------------------------------------------------------------------
  async function loadAdminDashboard() {
    if (!state.user || state.user.role !== 'admin') {
      showToast('Admin privilege required.', 'error');
      return;
    }

    try {
      const stats = await apiRequest('/dashboard/admin');

      document.getElementById('admin-total-users').textContent = stats.total_users || 0;
      document.getElementById('admin-active-users').textContent = stats.active_users || 0;
      document.getElementById('admin-total-detections').textContent = stats.total_detections || 0;
      document.getElementById('admin-total-factchecks').textContent = stats.total_fact_checks || 0;

      // Top Flagged claims
      const claimsTbody = document.querySelector('#admin-claims-table tbody');
      claimsTbody.innerHTML = '';
      const topClaims = stats.top_flagged_claims || [];
      if (topClaims.length === 0) {
        claimsTbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-dim);">No flagged fake claims yet.</td></tr>';
      } else {
        topClaims.forEach((c) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${escapeHtml(c.claim)}</td>
            <td><span class="stance-pill stance-refutes">${escapeHtml(c.verdict)}</span></td>
            <td>${c.times_detected}</td>
            <td>${Math.round((c.avg_confidence || 0) * 100)}%</td>
          `;
          claimsTbody.appendChild(tr);
        });
      }

      // Users table
      const usersData = await apiRequest('/dashboard/admin/users');
      const usersTbody = document.querySelector('#admin-users-table tbody');
      usersTbody.innerHTML = '';
      const users = usersData.users || [];
      if (users.length === 0) {
        usersTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-dim);">No users found.</td></tr>';
      } else {
        users.forEach((u) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><strong>${escapeHtml(u.full_name)}</strong></td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="tier-badge ${u.role === 'admin' ? 'tier-1' : 'tier-4'}">${u.role.toUpperCase()}</span></td>
            <td>${u.total_detections}</td>
            <td>${u.total_fact_checks}</td>
            <td>${u.is_active ? '<span style="color:var(--verdict-real);">● Active</span>' : '<span style="color:var(--verdict-fake);">● Inactive</span>'}</td>
          `;
          usersTbody.appendChild(tr);
        });
      }
    } catch (e) {
      showToast(`Admin error: ${e.message}`, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Utility Helpers
  // --------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function downloadJsonFile(obj, filename) {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(obj, null, 2));
    const a = document.createElement('a');
    a.setAttribute('href', dataStr);
    a.setAttribute('download', filename);
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------
  window.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupModals();
    setupDetection();
    setupHistory();
    setupFactChecking();
    setupNLP();
    setupDashboardReports();

    // Check existing auth session
    fetchUserProfile();
  });
})();
