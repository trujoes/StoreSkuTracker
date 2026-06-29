function updateSummary(summary) {
  for (const [key, value] of Object.entries(summary || {})) {
    const element = document.querySelector(`[data-summary-key="${key}"]`);
    if (element) {
      element.textContent = value;
    }
  }
}

function preserveScrollForCurrentPage() {
  sessionStorage.setItem(`stockTrackerScroll:${window.location.pathname}`, String(window.scrollY));
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
    document.querySelectorAll(`[data-overview-count="${key}"]`).forEach((element) => {
      element.textContent = value ?? 0;
    });
  }

  if (overview.donut_style) {
    document.querySelectorAll('[data-overview-donut]').forEach((donut) => {
      donut.style.cssText = overview.donut_style;
    });
  }

  updateMobileStoreSnapshot(overview.rows || []);

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
    <tr
      data-overview-row
      data-store-id="${escapeHtml(row.store_id)}"
      data-city-id="${escapeHtml(row.city_id || '')}"
      data-status="${escapeHtml(row.status)}"
      data-overdue="${row.is_overdue ? '1' : '0'}"
      data-expiring-skus="${escapeHtml(row.expiring_skus)}"
    >
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

function updateMobileStoreSnapshot(rows) {
  const list = document.querySelector('[data-mobile-store-snapshot-list]');
  if (!list) {
    return;
  }

  if (!rows.length) {
    list.innerHTML = '<p class="empty-state">No store status available yet.</p>';
    return;
  }

  list.innerHTML = rows.map((row) => {
    const skuCounts = (row.sku_breakdown || []).map((sku) => `
      <span class="mobile-sku-count status-${escapeHtml(sku.status_lower)}">
        <strong>${escapeHtml(sku.sku_name)}</strong>
        <em>${escapeHtml(sku.shelf_count)}/${escapeHtml(sku.recommended_count)}</em>
      </span>
    `).join('');
    return `
    <div class="mobile-store-snapshot-row">
      <div>
        <strong>${escapeHtml(row.store_name)}</strong>
        <span>${row.city_name ? `${escapeHtml(row.city_name)} · ` : ''}${escapeHtml(row.last_visit_display)}</span>
      </div>
      <span class="status-pill status-${escapeHtml(row.status_lower)}">${escapeHtml(row.status)}</span>
      <div class="mobile-store-sku-counts">${skuCounts}</div>
      <small>${escapeHtml(row.action)}</small>
    </div>
  `;
  }).join('');
}

function buildDonutStyle(counts, total) {
  if (!total) {
    return 'background: #f3dede;';
  }

  const criticalDegrees = (counts.Critical || 0) / total * 360;
  const unhealthyDegrees = criticalDegrees + (counts.Unhealthy || 0) / total * 360;
  return [
    'background: conic-gradient(',
    `#f6c7c1 0deg ${criticalDegrees.toFixed(1)}deg, `,
    `#fce7b7 ${criticalDegrees.toFixed(1)}deg ${unhealthyDegrees.toFixed(1)}deg, `,
    `#dcefdc ${unhealthyDegrees.toFixed(1)}deg 360deg);`,
  ].join('');
}

function updateFilteredOverviewStats() {
  const visibleRows = [...document.querySelectorAll('[data-overview-row]')]
    .filter((row) => row.style.display !== 'none');
  const counts = { Healthy: 0, Unhealthy: 0, Critical: 0 };
  let overdueStores = 0;
  let expiringSkus = 0;

  visibleRows.forEach((row) => {
    const status = row.dataset.status || 'Healthy';
    if (Object.prototype.hasOwnProperty.call(counts, status)) {
      counts[status] += 1;
    }
    if (row.dataset.overdue === '1') {
      overdueStores += 1;
    }
    expiringSkus += Number(row.dataset.expiringSkus || 0);
  });

  const total = visibleRows.length;
  const countMap = {
    critical_stores: counts.Critical,
    unhealthy_stores: counts.Unhealthy,
    overdue_stores: overdueStores,
    expiring_skus: expiringSkus,
    total,
    critical: counts.Critical,
    unhealthy: counts.Unhealthy,
    healthy: counts.Healthy,
  };
  for (const [key, value] of Object.entries(countMap)) {
    document.querySelectorAll(`[data-overview-count="${key}"]`).forEach((element) => {
      element.textContent = value;
    });
  }

  document.querySelectorAll('[data-overview-donut]').forEach((donut) => {
    donut.style.cssText = buildDonutStyle(counts, total);
  });
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
    preserveScrollForCurrentPage();
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
      preserveScrollForCurrentPage();
      form.submit();
    }
  });
}

