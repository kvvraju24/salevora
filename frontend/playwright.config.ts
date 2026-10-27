import { defineConfig } from '@playwright/test';
// E2E_BASE_URL lets CI test the single-process production build (uvicorn on :8000).
export default defineConfig({testDir:'./e2e',timeout:45000,use:{baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:5173',viewport:{width:1440,height:1060},headless:true,launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}},reporter:'list'});
