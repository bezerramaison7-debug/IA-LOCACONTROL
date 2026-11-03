import { defineConfig } from '@playwright/test'

// Network edition (ADR-025): a third server listening on the network, started by
// scripts/e2e-auth.py; the station browser reaches it by this computer's network address.
if (!process.env.E2E_NETWORK_BASE_URL || !process.env.E2E_STATION_BASE_URL)
  throw new Error('Execute pela raiz: .venv/Scripts/python.exe scripts/e2e-auth.py')
export default defineConfig({
  testDir: './e2e',
  testMatch: 'network.spec.ts',
  timeout: 120_000,
  workers: 1,
  maxFailures: 1,
  outputDir: 'auth-test-results/network',
  reporter: [['list'], ['html', { outputFolder: 'auth-playwright-report/network', open: 'never' }]],
  use: {
    actionTimeout: 15_000,
    baseURL: process.env.E2E_NETWORK_BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
      // The station talks to the main computer directly, never through a proxy.
      args: ['--no-proxy-server'],
    },
  },
  projects: [{ name: 'desktop', use: { viewport: { width: 1366, height: 768 } } }],
})
