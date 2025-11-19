# Proteus Delta Green API Documentation

## Přehled

Toto je dokumentace pro Proteus API (proteus.deltagreen.cz), které používá **tRPC** framework s batch requesty.

## Autentizace

### 1. Přihlášení

**Endpoint:** `POST /api/trpc/users.loginWithEmailAndPassword`

**Request Headers:**
```
Content-Type: application/json
Accept: */*
Origin: https://proteus.deltagreen.cz
Referer: https://proteus.deltagreen.cz/cs/auth/login/email-and-password
```

**Request Body:**
```json
{
  "json": {
    "email": "your-email@example.com",
    "password": "your-password",
    "tenantId": "TID_DELTA_GREEN"
  }
}
```

**Response:**
```json
{
  "result": {
    "data": {
      "json": {
        "nextUrl": "/"
      }
    }
  }
}
```

**Response Cookies:**
- `proteus_session` - Session cookie (HttpOnly, Secure, SameSite=lax)
- `proteus_csrf` - CSRF token cookie (Secure, SameSite=lax)

**Důležité:**
- Server vrací 2 cookies: `proteus_session` a `proteus_csrf`
- Obě jsou potřeba pro další API volání
- Session cookie je platná 30 dní
- CSRF token je také potřeba poslat v headeru `x-proteus-csrf`

---

## API Volání

### Obecný formát

Všechny tRPC endpointy používají následující formát:

**URL:** `GET /api/trpc/{procedure}?batch=1&input={encoded_json}`

**Required Headers:**
```
Cookie: proteus_csrf={csrf_token}; proteus_session={session_token}
x-proteus-csrf: {csrf_token}
trpc-accept: application/jsonl
Content-Type: application/json
Accept: */*
```

**Batch Input Format:**
```json
{
  "0": { "json": { ...params } },
  "1": { "json": { ...params } },
  ...
}
```

URL-encoded a přidán jako query parameter `input`.

**Response Format:**
API vrací **JSONL** (JSON Lines) - každý řádek je samostatný JSON objekt.

---

## Dostupné Endpointy

### 1. Control Plans Active

Získá aktivní kontrolní plány pro inverter (obsahuje časový rozvrh nabíjení/vybíjení baterie).

**Procedure:** `controlPlans.active`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

**Response obsahuje:**
- `activePlan` - Aktivní plán řízení
  - `id` - ID plánu
  - `createdAt`, `updatedAt` - Timestamps
  - `householdId` - ID domácnosti
  - `payload.steps[]` - Jednotlivé kroky plánu:
    - `id` - ID kroku
    - `startAt` - Začátek (ISO timestamp)
    - `durationMinutes` - Délka v minutách
    - `metadata`:
      - `flexalgoBattery` - Režim baterie (`charge_from_grid`, `discharge_to_household`, `do_not_discharge`, `default`)
      - `targetSoC` - Cílový State of Charge (%)
      - `priceMwh` - Cena za MWh
      - `predictedProduction` - Predikovaná produkce (Wh)
      - `predictedConsumption` - Predikovaná spotřeba (Wh)
      - `priceComponents` - Detailní cenové komponenty (distribuce, daně, POZE, ...)
    - `state` - Stav kroku:
      - `startedAt` - Čas zahájení
      - `finishedAt` - Čas dokončení

---

### 2. Inverter Detail

Získá detailní informace o inverteru.

**Procedure:** `inverters.detail`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

---

### 3. Inverter Extended Detail

Získá rozšířené detailní informace o inverteru.

**Procedure:** `inverters.extendedDetail`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

---

### 4. Inverter Last State

Získá poslední stav inverteru (real-time data).

**Procedure:** `inverters.lastState`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

**Response obsahuje:**
- Aktuální výkon (W)
- Stav baterie (SoC %)
- Produkce/spotřeba
- Timestamp posledního měření

---

### 5. Inverter Current Step

Získá aktuální krok z control plánu, který právě běží.

**Procedure:** `inverters.currentStep`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