function applyDashboardFilter(rawQuery, rawStoreId = '', rawCityId = '') {
  const query = String(rawQuery || '').trim().toLowerCase();
  const storeId = String(rawStoreId || '').trim();
  const cityId = String(rawCityId || '').trim();
  const hasFilter = Boolean(query || storeId || cityId);
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
  updateFilteredOverviewStats();

  const emptyState = document.querySelector('.dashboard-filter-empty');
  if (emptyState) {
    emptyState.style.display = hasFilter && visibleCount === 0 ? '' : 'none';
  }

  const statusGroupList = document.querySelector('[data-status-group-list]');
  if (statusGroupList) {
    statusGroupList.classList.toggle('mobile-filter-required', !hasFilter);
  }

  const mobileFilterPrompt = document.querySelector('[data-mobile-filter-prompt]');
  if (mobileFilterPrompt) {
    mobileFilterPrompt.classList.toggle('mobile-filter-prompt-hidden', hasFilter);
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

function updateInventorySummary(summary) {
  for (const [key, value] of Object.entries(summary || {})) {
    const element = document.querySelector(`[data-inventory-summary="${key}"]`);
    if (element) {
      element.textContent = value;
    }
  }
}

function updateInventoryRow(rowElement, item) {
  if (!rowElement || !item) {
    return;
  }

  const quantity = rowElement.querySelector('[data-field="inventory_quantity"]');
  if (quantity) {
    quantity.textContent = item.quantity ?? 0;
  }

  const minimum = rowElement.querySelector('[data-field="inventory_minimum"]');
  if (minimum) {
    minimum.textContent = item.emergency_minimum ?? 0;
  }

  const updated = rowElement.querySelector('[data-field="inventory_updated"]');
  if (updated) {
    updated.textContent = item.updated_display || 'Just now';
  }

  const warning = rowElement.querySelector('[data-field="inventory_warning"]');
  if (warning) {
    warning.hidden = !item.is_low_stock;
  }

  rowElement.querySelectorAll('form[action$="/set"] input[name="quantity"]').forEach((input) => {
    input.value = item.quantity ?? 0;
  });

}

async function submitInventorySave(form) {
  const response = await fetch(form.action, {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: new FormData(form),
  });

  if (!response.ok) {
    preserveScrollForCurrentPage();
    form.submit();
    return;
  }

  const data = await response.json();
  updateInventoryRow(form.closest('[data-inventory-row]'), data.item);
  updateInventorySummary(data.summary);
}

function bindInventorySteppers() {
  document.querySelectorAll('[data-inventory-stepper]').forEach((stepper) => {
    stepper.addEventListener('click', (event) => {
      const button = event.target.closest('[data-inventory-step]');
      if (!button) {
        return;
      }

      const row = button.closest('[data-inventory-row]');
      const exactInputs = row ? [...row.querySelectorAll('form[action$="/set"] input[name="quantity"]')] : [];
      const exactInput = exactInputs.find((input) => input.offsetParent !== null) || exactInputs[0];
      if (!exactInput) {
        return;
      }

      const currentValue = Number.parseInt(exactInput.value || '0', 10);
      const adjustment = Number.parseInt(button.dataset.inventoryStep || '0', 10);
      const safeCurrentValue = Number.isNaN(currentValue) ? 0 : currentValue;
      const safeAdjustment = Number.isNaN(adjustment) ? 0 : adjustment;
      exactInput.value = Math.max(safeCurrentValue + safeAdjustment, 0);
      exactInput.focus();
    });
  });
}

function bindInventorySaves() {
  document.querySelectorAll('[data-inventory-save-form]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      submitInventorySave(form).catch(() => {
        preserveScrollForCurrentPage();
        form.submit();
      });
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  bindInventorySteppers();
  bindInventorySaves();

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
