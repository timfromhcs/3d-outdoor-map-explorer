/**
 * app.js
 * Main Application Orchestrator for 3D Outdoor Map Explorer & POV Walker.
 * Manages runtime lifecycle, dynamic map loading, and UI events.
 */
class MapExplorerApp {
    constructor() {
        this.lifecycleState = "IDLE"; // IDLE, DISCOVERING, LOADING, PARSING, BUILDING_RUNTIME_DATA, READY, ERROR
        this.catalog = null;
        this.currentMapId = null;

        this.container = document.getElementById('canvas-container');
        this.loadingScreen = document.getElementById('loading-screen');
        this.loadingMsg = document.getElementById('loading-msg');

        this.engine = new WorldEngine(this.container);
        this.minimap = new Minimap('minimap-canvas');
        this.hud = new HUD(this.engine, this.minimap);
        this.catalogUI = new CatalogUI((mapId) => this.switchMap(mapId));

        this.hud.onOpenCatalog = () => {
            this.catalogUI.render(this.catalog, this.currentMapId);
            this.catalogUI.show();
        };

        const btnMaps = document.getElementById('btn-open-maps');
        if (btnMaps) {
            btnMaps.addEventListener('click', () => {
                this.catalogUI.render(this.catalog, this.currentMapId);
                this.catalogUI.show();
            });
        }
    }

    setLoading(visible, message = "Loading...") {
        this.loadingMsg.textContent = message;
        if (visible) {
            this.loadingScreen.style.opacity = '1';
            this.loadingScreen.style.display = 'flex';
        } else {
            this.loadingScreen.style.opacity = '0';
            setTimeout(() => { this.loadingScreen.style.display = 'none'; }, 250);
        }
    }

    async init() {
        this.lifecycleState = "DISCOVERING";
        this.setLoading(true, "Discovering 3D Outdoor Maps catalog...");

        try {
            // Load map catalog dynamically
            const res = await fetch('/output/catalog.json');
            if (!res.ok) throw new Error(`Could not load catalog.json: ${res.statusText}`);
            this.catalog = await res.json();

            if (!this.catalog.maps || this.catalog.maps.length === 0) {
                throw new Error("Catalog contains 0 maps.");
            }

            // Determine initial map from URL or default to first
            const params = new URLSearchParams(window.location.search);
            const initialMapId = params.get('map') || this.catalog.maps[0].id;

            await this.switchMap(initialMapId);

            // Start animation loop
            this.animate();
        } catch (err) {
            this.lifecycleState = "ERROR";
            this.setLoading(true, `Error: ${err.message}`);
            console.error("MapExplorerApp Initialization error:", err);
        }
    }

    async switchMap(mapId) {
        const manifestEntry = this.catalog.maps.find(m => m.id === mapId);
        if (!manifestEntry) {
            console.error(`Map '${mapId}' not found in catalog.`);
            return;
        }

        this.currentMapId = mapId;
        this.lifecycleState = "LOADING";
        this.setLoading(true, `Loading 3D Map: ${manifestEntry.name || mapId}...`);

        try {
            // Fetch detailed map manifest
            const mRes = await fetch(`/output/${mapId}/manifest.json`);
            const manifest = mRes.ok ? await mRes.json() : manifestEntry;

            this.lifecycleState = "PARSING";
            this.setLoading(true, `Parsing 3D geometry & textures...`);

            this.lifecycleState = "BUILDING_RUNTIME_DATA";
            await this.engine.loadMap(manifest);

            // Update Minimap with walkable ground points
            this.minimap.setMapData(manifest, this.engine.layers.walkable);

            // Update HUD Title
            if (this.hud.hudMapName) {
                this.hud.hudMapName.textContent = manifest.name || mapId;
            }

            // Update browser URL without reloading
            const url = new URL(window.location);
            url.searchParams.set('map', mapId);
            window.history.replaceState({}, '', url);

            this.lifecycleState = "READY";
            this.setLoading(false);
            console.log(`[MapExplorerApp] Successfully loaded map: ${mapId} (READY)`);
        } catch (err) {
            this.lifecycleState = "ERROR";
            this.setLoading(true, `Failed to load map '${mapId}': ${err.message}`);
            console.error("switchMap error:", err);
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        const now = performance.now();
        this.engine.update();
        this.hud.update(now);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    window.mapApp = new MapExplorerApp();
    window.mapApp.init();
});
