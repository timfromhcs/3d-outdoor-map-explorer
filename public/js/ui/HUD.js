/**
 * HUD.js
 * Heads-Up Display, Telemetry, Controls, and Developer Inspection Mode.
 */
class HUD {
    constructor(engine, minimap) {
        this.engine = engine;
        this.minimap = minimap;

        // Elements
        this.crosshair = document.getElementById('crosshair');
        this.clickOverlay = document.getElementById('click-to-play-overlay');
        this.devPanel = document.getElementById('dev-panel');
        this.hudMapName = document.querySelector('.hud-map-name');
        this.btnMode = document.getElementById('btn-toggle-mode');
        this.btnDev = document.getElementById('btn-toggle-dev');
        this.btnMaps = document.getElementById('btn-open-maps');
        this.btnReset = document.getElementById('btn-reset-spawn');
        this.btnFullscreen = document.getElementById('btn-fullscreen');

        // Telemetry elements
        this.telemetryPos = document.getElementById('tel-pos');
        this.telemetrySpeed = document.getElementById('tel-speed');
        this.telemetryGround = document.getElementById('tel-ground');
        this.telemetryCompass = document.getElementById('tel-compass');
        this.telemetryFps = document.getElementById('tel-fps');

        // Stats elements in dev panel
        this.statTriangles = document.getElementById('stat-triangles');
        this.statVertices = document.getElementById('stat-vertices');
        this.statCalls = document.getElementById('stat-calls');

        this.fpsCount = 0;
        this.lastFpsTime = performance.now();
        this.currentFps = 60;

        this._setupListeners();
    }

    _setupListeners() {
        // Pointer Lock overlay click
        this.clickOverlay.addEventListener('click', () => {
            if (this.engine.currentMode === 'POV') {
                this.engine.player.controls.lock();
            }
        });

        this.engine.player.onLockChange = (isLocked) => {
            if (isLocked) {
                this.clickOverlay.style.display = 'none';
                this.crosshair.style.display = 'block';
            } else {
                if (this.engine.currentMode === 'POV') {
                    this.clickOverlay.style.display = 'flex';
                }
                this.crosshair.style.display = 'none';
            }
        };

        // Camera Mode button
        this.btnMode.addEventListener('click', () => {
            const nextMode = this.engine.currentMode === 'POV' ? 'ORBIT' : 'POV';
            this.engine.setMode(nextMode);
            this.btnMode.textContent = nextMode === 'POV' ? 'POV Mode' : 'Orbit Mode';
            this.clickOverlay.style.display = nextMode === 'POV' ? 'flex' : 'none';
            this.crosshair.style.display = nextMode === 'POV' && this.engine.player.isLocked ? 'block' : 'none';
        });

        // Developer panel toggle
        this.btnDev.addEventListener('click', () => this.toggleDevPanel());

        // Reset to spawn
        this.btnReset.addEventListener('click', () => this.engine.player.respawn());

        // Fullscreen
        this.btnFullscreen.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(() => {});
            } else {
                document.exitFullscreen();
            }
        });

        // Keyboard shortcuts
        window.addEventListener('keydown', (e) => {
            if (e.code === 'KeyV') {
                this.btnMode.click();
            } else if (e.code === 'KeyR') {
                this.engine.player.respawn();
            } else if (e.code === 'Tab') {
                e.preventDefault();
                this.toggleDevPanel();
            } else if (e.code === 'KeyM') {
                if (this.onOpenCatalog) this.onOpenCatalog();
            }
        });

        // Dev Panel layer toggles
        this._setupDevToggles();
    }

    _setupDevToggles() {
        const toggles = [
            { id: 'toggle-render', layer: 'render' },
            { id: 'toggle-collision', layer: 'collision' },
            { id: 'toggle-walkable', layer: 'walkable' },
            { id: 'toggle-segmentation', layer: 'segmentation' },
            { id: 'toggle-navgraph', layer: 'navGraph' },
            { id: 'toggle-bbox', layer: 'bbox' },
            { id: 'toggle-player-helper', layer: 'playerHelper' }
        ];

        toggles.forEach(t => {
            const el = document.getElementById(t.id);
            if (el) {
                el.addEventListener('change', (e) => {
                    this.engine.setLayerVisible(t.layer, e.target.checked);
                });
            }
        });

        const wireToggle = document.getElementById('toggle-wireframe');
        if (wireToggle) {
            wireToggle.addEventListener('change', (e) => {
                this.engine.applyWireframe(e.target.checked);
            });
        }
    }

    toggleDevPanel() {
        const isShown = this.devPanel.style.display === 'block';
        this.devPanel.style.display = isShown ? 'none' : 'block';
        this.btnDev.style.borderColor = isShown ? '#30363d' : '#58a6ff';
    }

    update(now) {
        // FPS calculation
        this.fpsCount++;
        if (now - this.lastFpsTime >= 1000) {
            this.currentFps = Math.round((this.fpsCount * 1000) / (now - this.lastFpsTime));
            this.telemetryFps.textContent = `${this.currentFps} FPS`;
            this.fpsCount = 0;
            this.lastFpsTime = now;
        }

        const player = this.engine.player;
        const pos = player.position;

        // Position
        this.telemetryPos.textContent = `${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)}`;

        // Grounded state
        this.telemetryGround.textContent = player.grounded ? "GROUNDED" : "AIRBORNE";
        this.telemetryGround.style.color = player.grounded ? "#2ea043" : "#f0883e";

        // Speed
        const horizontalSpeed = Math.sqrt(player.velocity.x ** 2 + player.velocity.z ** 2);
        this.telemetrySpeed.textContent = `${player.movementState} (${horizontalSpeed.toFixed(2)} m/s)`;

        // Compass heading
        const yawDeg = ((THREE.MathUtils.radToDeg(this.engine.camera.rotation.y) % 360) + 360) % 360;
        const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
        const dirIndex = Math.round(yawDeg / 45) % 8;
        this.telemetryCompass.textContent = `${directions[dirIndex]} (${Math.round(yawDeg)}°)`;

        // Update Minimap
        if (this.minimap) {
            this.minimap.update(pos, this.engine.camera.rotation.y);
        }

        // Update Dev stats
        if (this.devPanel.style.display === 'block') {
            this.statCalls.textContent = this.engine.renderer.info.render.calls;
            this.statTriangles.textContent = this.engine.renderer.info.render.triangles.toLocaleString();
            this.statVertices.textContent = this.engine.renderer.info.render.points.toLocaleString();
        }
    }
}

window.HUD = HUD;