---

### 6. LinkBox Connection State

Získá stav připojení LinkBoxu (brána mezi inverterem a cloudem).

**Procedure:** `linkBoxes.connectionState`

**Input:**
```json
{
  "json": {
    "householdId": "YOUR_HOUSEHOLD_ID"
  }
}
```

**Response:**
- `connected` - Boolean, zda je LinkBox připojen
- `lastSeen` - Timestamp posledního připojení

---

### 7. Current Commands

Získá aktuální příkazy poslané inverteru.

**Procedure:** `commands.current`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

---

### 8. Current Distribution Prices

Získá aktuální distribuční ceny elektřiny.

**Procedure:** `prices.currentDistributionPrices`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

**Response obsahuje:**
- Ceny za HT/LT tarif
- Distribuční poplatky
- Systémové služby
- POZE příspěvek

---

### 9. Flexibility Rewards Summary

Získá souhrn odměn za flexibilitu (úspory za optimalizaci).

**Procedure:** `inverters.flexibilityRewardsSummary`

**Input:**
```json
{
  "json": {
    "inverterId": "YOUR_INVERTER_ID"
  }
}
```

**Response:**
- Celkové úspory (Kč)
- Úspory za období
- Porovnání s neoptimalizovaným provozem

---

### 10. WebSocket Token

Získá token pro WebSocket připojení (real-time updates).

**Procedure:** `users.wsToken`

**Input:**
```json
{
  "json": {}
}
```

**Response:**
- `token` - JWT token pro WebSocket autentizaci
- `wsUrl` - URL WebSocket serveru

---

### 11. Kombinované volání (Batch)

API podporuje volání více procedur najednou:

**Příklad 1 - Plan Page (3 endpointy):**
```
/api/trpc/linkBoxes.connectionState,inverters.detail,controlPlans.active?batch=1&input={...}
```

**Příklad 2 - Dashboard (všechny endpointy):**
```
/api/trpc/linkBoxes.connectionState,inverters.detail,commands.current,inverters.currentStep,prices.currentDistributionPrices,users.wsToken,inverters.extendedDetail,inverters.lastState,inverters.flexibilityRewardsSummary?batch=1&input={...}
```

**Input:**
```json
{
  "0": { "json": { "householdId": "YOUR_HOUSEHOLD_ID" } },
  "1": { "json": { "inverterId": "YOUR_INVERTER_ID" } },
  "2": { "json": { "inverterId": "YOUR_INVERTER_ID" } },
  ...
}
```

Procedury se volají v pořadí zleva doprava, odpověď obsahuje výsledky pro každou proceduru.

---

## Implementace v Node.js

### Instalace

Žádné závislosti nejsou potřeba, používá native Node.js `https` modul.

### Příklad použití

```javascript
const ProteusAPI = require('./proteus-api-complete.js');

const api = new ProteusAPI();

// Přihlášení
await api.login('email@example.com', 'password');

// === JEDNOTLIVÉ ENDPOINTY ===

// Získání aktivního plánu řízení baterie
const controlPlans = await api.getControlPlansActive();

// Detail inverteru
const inverterDetail = await api.getInverterDetail();
const extendedDetail = await api.getInverterExtendedDetail();

// Real-time stav
const lastState = await api.getInverterLastState();
const currentStep = await api.getCurrentStep();

// Stav připojení
const linkBoxState = await api.getLinkBoxConnectionState();

// Příkazy a ceny
const commands = await api.getCurrentCommands();
const prices = await api.getCurrentDistributionPrices();

// Odměny
const rewards = await api.getFlexibilityRewardsSummary();

// WebSocket token
const wsToken = await api.getWSToken();

// === KOMBINOVANÁ VOLÁNÍ (BATCH) ===

// Plan Page (3 endpointy najednou)
const planPage = await api.getInverterPlanPage();

// Kompletní Dashboard (všechny endpointy najednou - nejvíce efektivní)
const dashboard = await api.getDashboardData();

// Uložení dat do souboru
api.saveToFile('dashboard.json', dashboard);
```

