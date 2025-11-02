class ProteusScheduleCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      const card = document.createElement('ha-card');
      card.header = this.config.title || 'Proteus Plán';
      this.content = document.createElement('div');
      this.content.style.padding = '16px';
      card.appendChild(this.content);
      this.appendChild(card);
    }

    const entityId = this.config.entity;
    const stateObj = hass.states[entityId];

    if (!stateObj) {
      this.content.innerHTML = `<p>Entity ${entityId} not found</p>`;
      return;
    }

    const steps = stateObj.attributes.steps || [];
    const maxRows = this.config.max_rows || 12;
    const displaySteps = steps.slice(0, maxRows);

    // Vytvoř HTML tabulku
    let html = `
      <style>
        .proteus-schedule-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .proteus-schedule-table th {
          background: var(--primary-color);
          color: var(--text-primary-color);
          padding: 8px 4px;
          text-align: left;
          font-weight: 500;
          position: sticky;
          top: 0;
        }
        .proteus-schedule-table td {
          padding: 8px 4px;
          border-bottom: 1px solid var(--divider-color);
        }
        .proteus-schedule-table tr:hover {
          background: var(--table-row-background-hover-color, rgba(0, 0, 0, 0.05));
        }
        .mode-icon {
          font-size: 16px;
          margin-right: 4px;
        }
        .price-low {
          color: var(--success-color, green);
          font-weight: 500;
        }
        .price-high {
          color: var(--error-color, red);
          font-weight: 500;
        }
        .price-medium {
          color: var(--warning-color, orange);
          font-weight: 500;
        }
        .soc-value {
          font-weight: 500;
        }
      </style>
      <table class="proteus-schedule-table">
        <thead>
          <tr>
            <th>Čas</th>
            <th>Režim</th>
            <th>SoC</th>
            <th>Cena</th>
            ${this.config.show_predictions !== false ? '<th>Spotřeba</th><th>Výroba</th>' : ''}
          </tr>
        </thead>
        <tbody>
    `;

    // Zjisti cenový rozsah pro barevné rozlišení
    const prices = displaySteps.map(s => s.price_kwh).filter(p => p > 0);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    displaySteps.forEach(step => {
      // Urči barvu ceny
      let priceClass = 'price-medium';
      if (priceRange > 0) {
        const pricePct = (step.price_kwh - minPrice) / priceRange;
        if (pricePct < 0.33) priceClass = 'price-low';
        else if (pricePct > 0.66) priceClass = 'price-high';
      }

      html += `
        <tr>
          <td><strong>${step.time}</strong></td>
          <td>${step.mode}</td>
          <td class="soc-value">${step.target_soc}%</td>
          <td class="${priceClass}">${step.price_kwh} Kč/kWh</td>
          ${this.config.show_predictions !== false ? `
            <td>${step.predicted_consumption} Wh</td>
            <td>${step.predicted_production} Wh</td>
          ` : ''}
        </tr>
      `;
    });

    html += `
        </tbody>
      </table>
    `;

    if (steps.length > maxRows) {
      html += `<p style="text-align: center; color: var(--secondary-text-color); margin-top: 8px; font-size: 12px;">
        Zobrazeno ${maxRows} z ${steps.length} kroků
      </p>`;
    }

    this.content.innerHTML = html;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('You need to define an entity');
    }
    this.config = config;
  }

  getCardSize() {
    return (this.config.max_rows || 12) + 2;
  }
}

customElements.define('proteus-schedule-card', ProteusScheduleCard);

// Přidej kartu do HA card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'proteus-schedule-card',
  name: 'Proteus Schedule Card',
  description: 'Zobrazí nadcházející plán Proteus v tabulce',
  preview: true,
});
