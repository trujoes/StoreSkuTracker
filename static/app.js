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

  const tableRow = form.closest('tr');
  if (!tableRow) {
    return;
  }
  tableRow.classList.toggle('stale-row', Boolean(row.is_stale));

  const cells = tableRow.querySelectorAll('td');
  if (cells.length < 9) {
    return;
  }

  cells[3].querySelector('input').value = row.shelf_count ?? '';
  cells[4].querySelector('input').value = row.expiring_count ?? '';
  cells[5].textContent = row.last_visit_display || row.last_visit || 'No visit';
  cells[6].textContent = row.employee_name || 'No visit';
  const statusPill = cells[7].querySelector('.status-pill');
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
  const rows = document.querySelectorAll('tr[data-store-id]');
  let visibleCount = 0;

  rows.forEach((row) => {
    const rowText = row.textContent.toLowerCase();
    const matchesQuery = !query || rowText.includes(query);
    const matchesStore = !storeId || row.dataset.storeId === storeId;
    const isVisible = matchesQuery && matchesStore;
    row.style.display = isVisible ? '' : 'none';
    if (isVisible) {
      visibleCount += 1;
    }
  });

  const emptyStateRow = document.querySelector('td.empty-state')?.closest('tr');
  if (emptyStateRow) {
    emptyStateRow.style.display = visibleCount === 0 ? '' : 'none';
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