### Kompletní třída

Viz soubor `proteus-api-complete.js` v tomto adresáři.

---

## Důležité poznámky

### CSRF Token
- **MUSÍ** být přítomen v cookie `proteus_csrf`
- **MUSÍ** být přítomen v headeru `x-proteus-csrf` (ne `x-csrf-token`!)
- Získává se automaticky při přihlášení

### Response Format
- API vrací **JSONL** (JSON Lines)
- Každý řádek musí být parsován samostatně
- Header `trpc-accept: application/jsonl` je povinný

### Session Management
- Session cookie je platná 30 dní
- Po expiraci je nutné se znovu přihlásit
- Doporučuji ukládat session token pro opakované použití

### Error Handling
- Status 403 = Invalid CSRF token (zkontrolujte cookie a header)
- Status 401 = Neautorizováno (je potřeba se přihlásit)
- Status 404 = Procedure neexistuje

---

## Data Modely

### ControlPlan Step

```typescript
interface ControlPlanStep {
  id: string;
  startAt: string; // ISO timestamp
  durationMinutes: number;
  metadata: {
    flexalgoBattery: 'charge_from_grid' | 'discharge_to_household' | 'do_not_discharge' | 'default';
    flexalgoBatteryFallback: string;
    flexalgoPv: 'unrestricted' | string;
    targetSoC: number; // 0-100%
    priceMwh: number; // Kč/MWh
    priceMwhConsumption: number;
    priceMwhProduction: number;
    priceComponents: {
      distributionPrice: number;
      distributionTariffType: 'HT' | 'LT' | 'HT/LT';
      feeElectricityBuy: number;
      feeElectricitySell: number;
      taxElectricity: number;
      systemServices: number;
      poze: number;
      vatRate: number;
    };
    isPrediction: boolean;
    netSign: number;
    predictedProduction: number; // Wh
    predictedConsumption: number; // Wh
    currencyCode: 'CZK';
  };
  state: {
    startedAt?: string;
    finishedAt?: string;
  };
  dependsOn?: string; // ID předchozího kroku
}
```

---

## Rate Limiting

Nebyly zjištěny žádné explicitní rate limity, ale doporučuji:
- Max 1 request per second
- Používat batch volání pro snížení počtu requestů
- Cachovat data na klientovi

---

## Další Endpointy

API pravděpodobně obsahuje další endpointy (nebyly testovány):
- `inverters.list` - Seznam inverterů
- `households.detail` - Detail domácnosti
- `users.getCurrentUser` - Aktuální uživatel
- `energyData.*` - Různá energetická data

Pro zjištění dalších endpointů doporučuji analyzovat Network tab v DevTools při procházení aplikace.

---

## Licence & Disclaimers

- Toto je neoficiální dokumentace vytvořená na základě reverse engineeringu
- API není veřejné a může se kdykoliv změnit
- Použití na vlastní riziko
- Respektujte Terms of Service poskytovatele

---

## Autor

Generated by Claude (Anthropic) - 2025-11-02

## Changelog

### v1.1 (2025-11-02)
- Přidáno 7 nových endpointů:
  - `commands.current` - Aktuální příkazy
  - `inverters.currentStep` - Aktuální krok plánu
  - `prices.currentDistributionPrices` - Distribuční ceny
  - `users.wsToken` - WebSocket token
  - `inverters.extendedDetail` - Rozšířené detaily
  - `inverters.lastState` - Poslední stav (real-time)
  - `inverters.flexibilityRewardsSummary` - Souhrn odměn
- Přidána metoda `getDashboardData()` pro získání všech dat najednou
- Rozšířená dokumentace s příklady

### v1.0 (2025-11-02)
- Initial documentation
- Login endpoint
- Control Plans Active endpoint
- Batch API support
- CSRF token handling (`x-proteus-csrf`)
- JSONL response format
- 3 základní endpointy (controlPlans, inverters.detail, linkBoxes)
