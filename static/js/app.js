// WorkPulse Corporate Frontend Logic & Real-Time Sync
document.addEventListener('DOMContentLoaded', () => {
  // 1. Date Pill Formatter
  const dateLabel = document.getElementById('todayLabel');
  if (dateLabel) {
    dateLabel.textContent = new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }).format(new Date());
  }

  // 2. Modals Control
  document.querySelectorAll('[data-open-modal]').forEach(button => {
    button.addEventListener('click', (e) => {
      e.preventDefault();
      const modalId = button.dataset.openModal;
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('open');
      }
    });
  });

  document.querySelectorAll('[data-close-modal]').forEach(button => {
    button.addEventListener('click', () => {
      button.closest('.modal-backdrop')?.classList.remove('open');
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove('open');
      }
    });
  });

  // 3. Live Attendance Timer (Authoritative Client Stopwatch)
  const timerElem = document.getElementById('liveTimer');
  if (timerElem) {
    const punchInStr = timerElem.dataset.punchIn;
    const isPaused = timerElem.dataset.paused === 'true';
    const breakSec = parseInt(timerElem.dataset.breakSeconds || '0', 10);
    const breakStartStr = timerElem.dataset.breakStart;

    if (punchInStr) {
      const punchInDate = new Date(punchInStr);

      const updateTimer = () => {
        if (isPaused && breakStartStr) {
          // On Break: count duration of current break
          const bStart = new Date(breakStartStr);
          const elapsedBreak = Math.max(0, Math.floor((Date.now() - bStart.getTime()) / 1000));
          const h = String(Math.floor(elapsedBreak / 3600)).padStart(2, '0');
          const m = String(Math.floor((elapsedBreak % 3600) / 60)).padStart(2, '0');
          const s = String(elapsedBreak % 60).padStart(2, '0');
          
          const breakTimerElem = document.getElementById('breakTimer');
          if (breakTimerElem) {
            breakTimerElem.textContent = `${h}:${m}:${s}`;
          }
          return;
        }

        // Actively Working
        const totalElapsed = Math.max(0, Math.floor((Date.now() - punchInDate.getTime()) / 1000));
        const netWorkSeconds = Math.max(0, totalElapsed - breakSec);

        const hours = String(Math.floor(netWorkSeconds / 3600)).padStart(2, '0');
        const mins = String(Math.floor((netWorkSeconds % 3600) / 60)).padStart(2, '0');
        const secs = String(netWorkSeconds % 60).padStart(2, '0');

        timerElem.textContent = `${hours}:${mins}:${secs}`;

        const todayWorkedSync = document.getElementById('todayWorkedDisplay');
        if (todayWorkedSync) {
          todayWorkedSync.textContent = timerElem.textContent;
        }
      };

      updateTimer();
      setInterval(updateTimer, 1000);
    }
  }

  // 4. Auto Dismiss Toast Messages
  document.querySelectorAll('.toast').forEach(toast => {
    setTimeout(() => {
      toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 400);
    }, 4500);
  });

  // 5. Client-Side Quick Table Search
  document.querySelectorAll('[data-table-search]').forEach(input => {
    input.addEventListener('input', () => {
      const targetTableId = input.dataset.tableSearch;
      const filterValue = input.value.toLowerCase().trim();
      const rows = document.querySelectorAll(`#${targetTableId} tbody tr`);

      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filterValue) ? '' : 'none';
      });
    });
  });

  // 6. Demo Account Quick Fill Helper
  window.fillCredentials = (empId, password) => {
    const idInput = document.querySelector('input[name="emp_id"]');
    const pwInput = document.querySelector('input[name="password"]');
    if (idInput && pwInput) {
      idInput.value = empId;
      pwInput.value = password;
      idInput.focus();
    }
  };

  // 7. Real-Time Activity Heartbeat
  if (window.currentUserId) {
    let lastActiveTime = Date.now();
    const markActive = () => { lastActiveTime = Date.now(); };

    ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(event => {
      document.addEventListener(event, markActive, { passive: true });
    });

    const sendHeartbeat = () => {
      // Send heartbeat only if user was active in last 5 minutes
      if (Date.now() - lastActiveTime < 300000) {
        fetch('/api/activity/heartbeat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        }).catch(err => console.debug('Heartbeat sync deferred'));
      }
    };

    // Initial ping & recurring 60s ping
    sendHeartbeat();
    setInterval(sendHeartbeat, 60000);
  }
});