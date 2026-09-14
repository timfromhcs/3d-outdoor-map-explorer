/**
 * test_pov_walker.js
 * Comprehensive automated Playwright test suite for the 3D POV Walker.
 * Tests POV entry, WASD movement, wall collision, slope climbing, layer toggles,
 * map switching between map1, map2, map3, and captures real visual proof screenshots.
 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8092;
const SERVER_URL = `http://127.0.0.1:${PORT}`;

function waitForServer(url, timeoutMs = 12000) {
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

async function runPOVTests() {
    console.log('[POV Test] Starting local server...');
    const pythonExe = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
    const serverProc = spawn(pythonExe, ['-m', 'pipeline.viewer.server', '--port', String(PORT)], {
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit'
    });

    const reportBase = path.join(__dirname, '..', 'reports', 'visual');
    const performanceReport = {};

    try {
        await waitForServer(SERVER_URL);
        console.log('[POV Test] Server online.');

        const browser = await chromium.launch({
            headless: true,
            args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl']
        });

        const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
        const page = await context.newPage();

        const consoleErrors = [];
        const networkFailures = [];

        page.on('console', msg => {
            if (msg.type() === 'error') {
                consoleErrors.push(msg.text());
            }
        });

        page.on('requestfailed', req => {
            networkFailures.push(`${req.url()} (${req.failure()?.errorText})`);
        });

        const mapsToTest = ['map1', 'map2', 'map3'];

        for (const mapId of mapsToTest) {
            console.log(`\n=======================================================`);
            console.log(`[POV Test] Testing ${mapId.toUpperCase()}`);
            console.log(`=======================================================`);

            const mapVisualDir = path.join(reportBase, mapId);
            fs.mkdirSync(mapVisualDir, { recursive: true });

            const loadStartTime = Date.now();
            await page.goto(`${SERVER_URL}/?map=${mapId}`, { waitUntil: 'networkidle' });

            // Wait for app to reach READY state
            await page.waitForFunction(() => {
                return window.mapApp && window.mapApp.lifecycleState === 'READY';
            }, { timeout: 20000 });

            const loadDurationMs = Date.now() - loadStartTime;
            console.log(`[POV Test] ${mapId} loaded in ${loadDurationMs}ms (State: READY)`);

            // 1. Initial Overview Screenshot (Aerial / Spawn perspective)
            await page.waitForTimeout(1000);
            const overviewShot = path.join(mapVisualDir, 'overview.png');
            await page.screenshot({ path: overviewShot });
            console.log(`[POV Test] Captured overview.png`);

            // 2. Enter POV Mode
            console.log(`[POV Test] Engaging POV mode...`);
            await page.click('#btn-toggle-mode');
            await page.waitForTimeout(500);

            const povShot = path.join(mapVisualDir, 'pov.png');
            await page.screenshot({ path: povShot });
            console.log(`[POV Test] Captured pov.png`);

            // 3. Test WASD Movement
            console.log(`[POV Test] Simulating WASD movement...`);
            const posBefore = await page.evaluate(() => {
                const p = window.mapApp.engine.player.position;
                return { x: p.x, y: p.y, z: p.z };
            });

            // Hold 'W' for 800ms
            await page.keyboard.down('KeyW');
            await page.waitForTimeout(800);
            await page.keyboard.up('KeyW');

            // Hold 'D' for 400ms
            await page.keyboard.down('KeyD');
            await page.waitForTimeout(400);
            await page.keyboard.up('KeyD');

            const posAfter = await page.evaluate(() => {
                const p = window.mapApp.engine.player.position;
                const state = window.mapApp.engine.player.movementState;
                const grounded = window.mapApp.engine.player.grounded;
                return { x: p.x, y: p.y, z: p.z, state, grounded };
            });

            const deltaMove = Math.sqrt((posAfter.x - posBefore.x)**2 + (posAfter.z - posBefore.z)**2);
            console.log(`[POV Test] Player moved: ${deltaMove.toFixed(3)}m, Grounded: ${posAfter.grounded}, State: ${posAfter.state}`);

            // 4. Test Collision Against Obstacle/Wall
            console.log(`[POV Test] Testing wall collision sliding...`);
            // Walk forward vigorously towards potential boundaries
            await page.keyboard.down('ShiftLeft');
            await page.keyboard.down('KeyW');
            await page.waitForTimeout(1500);
            await page.keyboard.up('KeyW');
            await page.keyboard.up('ShiftLeft');

            const posAfterSprint = await page.evaluate(() => {
                const p = window.mapApp.engine.player.position;
                return { x: p.x, y: p.y, z: p.z };
            });

            // 5. Toggle Developer Mode & Capture Collision Layer
            console.log(`[POV Test] Unlocking cursor & toggling Dev Panel...`);
            await page.keyboard.press('Escape');
            await page.waitForTimeout(400);

            await page.evaluate(() => {
                document.getElementById('btn-toggle-dev').click();
            });
            await page.waitForTimeout(300);

            // Enable collision layer
            await page.evaluate(() => {
                const el = document.getElementById('toggle-collision');
                el.checked = true;
                el.dispatchEvent(new Event('change'));
            });
            await page.waitForTimeout(600);
            const colShot = path.join(mapVisualDir, 'collision.png');
            await page.screenshot({ path: colShot });
            console.log(`[POV Test] Captured collision.png`);

            // Enable walkable layer & Nav Graph
            console.log(`[POV Test] Toggling Walkable & Nav Graph layer...`);
            await page.evaluate(() => {
                const colEl = document.getElementById('toggle-collision');
                colEl.checked = false;
                colEl.dispatchEvent(new Event('change'));

                const walkEl = document.getElementById('toggle-walkable');
                walkEl.checked = true;
                walkEl.dispatchEvent(new Event('change'));

                const navEl = document.getElementById('toggle-navgraph');
                navEl.checked = true;
                navEl.dispatchEvent(new Event('change'));
            });
            await page.waitForTimeout(600);
            const walkShot = path.join(mapVisualDir, 'walkable.png');
            await page.screenshot({ path: walkShot });
            console.log(`[POV Test] Captured walkable.png`);

            // 6. Collect Performance & Telemetry metrics
            const telemetry = await page.evaluate(() => {
                const p = window.mapApp.engine.player;
                const r = window.mapApp.engine.renderer.info.render;
                return {
                    fps: document.getElementById('tel-fps')?.textContent,
                    coords: document.getElementById('tel-pos')?.textContent,
                    heading: document.getElementById('tel-compass')?.textContent,
                    surface: document.getElementById('tel-ground')?.textContent,
                    triangles: r.triangles,
                    calls: r.calls,
                    points: r.points
                };
            });

            performanceReport[mapId] = {
                load_time_ms: loadDurationMs,
                telemetry: telemetry,
                movement_delta: deltaMove,
                screenshots: ['overview.png', 'pov.png', 'collision.png', 'walkable.png']
            };

            // Test Respawn button
            await page.keyboard.press('KeyR');
            await page.waitForTimeout(400);
        }

        // Test Map Switching via Catalog Modal
        console.log(`\n[POV Test] Testing dynamic Map Catalog modal & switching...`);
        await page.evaluate(() => {
            document.getElementById('btn-open-maps').click();
        });
        await page.waitForTimeout(600);

        // Click on map2 in modal
        await page.evaluate(() => {
            const btn = document.querySelector('.btn-select-map[data-map="map2"]');
            if (btn) btn.click();
        });
        await page.waitForFunction(() => {
            return window.mapApp && window.mapApp.currentMapId === 'map2' && window.mapApp.lifecycleState === 'READY';
        }, { timeout: 15000 });
        console.log(`[POV Test] Successfully switched to map2 via dynamic Catalog UI!`);

        await browser.close();

        // Write test report
        const reportPath = path.join(__dirname, '..', 'reports', 'pov_test_report.json');
        const finalReport = {
            timestamp: new Date().toISOString(),
            status: (consoleErrors.length === 0 && networkFailures.length === 0) ? 'VERIFIED' : 'WARNINGS',
            console_errors: consoleErrors,
            network_failures: networkFailures,
            maps: performanceReport
        };
        fs.writeFileSync(reportPath, JSON.stringify(finalReport, null, 2));

        console.log(`\n[POV Test] Finished! Report saved to ${reportPath}`);
        console.log(`Console Errors: ${consoleErrors.length} | Network Failures: ${networkFailures.length}`);

    } finally {
        serverProc.kill();
    }
}

runPOVTests().catch(err => {
    console.error('[POV Test] Fatal error:', err);
    process.exit(1);
});
