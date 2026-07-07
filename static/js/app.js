function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function filterCards(gridSelector, criteria) {
  const cards = document.querySelectorAll(gridSelector);
  cards.forEach((card) => {
    const text = normalize(card.dataset.search);
    const brand = normalize(card.dataset.brand);
    const status = normalize(card.dataset.status);
    const trim = normalize(card.dataset.trim);

    const matchesSearch = !criteria.search || text.includes(criteria.search);
    const matchesBrand = !criteria.brand || brand === criteria.brand;
    const matchesStatus = !criteria.status || status === criteria.status;
    const matchesTrim = !criteria.trim || trim === criteria.trim;

    card.classList.toggle('hidden-card', !(matchesSearch && matchesBrand && matchesStatus && matchesTrim));
  });
}

function bindManagementFilters() {
  const search = document.querySelector('#car-search');
  const status = document.querySelector('#status-filter');
  const brand = document.querySelector('#brand-filter');
  const trim = document.querySelector('#trim-filter');
  const reset = document.querySelector('#reset-filters');

  if (!search || !status || !brand || !trim || !reset) {
    return;
  }

  const apply = () => filterCards('#fleet-grid .vehicle-card', {
    search: normalize(search.value),
    status: normalize(status.value),
    brand: normalize(brand.value),
    trim: normalize(trim.value),
  });

  [search, status, brand, trim].forEach((field) => field.addEventListener('input', apply));
  reset.addEventListener('click', () => {
    search.value = '';
    status.value = '';
    brand.value = '';
    trim.value = '';
    apply();
  });

  apply();
}

function bindCatalogFilters() {
  const search = document.querySelector('#catalog-search');
  const brand = document.querySelector('#catalog-brand-filter');
  const trim = document.querySelector('#catalog-trim-filter');
  const status = document.querySelector('#catalog-status-filter');
  const reset = document.querySelector('#catalog-reset-filters');

  if (!search || !brand || !trim || !status || !reset) {
    return;
  }

  const apply = () => filterCards('#catalog-grid .catalog-card', {
    search: normalize(search.value),
    brand: normalize(brand.value),
    status: normalize(status.value),
    trim: normalize(trim.value),
  });

  [search, brand, trim, status].forEach((field) => field.addEventListener('input', apply));
  reset.addEventListener('click', () => {
    search.value = '';
    brand.value = '';
    trim.value = '';
    status.value = '';
    apply();
  });

  apply();
}

function bindCalendar() {
  const calendarEl = document.querySelector('#arrival-calendar');
  if (!calendarEl || typeof FullCalendar === 'undefined') {
    return;
  }

  const events = Array.isArray(window.CALENDAR_EVENTS) ? window.CALENDAR_EVENTS : [];
  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    height: 'auto',
    firstDay: 1,
    locale: 'it',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,listWeek',
    },
    buttonText: {
      today: 'Oggi',
      month: 'Mese',
      week: 'Settimana',
      list: 'Lista',
    },
    events,
    eventDidMount(info) {
      info.el.title = `${info.event.title} · ${info.event.extendedProps.status}`;
    },
    eventContent(arg) {
      const status = arg.event.extendedProps.status || '';
      const dateLabel = arg.event.extendedProps.dateLabel || '';
      return {
        html: `<div class="fc-event-wrap"><strong>${arg.event.title}</strong><div>${dateLabel}</div><div>${status}</div></div>`,
      };
    },
  });

  calendar.render();
}

document.addEventListener('DOMContentLoaded', () => {
  bindManagementFilters();
  bindCatalogFilters();
  bindCalendar();
});
