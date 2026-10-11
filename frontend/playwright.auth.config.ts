import { defineConfig } from '@playwright/test'

if (!process.env.E2E_AUTH_BASE_URL)
  throw new Error('Execute pela raiz: .venv/Scripts/python.exe scripts/e2e-auth.py')
export default defineConfig({
  testDir: './e2e',
  testMatch: /(?:auth|masters|imports|quotes|contracts|reports|portal|fiscal|backups)\.spec\.ts/,
  timeout: 120_000,
  workers: 1,
  maxFailures: 1,
  outputDir: 'auth-test-results',
  reporter: [['list'], ['html', { outputFolder: 'auth-playwright-report', open: 'never' }]],
  use: {
    actionTimeout: 15_000,
    baseURL: process.env.E2E_AUTH_BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined },
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1366, height: 768 } } },
    { name: 'full-hd', use: { viewport: { width: 1920, height: 1080 } } },
    { name: 'tablet', use: { viewport: { width: 820, height: 1180 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
})
