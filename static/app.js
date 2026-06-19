function updateSummary(summary) {
  for (const [key, value] of Object.entries(summary || {})) {
    const element = document.querySelector(`[data-summary-key="${key}"]`);
    if (element) {
      element.textContent = value;
    }
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }[character]));
}

function updateStoreOverview(overview) {
  if (!overview) {
    return;
  }

  const countMap = {
    critical_stores: overview.critical_stores,
    unhealthy_stores: overview.unhealthy_stores,
    overdue_stores: overview.overdue_stores,
    expiring_skus: overview.expiring_skus,
    total: overview.total,
    critical: overview.counts?.Critical,
    unhealthy: overview.counts?.Unhealthy,
    healthy: overview.counts?.Healthy,
  };
  for (const [key, value] of Object.entries(countMap)) {
    const element = document.querySelector(`[data-overview-count="${key}"]`);
    if (element) {
      element.textContent = value ?? 0;
    }
  }

  const donut = document.querySelector('[data-overview-donut]');
  if (donut && overview.donut_style) {
    donut.style.cssText = overview.donut_style;
  }

  const body = document.querySelector('[data-store-overview-body]');
  if (!body) {
    return;
  }

  const rows = overview.rows || [];
  if (!rows.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="7" class="empty-state">No store status available yet.</td></tr>';
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr data-overview-row data-store-id="${escapeHtml(row.store_id)}" data-city-id="${escapeHtml(row.city_id || '')}">
      <td data-label="Store">${escapeHtml(row.store_name)}${row.city_name ? `<br><small>${escapeHtml(row.city_name)}</small>` : ''}</td>
      <td data-label="Status"><span class="status-pill status-${escapeHtml(row.status_lower)}">${escapeHtml(row.status)}</span></td>
      <td data-label="Critical SKUs">${escapeHtml(row.critical_skus)}</td>
      <td data-label="Expiring">${escapeHtml(row.expiring_total)}</td>
      <td data-label="Last visit">${escapeHtml(row.last_visit_display)}</td>
      <td data-label="Monthly visits">${escapeHtml(row.monthly_visits_made)}/${escapeHtml(row.monthly_expected_by_today)} (${escapeHtml(row.monthly_completion_percent)}%)</td>
      <td data-label="Action">${escapeHtml(row.action)}</td>
    </tr>
  `).join('');
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
  updateStoreOverview(data.store_overview);
  updateStatusRow(formId, data.row);
  applyCurrentDashboardFilter();
}

function submitInlineForm(formId) {
  submitFormAjax(formId).catch(() => {
    const form = document.getElementById(formId);
    if (form) {
      form.submit();
    }
  });
}

function applyDashboardFilter(rawQuery, rawStoreId = '', rawCityId = '') {
  const query = String(rawQuery || '').trim().toLowerCase();
  const storeId = String(rawStoreId || '').trim();
  const cityId = String(rawCityId || '').trim();
  const groups = document.querySelectorAll('[data-status-group]');
  let visibleCount = 0;

  groups.forEach((group) => {
    const matchesStore = !storeId || group.dataset.storeId === storeId;
    const matchesCity = !cityId || group.dataset.cityId === cityId;
    let groupVisibleCount = 0;

    group.querySelectorAll('[data-status-row]').forEach((row) => {
      const rowText = row.textContent.toLowerCase();
      const matchesQuery = !query || rowText.includes(query);
      const isVisible = matchesStore && matchesCity && matchesQuery;
      row.style.display = isVisible ? '' : 'none';
      if (isVisible) {
        groupVisibleCount += 1;
      }
    });

    group.style.display = groupVisibleCount > 0 ? '' : 'none';
    visibleCount += groupVisibleCount;
  });

  document.querySelectorAll('[data-overview-row]').forEach((row) => {
    const rowText = row.textContent.toLowerCase();
    const matchesQuery = !query || rowText.includes(query);
    const matchesStore = !storeId || row.dataset.storeId === storeId;
    const matchesCity = !cityId || row.dataset.cityId === cityId;
    row.style.display = matchesQuery && matchesStore && matchesCity ? '' : 'none';
  });

  const emptyState = document.querySelector('.dashboard-filter-empty');
  if (emptyState) {
    emptyState.style.display = visibleCount === 0 ? '' : 'none';
  }

  return visibleCount;
}

function applyCurrentDashboardFilter() {
  const searchBar = document.querySelector('.search-bar');
  if (!searchBar) {
    return;
  }
  const searchInput = searchBar.querySelector('input[name="search"]');
  const storeSelect = searchBar.querySelector('select[name="store_id"]');
  const citySelect = searchBar.querySelector('select[name="city_id"]');
  applyDashboardFilter(searchInput ? searchInput.value : '', storeSelect ? storeSelect.value : '', citySelect ? citySelect.value : '');
}

document.addEventListener('DOMContentLoaded', () => {
  const searchBar = document.querySelector('.search-bar');
  if (!searchBar) {
    return;
  }

  const searchInput = searchBar.querySelector('input[name="search"]');
  const citySelect = searchBar.querySelector('select[name="city_id"]');
  const storeSelect = searchBar.querySelector('select[name="store_id"]');
  if (searchInput) {
    applyDashboardFilter(searchInput.value, storeSelect ? storeSelect.value : '', citySelect ? citySelect.value : '');
  }

  searchBar.addEventListener('submit', (event) => {
    event.preventDefault();

    const query = searchInput ? searchInput.value : '';
    const cityId = citySelect ? citySelect.value : '';
    const storeId = storeSelect ? storeSelect.value : '';
    applyDashboardFilter(query, storeId, cityId);

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
    if (cityId) {
      url.searchParams.set('city_id', cityId);
    } else {
      url.searchParams.delete('city_id');
    }
    window.history.replaceState({}, '', url);
  });

  if (citySelect) {
    citySelect.addEventListener('change', () => {
      searchBar.requestSubmit();
    });
  }

  if (storeSelect) {
    storeSelect.addEventListener('change', () => {
      searchBar.requestSubmit();
    });
  }
});
