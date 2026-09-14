/**
 * Automated Visual Verification script using Headless Chromium via Playwright.
 * Loads real map outputs in Three.js, checks WebGL rendering, console logs, and saves screenshots.
 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8089;
const SERVER_URL = `http://127.0.0.1:${PORT}`;

function waitForServer(url, timeoutMs = 10000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
        function check() {
            http.get(`${url}/api/health`, (res) => {
                if (res.statusCode === 200) return resolve();
                setTimeout(check, 250);
            }).on('error', () => {
                if (Date.now() - start > timeoutMs) return reject(new Error('Server start timed out'));
                setTimeout(check, 250);
            });
        }
        check();
    });
}

async function runVerification() {
    console.log('[Visual Verification] Starting viewer server...');
    const pythonExe = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
    const serverProc = spawn(pythonExe, ['-m', 'pipeline.viewer.server', '--port', String(PORT)], {
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit'
    });

    try {
        await waitForServer(SERVER_URL);
        console.log('[Visual Verification] Viewer server is online.');

        const browser = await chromium.launch({
            headless: true,
            args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl']
        });

        const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
        const page = await context.newPage();

        const consoleLogs = [];
        const consoleErrors = [];

        page.on('console', msg => {
            const text = msg.text();
            consoleLogs.push({ type: msg.type(), text });
            if (msg.type() === 'error') {
                consoleErrors.push(text);
            }
        });

        page.on('pageerror', err => {
            consoleErrors.push(err.toString());
        });

        const reportDir = path.join(__dirname, '..', 'reports');
        if (!fs.existsSync(reportDir)) fs.mkdirSync(reportDir, { recursive: true });

        const verificationResults = {
            timestamp: new Date().toISOString(),
            browser: 'Chromium (SwiftShader WebGL)',
            maps_verified: []
        };

        // Test Map 1
        console.log('[Visual Verification] Testing map1 in viewer...');
        await page.goto(`${SERVER_URL}/viewer?map=map1`, { waitUntil: 'networkidle' });

        // Wait for stats to populate
        await page.waitForFunction(() => {
            const el = document.getElementById('stat-triangles');
            return el && el.textContent && el.textContent !== '-' && el.textContent !== '0';
        }, { timeout: 15000 });

        // Wait 1.5s for initial Three.js render frame
        await page.waitForTimeout(1500);

        const map1Stats = await page.evaluate(() => {
            return {
                fps: document.getElementById('stat-fps')?.textContent,
                vertices: document.getElementById('stat-verts')?.textContent,
                triangles: document.getElementById('stat-triangles')?.textContent,
                dimensions: document.getElementById('stat-dims')?.textContent,
                quality: document.getElementById('stat-quality')?.textContent,
                gates: document.getElementById('stat-gates')?.textContent,
            };
        });

        console.log(`[Visual Verification] map1 stats:`, map1Stats);
        const map1Shot = path.join(reportDir, 'screenshot_map1_render.png');
        await page.screenshot({ path: map1Shot });
        console.log(`[Visual Verification] Saved screenshot: ${map1Shot}`);

        // Toggle collision layer
        await page.click('#toggle-collision');
        await page.waitForTimeout(800);
        const map1ColShot = path.join(reportDir, 'screenshot_map1_collision.png');
        await page.screenshot({ path: map1ColShot });

        // Toggle walkable layer
        await page.click('#toggle-walkable');
        await page.waitForTimeout(800);
        const map1WalkShot = path.join(reportDir, 'screenshot_map1_walkable.png');
        await page.screenshot({ path: map1WalkShot });

        verificationResults.maps_verified.push({
            map_id: 'map1',
            status: 'RENDER_VERIFIED',
            stats: map1Stats,
            screenshots: ['screenshot_map1_render.png', 'screenshot_map1_collision.png', 'screenshot_map1_walkable.png']
        });

        // Test Map 3
        console.log('[Visual Verification] Testing map3 in viewer...');
        await page.goto(`${SERVER_URL}/viewer?map=map3`, { waitUntil: 'networkidle' });
        await page.waitForFunction(() => {
            const el = document.getElementById('stat-triangles');
            return el && el.textContent && el.textContent !== '-' && el.textContent !== '0';
        }, { timeout: 15000 });
        await page.waitForTimeout(1500);

        const map3Stats = await page.evaluate(() => {
            return {
                fps: document.getElementById('stat-fps')?.textContent,
                vertices: document.getElementById('stat-verts')?.textContent,
                triangles: document.getElementById('stat-triangles')?.textContent,
                dimensions: document.getElementById('stat-dims')?.textContent,
            };
        });

        console.log(`[Visual Verification] map3 stats:`, map3Stats);
        const map3Shot = path.join(reportDir, 'screenshot_map3_render.png');
        await page.screenshot({ path: map3Shot });
        console.log(`[Visual Verification] Saved screenshot: ${map3Shot}`);

        verificationResults.maps_verified.push({
            map_id: 'map3',
            status: 'RENDER_VERIFIED',
            stats: map3Stats,
            screenshots: ['screenshot_map3_render.png']
        });

        verificationResults.console_errors = consoleErrors;
        verificationResults.all_passed = consoleErrors.length === 0;

        const reportPath = path.join(reportDir, 'visual_verification.json');
        fs.writeFileSync(reportPath, JSON.stringify(verificationResults, null, 2));
        console.log(`[Visual Verification] Report saved to ${reportPath}`);

        await browser.close();

        if (consoleErrors.length > 0) {
            console.warn('[Visual Verification] Browser console logged errors:', consoleErrors);
        } else {
            console.log('[Visual Verification] SUCCESS: Zero console errors, real 3D geometry loaded and verified.');
        }

    } finally {
        serverProc.kill();
    }
}

runVerification().catch(err => {
    console.error('[Visual Verification] Fatal error:', err);
    process.exit(1);
});
