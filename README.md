# Proteus API - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Integrace pro Home Assistant, která umožňuje sledovat data z Proteus API (Delta Green).

## Funkce

- 📊 **Monitoring baterie**: Stav nabití (SoC), výkon, cílový stav, režim
- ⚡ **Sledování výkonu**: Výroba z FVE, spotřeba, síť, baterie
- 📈 **Energie**: Denní statistiky výroby, spotřeby, importu a exportu
- 💰 **Ceny elektřiny**: Aktuální cena, příští hodina, nejlevnější hodina dne
- 📅 **Kalendář**: Plán řízení baterie na další dny
- 🔍 **Binary sensory**: Detekce nejlevnější hodiny a 4-hodinového bloku

## Instalace přes HACS

### 1. Přidání custom repository

1. Otevřete HACS v Home Assistant
2. Klikněte na **Integrations**
3. Klikněte na tři tečky v pravém horním rohu
4. Vyberte **Custom repositories**
5. Přidejte URL tohoto repozitáře: `https://github.com/LynSisCZ/HomeAssitant-Proteus-API`
6. Kategorie: **Integration**
7. Klikněte **Add**

### 2. Instalace integrace

1. V HACS klikněte na **Explore & Download Repositories**
2. Vyhledejte "Proteus API"
3. Klikněte **Download**
4. Restartujte Home Assistant

### 3. Konfigurace

1. Přejděte do **Settings** → **Devices & Services**
2. Klikněte **Add Integration**
3. Vyhledejte "Proteus API"
4. Zadejte přihlašovací údaje:
   - **Email**: Váš email do Proteus
   - **Heslo**: Vaše heslo
   - **Inverter ID** (volitelné): ID vašeho měniče
   - **Household ID** (volitelné): ID vaší domácnosti

> **Poznámka**: Pokud nezadáte Inverter ID a Household ID, integrace automaticky najde všechny dostupné měniče a použije první.

## Manuální instalace

1. Stáhněte složku `custom_components/proteus`
2. Zkopírujte ji do složky `custom_components` ve vaší Home Assistant instalaci
3. Restartujte Home Assistant
4. Přidejte integraci přes **Settings** → **Devices & Services**

## Dostupné senzory

### Baterie
- `sensor.proteus_battery_soc` - Stav nabití baterie (%)
- `sensor.proteus_battery_power` - Výkon baterie (W)
- `sensor.proteus_battery_target_soc` - Cílový stav nabití (%)
- `sensor.proteus_battery_mode` - Režim baterie

### Výkon
- `sensor.proteus_production_power` - Výkon FVE (W)
- `sensor.proteus_consumption_power` - Spotřeba (W)
- `sensor.proteus_grid_power` - Výkon ze/do sítě (W)

### Energie
- `sensor.proteus_daily_production` - Denní výroba (kWh)
- `sensor.proteus_daily_consumption` - Denní spotřeba (kWh)
- `sensor.proteus_daily_grid_import` - Denní import ze sítě (kWh)
- `sensor.proteus_daily_grid_export` - Denní export do sítě (kWh)

### Ceny
- `sensor.proteus_current_price` - Aktuální cena (Kč/kWh)
- `sensor.proteus_next_hour_price` - Cena příští hodiny (Kč/kWh)
- `sensor.proteus_cheapest_hour_today` - Nejlevnější hodina dnes

### Binary sensory
- `binary_sensor.proteus_cheapest_hour` - Je právě nejlevnější hodina? (on/off)
- `binary_sensor.proteus_cheapest_4h_block` - Je právě nejlevnější 4h blok? (on/off)

### Ostatní
- `sensor.proteus_current_step` - Aktuální krok plánu
- `sensor.proteus_upcoming_schedule` - Nadcházející plán
- `sensor.proteus_connection_state` - Stav připojení
- `calendar.proteus_control_plan` - Kalendář plánu řízení

## Custom Lovelace Card

Integrace obsahuje vlastní grafickou kartu pro zobrazení nadcházejícího plánu.

### Instalace karty

1. Karta je automaticky v `/config/www/community/proteus/proteus-schedule-card.js`
2. Přejdi do **Settings** → **Dashboards** → **Resources**
3. Klikni **Add Resource**
4. URL: `/local/community/proteus/proteus-schedule-card.js`
5. Type: **JavaScript Module**

### Použití v dashboardu

```yaml
type: custom:proteus-schedule-card
entity: sensor.proteus_upcoming_schedule
title: Proteus Plán
max_rows: 12
show_predictions: true
```

**Parametry:**
- `max_rows` - Počet zobrazených hodin (default: 12)
- `show_predictions` - Zobrazit predikce spotřeby/výroby (default: true)

Kompletní návod viz `/config/custom_components/proteus/www/README.md`

## Podpora

Pro hlášení chyb nebo návrhy na vylepšení použijte [GitHub Issues](https://github.com/LynSisCZ/HomeAssitant-Proteus-API/issues).

## Licence

MIT License
