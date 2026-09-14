/**
 * WorldEngine.js
 * Core Three.js runtime engine coordinating render layers, dual-camera system
 * (POV / Orbit), asset loading, and animation loop.
 */
class WorldEngine {
    constructor(container) {
        this.container = container;
        this.scene = new THREE.Scene();
        // Atmospheric daylight sky and subtle haze
        this.scene.background = new THREE.Color(0x8cb8e6);
        this.scene.fog = new THREE.FogExp2(0xa5cbf0, 0.008);

        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.05, 2000);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 0.95;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        this.collisionSystem = new CollisionSystem();
        this.player = new PlayerController(this.camera, this.renderer.domElement, this.collisionSystem);

        this.orbitControls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.orbitControls.enableDamping = true;
        this.orbitControls.dampingFactor = 0.08;
        this.orbitControls.maxPolarAngle = Math.PI / 2 + 0.05; // Prevent camera going below ground
        this.orbitControls.enabled = true; // Starts in Orbit Overview mode

        this.currentMode = "ORBIT"; // "ORBIT" or "POV"
        this.currentMapManifest = null;

        // Visual Layers
        this.layers = {
            render: null,
            collision: null,
            walkable: null,
            segmentation: null,
            navGraph: null,
            bbox: null,
            grid: null,
            playerHelper: null
        };

        this.layerVisibility = {
            render: true,
            collision: false,
            walkable: false,
            segmentation: false,
            navGraph: false,
            wireframe: false,
            bbox: false,
            playerHelper: false
        };

        this.clock = new THREE.Clock();
        this.loader = new THREE.GLTFLoader();

