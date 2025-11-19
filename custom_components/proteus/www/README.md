# Proteus Schedule Card

Custom Lovelace card pro grafické zobrazení nadcházejícího plánu Proteus.

## Instalace

### Krok 1: Přidat jako resource

1. Otevři **Settings** → **Dashboards** → **Resources** (vpravo nahoře tři tečky)
2. Klikni **Add Resource**
3. URL: `/local/community/proteus/proteus-schedule-card.js`
4. Resource type: **JavaScript Module**
5. Klikni **Create**

### Krok 2: Zkopírovat soubor

Zkopíruj `proteus-schedule-card.js` do:
```
/config/www/community/proteus/proteus-schedule-card.js
```

Nebo pokud máš custom_components:
```
/config/custom_components/proteus/www/proteus-schedule-card.js
```

A v Resources použij URL:
```
/local/custom_components/proteus/www/proteus-schedule-card.js
```

### Krok 3: Restartuj HomeAssistant

## Použití v Lovelace

### Základní konfigurace

```yaml
type: custom:proteus-schedule-card
entity: sensor.proteus_upcoming_schedule
title: Proteus Plán
max_rows: 12
```

### Kompletní konfigurace

```yaml
type: custom:proteus-schedule-card
entity: sensor.proteus_upcoming_schedule
title: Nadcházející plán
max_rows: 24          # Počet zobrazených řádků (hodin)
show_predictions: true # Zobrazit predikce spotřeby/výroby
```

### Malá karta (sidebar)

```yaml
type: custom:proteus-schedule-card
entity: sensor.proteus_upcoming_schedule
title: Příštích 6 hodin
max_rows: 6
show_predictions: false
```

### Velká karta (celý den)

```yaml
type: custom:proteus-schedule-card
entity: sensor.proteus_upcoming_schedule
title: Dnešní a zítřejší plán
max_rows: 48
```

## Parametry

| Parametr | Povinný | Default | Popis |
|----------|---------|---------|-------|
| `entity` | Ano | - | ID sensoru `sensor.proteus_upcoming_schedule` |
| `title` | Ne | "Proteus Plán" | Název karty |
| `max_rows` | Ne | 12 | Maximální počet zobrazených hodin |
| `show_predictions` | Ne | true | Zobrazit sloupce se spotřebou a výrobou |

## Funkce

- ✅ **Barevné rozlišení cen**: Levné (zelená), střední (oranžová), drahé (červená)
- ✅ **Emoji ikony**: Pro režimy baterie (⚡🔋☀️⏸️🔄)
- ✅ **Sticky header**: Záhlaví tabulky zůstává nahoře při scrollování
- ✅ **Hover efekt**: Zvýraznění řádku při najetí myší
- ✅ **Responzivní**: Přizpůsobí se velikosti karty
- ✅ **Dark mode**: Automaticky použije HA téma

## Screenshot

Karta zobrazí tabulku s:
- **Čas**: Datum a hodina
- **Režim**: Emoji + text (např. "⚡ Nabíjení ze sítě")
- **SoC**: Cílový stav baterie (%)
- **Cena**: Barevně rozlišená cena elektřiny (Kč/kWh)
- **Spotřeba**: Predikovaná spotřeba (Wh) - volitelné
- **Výroba**: Predikovaná výroba z FVE (Wh) - volitelné

## Tipy

### Přidat do mobile dashboardu
Použij `max_rows: 6` pro kompaktní zobrazení

### Přidat do grafu
Kombinuj s dalšími kartami:

```yaml
type: vertical-stack
cards:
  - type: custom:proteus-schedule-card
    entity: sensor.proteus_upcoming_schedule
    max_rows: 12
  - type: entities
    entities:
      - sensor.proteus_battery_soc
      - sensor.proteus_current_price
```

### Zobrazit jen levné hodiny
Pro filtrování použij custom template sensor a zobraz jen kroky s cenou < 5 Kč/kWh.
