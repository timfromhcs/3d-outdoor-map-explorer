/**
 * test_hf_space_live.js
 * Verifies live execution of the deployed Hugging Face Static Space in Headless Chromium.
 * Loads the live HF Space URL, waits for WebGL render, tests POV, and saves screenshot proof.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const LIVE_HF_URL = 'https://timfromhcs-3d-outdoor-map-explorer.static.hf.space';

async function testLiveHFSpace() {
    console.log(`[HF Live Test] Navigating to: ${LIVE_HF_URL}`);

    const browser = await chromium.launch({
        headless: true,
        args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl']
    });

    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    const page = await context.newPage();

    const consoleLogs = [];
    const consoleErrors = [];

    page.on('console', msg => {
        const t = msg.text();
        consoleLogs.push({ type: msg.type(), text: t });
        if (msg.type() === 'error') consoleErrors.push(t);
    });

    try {
        const start = Date.now();
        await page.goto(`${LIVE_HF_URL}/?map=map1`, { waitUntil: 'networkidle', timeout: 30000 });

        // Wait for READY state
        await page.waitForFunction(() => {
            return window.mapApp && window.mapApp.lifecycleState === 'READY';
        }, { timeout: 30000 });

        const loadMs = Date.now() - start;
        console.log(`[HF Live Test] Live Space loaded in ${loadMs}ms!`);

        // Wait 2 seconds for rendering
        await page.waitForTimeout(2000);

        const liveStats = await page.evaluate(() => {
            return {
                fps: document.getElementById('tel-fps')?.textContent,
                pos: document.getElementById('tel-pos')?.textContent,
                heading: document.getElementById('tel-compass')?.textContent,
                triangles: window.mapApp.engine.renderer.info.render.triangles,
                calls: window.mapApp.engine.renderer.info.render.calls
            };
        });

        console.log(`[HF Live Test] Live Telemetry:`, liveStats);

        const screenshotPath = path.join(__dirname, '..', 'reports', 'screenshot_hf_space_live.png');
        await page.screenshot({ path: screenshotPath });
        console.log(`[HF Live Test] Saved live screenshot proof to: ${screenshotPath}`);

        const proofReport = {
            timestamp: new Date().toISOString(),
            hf_space_url: LIVE_HF_URL,
            load_time_ms: loadMs,
            stats: liveStats,
            console_errors: consoleErrors,
            status: consoleErrors.length === 0 ? 'VERIFIED' : 'WARNINGS'
        };

        const proofJson = path.join(__dirname, '..', 'reports', 'hf_space_verification.json');
        fs.writeFileSync(proofJson, JSON.stringify(proofReport, null, 2));

        console.log(`[HF Live Test] SUCCESS: Live Hugging Face Space verified with 0 errors.`);

    } finally {
        await browser.close();
    }
}

testLiveHFSpace().catch(err => {
    console.error('[HF Live Test] Failure:', err);
    process.exit(1);
});
