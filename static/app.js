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
  if (cells.length < 8) {
    return;
  }

  cells[3].querySelector('input').value = row.shelf_count ?? '';
  cells[4].querySelector('input').value = row.expiring_count ?? '';
  cells[5].textContent = row.last_visit || '—';
  const statusPill = cells[6].querySelector('.status-pill');
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

function applyDashboardFilter(rawQuery) {
  const query = String(rawQuery || '').trim().toLowerCase();
  const rows = document.querySelectorAll('tr[data-store-id]');
  let visibleCount = 0;

  rows.forEach((row) => {
    const rowText = row.textContent.toLowerCase();
    const isVisible = !query || rowText.includes(query);
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
  if (searchInput) {
    applyDashboardFilter(searchInput.value);
  }

  searchBar.addEventListener('submit', (event) => {
    event.preventDefault();

    const query = searchInput ? searchInput.value : '';
    applyDashboardFilter(query);

    const url = new URL(window.location.href);
    if (query.trim()) {
      url.searchParams.set('search', query.trim());
    } else {
      url.searchParams.delete('search');
    }
    window.history.replaceState({}, '', url);
  });
});