        this._setupLighting();
        this._setupGroundGrid();
        this._setupPlayerHelper();
        window.addEventListener('resize', () => this.onResize());
    }

    _setupLighting() {
        // Multi-angle realistic outdoor daylight lighting calibrated for vertex colors
        const ambient = new THREE.AmbientLight(0xffffff, 0.35);
        this.scene.add(ambient);

        // Sky & ground hemisphere bounce
        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x556677, 0.45);
        hemiLight.position.set(0, 50, 0);
        this.scene.add(hemiLight);

        // Primary warm sun
        const sun = new THREE.DirectionalLight(0xfff5e6, 0.75);
        sun.position.set(25, 45, 30);
        sun.castShadow = true;
        this.scene.add(sun);

        // Secondary fill / ground bounce light
        const backSun = new THREE.DirectionalLight(0xddeeff, 0.25);
        backSun.position.set(-25, 20, -25);
        this.scene.add(backSun);
    }

    _setupGroundGrid() {
        const grid = new THREE.GridHelper(80, 40, 0x5588bb, 0x99bbee);
        grid.position.y = -0.01;
        this.layers.grid = grid;
        this.scene.add(grid);
    }

    _setupPlayerHelper() {
        const geom = new THREE.CylinderGeometry(0.35, 0.35, 1.7, 12);
        const mat = new THREE.MeshStandardMaterial({ color: 0x00e5ff, wireframe: true });
        this.layers.playerHelper = new THREE.Mesh(geom, mat);
        this.layers.playerHelper.visible = false;
        this.scene.add(this.layers.playerHelper);
    }

    onResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    /**
     * Toggles between First Person POV mode and Aerial Orbit mode.
     */
    setMode(mode) {
        this.currentMode = mode;
        if (mode === "POV") {
            this.orbitControls.enabled = false;
            this.player.respawn("POV");
            this.player.controls.lock();
            this.layers.playerHelper.visible = false;
        } else {
            this.player.controls.unlock();
            this.orbitControls.enabled = true;
            if (this.layers.render) {
                const box = new THREE.Box3().setFromObject(this.layers.render);
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.z, 15);

                this.orbitControls.target.copy(center);
                this.camera.position.set(
                    center.x + maxDim * 0.85,
                    center.y + maxDim * 0.75,
                    center.z + maxDim * 0.85
                );
            } else {
                this.orbitControls.target.copy(this.player.position);
                this.camera.position.set(
                    this.player.position.x + 10,
                    this.player.position.y + 8,
                    this.player.position.z + 10
                );
            }
            this.orbitControls.update();
            this.layers.playerHelper.visible = this.layerVisibility.playerHelper;
        }
    }

    /**
     * Clears all layers of the currently loaded map.
     */
    clearMap() {
        ['render', 'collision', 'walkable', 'segmentation', 'navGraph', 'bbox'].forEach(k => {
            if (this.layers[k]) {
                this.scene.remove(this.layers[k]);
                this.layers[k] = null;
            }
        });
    }

    /**
     * Loads a map dynamically from its manifest.
     */
    async loadMap(manifest) {
        this.currentMapManifest = manifest;
        this.clearMap();

        const basePath = `/output/${manifest.id}`;

        // Helper to load GLB safely
        const loadGLB = (relPath) => {
            return new Promise((resolve) => {
                if (!relPath) return resolve(null);
                const url = `${basePath}/${relPath}`;
                this.loader.load(
                    url,
                    (gltf) => resolve(gltf.scene),
                    undefined,
                    (err) => {
                        console.warn(`Asset not available: ${url}`);
                        resolve(null);
                    }
                );
            });
        };

        // Load visual and physical layers concurrently
        const [renderScene, colScene, walkScene, segScene] = await Promise.all([
            loadGLB(manifest.assets.render ? manifest.assets.render.path : null),
            loadGLB(manifest.assets.collision ? manifest.assets.collision.path : null),
            loadGLB(manifest.assets.walkable ? manifest.assets.walkable.path : null),
            loadGLB(manifest.assets.segmentation ? manifest.assets.segmentation.path : null)
        ]);

        if (renderScene) {
            this.layers.render = renderScene;
            this.layers.render.visible = this.layerVisibility.render;
            this.scene.add(renderScene);
        }

        if (colScene) {
            this.layers.collision = colScene;
            this.layers.collision.visible = this.layerVisibility.collision;
            this.scene.add(colScene);
        }

        if (walkScene) {
            this.layers.walkable = walkScene;
            this.layers.walkable.visible = this.layerVisibility.walkable;
            this.scene.add(walkScene);
        }

        if (segScene) {
            this.layers.segmentation = segScene;
            this.layers.segmentation.visible = this.layerVisibility.segmentation;
            this.scene.add(segScene);
        }

        // Configure high visual fidelity, double-sided rendering & smooth normals
        [renderScene, colScene, walkScene, segScene].forEach(scene => {
            if (!scene) return;
            scene.traverse(child => {
                if (child.isMesh) {
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(m => {
                                m.side = THREE.DoubleSide;
                                m.roughness = 0.65;
                                m.metalness = 0.05;
                                m.needsUpdate = true;
                            });
                        } else {
                            child.material.side = THREE.DoubleSide;
                            child.material.roughness = 0.65;
                            child.material.metalness = 0.05;
                            child.material.needsUpdate = true;
                        }
                    }
                    if (child.geometry && !child.geometry.attributes.normal) {
                        child.geometry.computeVertexNormals();
                    }
                }
            });
        });

        // Bounding Box Helper
        const mainMesh = renderScene || colScene || walkScene;
        if (mainMesh) {
            const box = new THREE.Box3().setFromObject(mainMesh);
            this.layers.bbox = new THREE.Box3Helper(box, 0x58a6ff);
            this.layers.bbox.visible = this.layerVisibility.bbox;
            this.scene.add(this.layers.bbox);

            // Auto-frame Orbit camera to center of map
            if (this.currentMode === 'ORBIT') {
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.z, 15);

                this.orbitControls.target.copy(center);
                this.camera.position.set(
                    center.x + maxDim * 0.85,
                    center.y + maxDim * 0.75,
                    center.z + maxDim * 0.85
                );
                this.orbitControls.update();
            }
        }

        // Load Nav Graph if available
        if (manifest.assets.nav_graph) {
            this._loadNavGraph(`${basePath}/${manifest.assets.nav_graph.path}`);
        }

        // Extract primary mesh for collision detection
        const colMesh = this._extractMainTrimesh(this.layers.collision || this.layers.walkable || this.layers.render);
        const walkMesh = this._extractMainTrimesh(this.layers.walkable);
        this.collisionSystem.setCollisionMesh(colMesh, walkMesh, manifest.bounds);

        // Position player at safe spawn point
        const spawn = (manifest.spawn_points && manifest.spawn_points.length > 0)
            ? manifest.spawn_points[0]
            : { position: [0, 1.7, 0], lookYaw: 0 };

        this.player.setSpawn(spawn, manifest.bounds.extents, this.currentMode);
        this.applyWireframe(this.layerVisibility.wireframe);

        return true;
    }

    _extractMainTrimesh(sceneGroup) {
        if (!sceneGroup) return null;
        let found = null;
        sceneGroup.traverse((child) => {
            if (child.isMesh && child.geometry && !found) {
                found = child;
            }
        });
        return found;
    }

    async _loadNavGraph(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();
            const graphGroup = new THREE.Group();

            // Render nodes
            const nodeGeom = new THREE.SphereGeometry(0.008, 6, 6);
            const nodeMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff });
            const nodeInstanced = new THREE.InstancedMesh(nodeGeom, nodeMat, data.nodes.length);
            const matrix = new THREE.Matrix4();

            data.nodes.forEach((n, i) => {
                matrix.setPosition(n.x, n.y + 0.01, n.z);
                nodeInstanced.setMatrixAt(i, matrix);
            });
            nodeInstanced.instanceMatrix.needsUpdate = true;
            graphGroup.add(nodeInstanced);

            // Render edges
            const linePositions = [];
            const nodeMap = new Map();
            data.nodes.forEach(n => nodeMap.set(n.id, [n.x, n.y + 0.01, n.z]));

            data.edges.forEach(e => {
                const p1 = nodeMap.get(e.source);
                const p2 = nodeMap.get(e.target);
                if (p1 && p2) {
                    linePositions.push(...p1, ...p2);
                }
            });

            if (linePositions.length > 0) {
                const lineGeom = new THREE.BufferGeometry();
                lineGeom.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
                const lineMat = new THREE.LineBasicMaterial({ color: 0x00bcd4, transparent: true, opacity: 0.6 });
                const lines = new THREE.LineSegments(lineGeom, lineMat);
                graphGroup.add(lines);
            }

            graphGroup.visible = this.layerVisibility.navGraph;
            this.layers.navGraph = graphGroup;
            this.scene.add(graphGroup);
        } catch (e) {
            console.warn("Could not load nav graph visualizer:", e);
        }
    }

    setLayerVisible(name, visible) {
        this.layerVisibility[name] = visible;
        if (this.layers[name]) {
            this.layers[name].visible = visible;
        }
    }

    applyWireframe(wireframe) {
        this.layerVisibility.wireframe = wireframe;
        this.scene.traverse((obj) => {
            if (obj.isMesh && obj.material && obj !== this.layers.playerHelper) {
                if (Array.isArray(obj.material)) {
                    obj.material.forEach(m => m.wireframe = wireframe);
                } else {
                    obj.material.wireframe = wireframe;
                }
            }
        });
    }

    update() {
        const delta = this.clock.getDelta();

        if (this.currentMode === "POV") {
            this.player.update(delta);
        } else {
            this.orbitControls.update();
            // Sync player helper position in orbit mode
            if (this.layers.playerHelper) {
                this.layers.playerHelper.position.set(
                    this.player.position.x,
                    this.player.position.y + this.player.height * 0.5,
                    this.player.position.z
                );
            }
        }

        this.renderer.render(this.scene, this.camera);
    }
}

window.WorldEngine = WorldEngine;
