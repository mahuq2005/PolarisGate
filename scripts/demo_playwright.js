// PolarisGate Demo Video — Playwright Automation
// Captures real browser screenshots showing prompts, safety badges, and dashboard
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const DEMO_DIR = path.join(__dirname, '..', 'demo');
const FRAMES = path.join(DEMO_DIR, 'frames');
fs.mkdirSync(FRAMES, { recursive: true });

const CHAT_URL = 'http://localhost:3001/chat.html';
const ADMIN_URL = 'http://localhost:3001/';
const EMAIL = 'admin@polarisgate.ai';
const PASS = 'PolarisGate2024!';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  
  // ── Chat Portal ──────────────────────────────────────────
  console.log('1. Chat Portal login...');
  const chatPage = await browser.newPage();
  await chatPage.setViewportSize({ width: 1440, height: 860 });
  await chatPage.goto(CHAT_URL, { waitUntil: 'networkidle' });
  await sleep(1000);
  
  // Login
  await chatPage.fill('#login-email', EMAIL);
  await chatPage.fill('#login-password', PASS);
  await chatPage.click('button:has-text("Login")');
  await sleep(2000);

  // Select Ollama from dropdown
  try {
    await chatPage.click('.custom-select-trigger');
    await sleep(500);
    await chatPage.click('.custom-option:has-text("Ollama")');
    await sleep(500);
  } catch(e) {}

  console.log('   Sending demo prompts...');

  // Prompt 1: Safe
  await chatPage.fill('#chat-input', "Write a summary of today's marketing meeting");
  await chatPage.click('#send-btn');
  await sleep(8000);
  await chatPage.screenshot({ path: path.join(FRAMES, '01_safe_prompt.png') });
  console.log('   Safe prompt captured');

  // Prompt 2: PII
  await chatPage.fill('#chat-input', 'My email is john@example.com and call me at 416-555-1234');
  await chatPage.click('#send-btn');
  await sleep(8000);
  await chatPage.screenshot({ path: path.join(FRAMES, '02_pii_flagged.png') });
  console.log('   PII prompt captured');

  // Prompt 3: Toxicity
  await chatPage.fill('#chat-input', 'I hate you, you stupid idiot!');
  await chatPage.click('#send-btn');
  await sleep(8000);
  await chatPage.screenshot({ path: path.join(FRAMES, '03_toxic_flagged.png') });
  console.log('   Toxic prompt captured');

  await chatPage.close();

  // ── Admin Portal ──────────────────────────────────────────
  console.log('2. Admin Portal...');
  const adminPage = await browser.newPage();
  await adminPage.setViewportSize({ width: 1440, height: 860 });
  await adminPage.goto(ADMIN_URL, { waitUntil: 'networkidle' });
  await sleep(2000);

  await adminPage.fill('#login-email', EMAIL);
  await adminPage.fill('#login-password', PASS);
  await adminPage.click('button:has-text("Login")');
  await sleep(3000);
  await adminPage.screenshot({ path: path.join(FRAMES, '04_dashboard.png') });
  console.log('   Dashboard captured');

  // Click Incidents tab
  try {
    await adminPage.click('.sidebar-btn:has-text("Incidents")');
    await sleep(2000);
    await adminPage.screenshot({ path: path.join(FRAMES, '05_incidents.png') });
    console.log('   Incidents captured');

    // Click first incident
    await adminPage.click('.incident-row:first-child');
    await sleep(1000);
    await adminPage.screenshot({ path: path.join(FRAMES, '06_drilldown.png') });
    console.log('   Drill-down captured');
  } catch(e) {
    console.log('   Incident drill skipped');
  }

  // Settings → LLM Providers
  try {
    await adminPage.click('.tab:has-text("Settings")');
    await sleep(500);
    await adminPage.click('.sidebar-btn:has-text("LLM Providers")');
    await sleep(2000);
    await adminPage.screenshot({ path: path.join(FRAMES, '07_providers.png') });
    console.log('   Providers captured');
  } catch(e) {
    console.log('   Providers skipped');
  }

  await adminPage.close();
  await browser.close();

  console.log('\nAll screenshots captured!');
  console.log(`Frames: ${fs.readdirSync(FRAMES).length} files in ${FRAMES}`);
})();