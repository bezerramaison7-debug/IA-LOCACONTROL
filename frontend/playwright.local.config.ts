import { defineConfig } from '@playwright/test'

// Local edition (ADR-023): a second server with LOCACONTROL_LOCAL_MODE=true, started by
// scripts/e2e-auth.py after the login-based suite.
if (!process.env.E2E_LOCAL_BASE_URL)
  throw new Error('Execute pela raiz: .venv/Scripts/python.exe scripts/e2e-auth.py')
export default defineConfig({
  testDir: './e2e',
  testMatch: 'local.spec.ts',
  timeout: 120_000,
  workers: 1,
  maxFailures: 1,
  // Inside the ignored folders of the login-based suite.
  outputDir: 'auth-test-results/local',
  reporter: [['list'], ['html', { outputFolder: 'auth-playwright-report/local', open: 'never' }]],
  use: {
    actionTimeout: 15_000,
    baseURL: process.env.E2E_LOCAL_BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined },
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1366, height: 768 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
})
