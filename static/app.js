function updateSummary(summary) {
  for (const [key, value] of Object.entries(summary || {})) {
    const element = document.querySelector(`[data-summary-key="${key}"]`);
    if (element) {
      element.textContent = value;
    }
  }
}

function updateStatusRow(formId, row) {
  const form = document.getElementById(formId);
  if (!form || !row) {
    return;
  }

  const statusRow = form.closest('[data-status-row]');
  if (!statusRow) {
    return;
  }
  statusRow.classList.toggle('stale-row', Boolean(row.is_stale));

  statusRow.querySelector('input[name="shelf_count"]').value = row.shelf_count ?? '';
  statusRow.querySelector('input[name="expiring_count"]').value = row.expiring_count ?? '';
  const lastVisit = statusRow.querySelector('[data-field="last_visit"]');
  if (lastVisit) {
    lastVisit.textContent = row.last_visit_display || row.last_visit || 'No visit';
  }
  const employeeName = statusRow.querySelector('[data-field="employee_name"]');
  if (employeeName) {
    employeeName.textContent = row.employee_name || 'No visit';
  }
  const statusPill = statusRow.querySelector('[data-field="status"]');
  if (statusPill) {
    statusPill.textContent = row.status || 'Critical';
    statusPill.className = `status-pill status-${String(row.status || 'Critical').toLowerCase()}`;
  }
}

async function submitFormAjax(formId) {
  const form = document.getElementById(formId);
  if (!form) {
    return;
  }

  const employeeSelect = form.querySelector('select[name="employee_id"]');
  if (employeeSelect && !employeeSelect.value) {
    alert('Please select an employee before saving.');
    employeeSelect.focus();
    return;
  }

  const associatedNumberInputs = [
    ...form.querySelectorAll('input[type="number"]'),
    ...document.querySelectorAll(`input[type="number"][form="${formId}"]`),
  ];
  associatedNumberInputs.forEach((input) => {
    if (String(input.value).trim() === '') {
      input.value = '0';
    }
  });

  const payload = new FormData(form);
  const response = await fetch(form.action, {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: payload,
  });

  if (!response.ok) {
    form.submit();
    return;
  }

  const data = await response.json();
  updateSummary(data.summary);
  const criticalReportLink = document.querySelector('[data-critical-report-link]');
  if (criticalReportLink && data.critical_report_mailto) {
    criticalReportLink.href = data.critical_report_mailto;
  }
  updateStatusRow(formId, data.row);
}

function submitInlineForm(formId) {
  submitFormAjax(formId).catch(() => {
    const form = document.getElementById(formId);
    if (form) {
      form.submit();
    }
  });
}

function applyDashboardFilter(rawQuery, rawStoreId = '') {
  const query = String(rawQuery || '').trim().toLowerCase();
  const storeId = String(rawStoreId || '').trim();
  const groups = document.querySelectorAll('[data-status-group]');
  let visibleCount = 0;

  groups.forEach((group) => {
    const matchesStore = !storeId || group.dataset.storeId === storeId;
    let groupVisibleCount = 0;

    group.querySelectorAll('[data-status-row]').forEach((row) => {
      const rowText = row.textContent.toLowerCase();
      const matchesQuery = !query || rowText.includes(query);
      const isVisible = matchesStore && matchesQuery;
      row.style.display = isVisible ? '' : 'none';
      if (isVisible) {
        groupVisibleCount += 1;
      }
    });

    group.style.display = groupVisibleCount > 0 ? '' : 'none';
    visibleCount += groupVisibleCount;
  });

  const emptyState = document.querySelector('.dashboard-filter-empty');
  if (emptyState) {
    emptyState.style.display = visibleCount === 0 ? '' : 'none';
  }

  return visibleCount;
}

document.addEventListener('DOMContentLoaded', () => {
  const searchBar = document.querySelector('.search-bar');
  if (!searchBar) {
    return;
  }

  const searchInput = searchBar.querySelector('input[name="search"]');
  const storeSelect = searchBar.querySelector('select[name="store_id"]');
  if (searchInput) {
    applyDashboardFilter(searchInput.value, storeSelect ? storeSelect.value : '');
  }

  searchBar.addEventListener('submit', (event) => {
    event.preventDefault();

    const query = searchInput ? searchInput.value : '';
    const storeId = storeSelect ? storeSelect.value : '';
    applyDashboardFilter(query, storeId);

    const url = new URL(window.location.href);
    if (query.trim()) {
      url.searchParams.set('search', query.trim());
    } else {
      url.searchParams.delete('search');
    }
    if (storeId) {
      url.searchParams.set('store_id', storeId);
    } else {
      url.searchParams.delete('store_id');
    }
    window.history.replaceState({}, '', url);
  });

  if (storeSelect) {
    storeSelect.addEventListener('change', () => {
      searchBar.requestSubmit();
    });
  }
});
