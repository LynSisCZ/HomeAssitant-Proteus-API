const https = require('https');
const fs = require('fs');

class ProteusAPI {
  constructor() {
    this.sessionCookie = null;
    this.csrfToken = null;
    this.inverterId = null;  // Set your inverter ID or leave null to auto-detect
    this.householdId = null; // Set your household ID or leave null to auto-detect
  }

  // Přihlášení
  async login(email, password) {
    return new Promise((resolve, reject) => {
      const postData = JSON.stringify({
        json: {
          email: email,
          password: password,
          tenantId: "TID_DELTA_GREEN"
        }
      });

      const options = {
        hostname: 'proteus.deltagreen.cz',
        path: '/api/trpc/users.loginWithEmailAndPassword',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData),
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept': '*/*',
          'Origin': 'https://proteus.deltagreen.cz',
          'Referer': 'https://proteus.deltagreen.cz/cs/auth/login/email-and-password'
        }
      };

      const req = https.request(options, (res) => {
        let data = '';

        const cookies = res.headers['set-cookie'];
        if (cookies) {
          cookies.forEach(cookie => {
            const sessionMatch = cookie.match(/proteus_session=([^;]+)/);
            const csrfMatch = cookie.match(/proteus_csrf=([^;]+)/);
            if (sessionMatch) this.sessionCookie = sessionMatch[1];
            if (csrfMatch) this.csrfToken = csrfMatch[1];
          });
        }

        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          if (res.statusCode === 200) {
            console.log('✅ Login successful');
            console.log('Session:', this.sessionCookie);
            console.log('CSRF:', this.csrfToken);
            resolve(JSON.parse(data));
          } else {
            reject(new Error(`Login failed: ${res.statusCode}`));
          }
        });
      });

      req.on('error', reject);
      req.write(postData);
      req.end();
    });
  }

  // Generická funkce pro TRPC volání
  async callTRPC(procedures, inputs) {
    return new Promise((resolve, reject) => {
      const procedureStr = Array.isArray(procedures) ? procedures.join(',') : procedures;

      const batchInput = {};
      inputs.forEach((input, index) => {
        batchInput[index.toString()] = input;
      });

      const queryParams = `batch=1&input=${encodeURIComponent(JSON.stringify(batchInput))}`;

      const options = {
        hostname: 'proteus.deltagreen.cz',
        path: `/api/trpc/${procedureStr}?${queryParams}`,
        method: 'GET',
        headers: {
          'Cookie': `proteus_csrf=${this.csrfToken}; proteus_session=${this.sessionCookie}`,
          'x-proteus-csrf': this.csrfToken,
          'trpc-accept': 'application/jsonl',
          'Content-Type': 'application/json',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept': '*/*',
          'Referer': 'https://proteus.deltagreen.cz/',
          'sec-fetch-dest': 'empty',
          'sec-fetch-mode': 'cors',
          'sec-fetch-site': 'same-origin'
        }
      };

      const req = https.request(options, (res) => {
        let data = '';

        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          console.log(`\n=== ${procedureStr} ===`);
          console.log('Status:', res.statusCode);

          if (res.statusCode === 200) {
            // Parse JSONL response
            const lines = data.trim().split('\n');
            const results = lines.map(line => {
              try {
                return JSON.parse(line);
              } catch (e) {
                return line;
              }
            });
            console.log('Response:', JSON.stringify(results, null, 2));
            resolve(results);
          } else {
            console.log('Error:', data);
            reject(new Error(`API call failed: ${res.statusCode}`));
          }
        });
      });

      req.on('error', reject);
      req.end();
    });
  }

  // Konkrétní API metody
  async getControlPlansActive() {
    return this.callTRPC('controlPlans.active', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getInverterDetail() {
    return this.callTRPC('inverters.detail', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getLinkBoxConnectionState() {
    return this.callTRPC('linkBoxes.connectionState', [
      { json: { householdId: this.householdId } }
    ]);
  }

  async getCurrentCommands() {
    return this.callTRPC('commands.current', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getCurrentStep() {
    return this.callTRPC('inverters.currentStep', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getCurrentDistributionPrices() {
    return this.callTRPC('prices.currentDistributionPrices', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getWSToken() {
    return this.callTRPC('users.wsToken', [
      { json: {} }
    ]);
  }

  async getInverterExtendedDetail() {
    return this.callTRPC('inverters.extendedDetail', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getInverterLastState() {
    return this.callTRPC('inverters.lastState', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  async getFlexibilityRewardsSummary() {
    return this.callTRPC('inverters.flexibilityRewardsSummary', [
      { json: { inverterId: this.inverterId } }
    ]);
  }

  // Kombinované volání (jako v browseru)
  async getInverterPlanPage() {
    return this.callTRPC(
      ['linkBoxes.connectionState', 'inverters.detail', 'controlPlans.active'],
      [
        { json: { householdId: this.householdId } },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } }
      ]
    );
  }

  // Kompletní dashboard data (všechny endpointy najednou)
  async getDashboardData() {
    return this.callTRPC(
      [
        'linkBoxes.connectionState',
        'inverters.detail',
        'commands.current',
        'inverters.currentStep',
        'prices.currentDistributionPrices',
        'users.wsToken',
        'inverters.extendedDetail',
        'inverters.lastState',
        'inverters.flexibilityRewardsSummary'
      ],
      [
        { json: { householdId: this.householdId } },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } },
        { json: {} },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } },
        { json: { inverterId: this.inverterId } }
      ]
    );
  }

  // Uložení odpovědi do souboru
  saveToFile(filename, data) {
    fs.writeFileSync(filename, JSON.stringify(data, null, 2));
    console.log(`\n💾 Saved to ${filename}`);
  }
}

// Hlavní funkce
async function main() {
  const api = new ProteusAPI();

  try {
    // Přihlášení
    console.log('=== LOGGING IN ===\n');
    await api.login('your-email@example.com', 'your-password');

    console.log('\n=== FETCHING INDIVIDUAL ENDPOINTS ===\n');

    // Získej jednotlivé endpointy
    const controlPlans = await api.getControlPlansActive();
    api.saveToFile('controlPlans.json', controlPlans);

    const inverterDetail = await api.getInverterDetail();
    api.saveToFile('inverterDetail.json', inverterDetail);

    const linkBoxState = await api.getLinkBoxConnectionState();
    api.saveToFile('linkBoxState.json', linkBoxState);

    const currentCommands = await api.getCurrentCommands();
    api.saveToFile('currentCommands.json', currentCommands);

    const currentStep = await api.getCurrentStep();
    api.saveToFile('currentStep.json', currentStep);

    const distributionPrices = await api.getCurrentDistributionPrices();
    api.saveToFile('distributionPrices.json', distributionPrices);

    const wsToken = await api.getWSToken();
    api.saveToFile('wsToken.json', wsToken);

    const extendedDetail = await api.getInverterExtendedDetail();
    api.saveToFile('extendedDetail.json', extendedDetail);

    const lastState = await api.getInverterLastState();
    api.saveToFile('lastState.json', lastState);

    const rewardsSummary = await api.getFlexibilityRewardsSummary();
    api.saveToFile('rewardsSummary.json', rewardsSummary);

    console.log('\n=== FETCHING COMBINED DATA ===\n');

    // Kombinované volání - plan page
    const planPage = await api.getInverterPlanPage();
    api.saveToFile('inverterPlanPage.json', planPage);

    // Kombinované volání - dashboard (všechny endpointy najednou)
    const dashboard = await api.getDashboardData();
    api.saveToFile('dashboardData.json', dashboard);

    console.log('\n✅ All API calls completed successfully!');
    console.log('\n📁 Saved files:');
    console.log('   - controlPlans.json');
    console.log('   - inverterDetail.json');
    console.log('   - linkBoxState.json');
    console.log('   - currentCommands.json');
    console.log('   - currentStep.json');
    console.log('   - distributionPrices.json');
    console.log('   - wsToken.json');
    console.log('   - extendedDetail.json');
    console.log('   - lastState.json');
    console.log('   - rewardsSummary.json');
    console.log('   - inverterPlanPage.json');
    console.log('   - dashboardData.json');

  } catch (error) {
    console.error('❌ Error:', error.message);
    console.error(error.stack);
  }
}

main();
