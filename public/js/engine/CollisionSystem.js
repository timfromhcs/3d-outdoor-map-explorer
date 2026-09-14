/**
 * CollisionSystem.js
 * High-performance kinematic collision detection, floor snapping, slope testing,
 * and wall sliding against physical collision meshes.
 */
class CollisionSystem {
    constructor() {
        this.collisionMesh = null;
        this.walkableMesh = null;
        this.bounds = null;
        this.maxSlopeDeg = 45.0;
        this.raycaster = new THREE.Raycaster();
        this.downVector = new THREE.Vector3(0, -1, 0);
    }

    /**
     * Sets the active collision and walkable meshes for the current map.
     */
    setCollisionMesh(colMesh, walkMesh, bounds) {
        this.collisionMesh = colMesh;
        this.walkableMesh = walkMesh;
        this.bounds = bounds;

        // Build BVH if library is present
        [this.collisionMesh, this.walkableMesh].forEach(mesh => {
            if (mesh && mesh.geometry && window.MeshBVH && !mesh.geometry.boundsTree) {
                try {
                    mesh.geometry.computeBoundsTree();
                } catch (e) {
                    console.warn("BVH generation note:", e);
                }
            }
        });
    }

    /**
     * Casts a ray downward to detect ground contact and slope.
     * @param {THREE.Vector3} playerPos Base feet position
     * @param {number} stepHeight Maximum step height player can step up
     * @returns {Object|null} Ground hit info { groundY, normal, slopeDeg, distance }
     */
    checkGround(playerPos, stepHeight = 0.04) {
        const targetMesh = this.collisionMesh || this.walkableMesh;
        if (!targetMesh) {
            return { groundY: 0, normal: new THREE.Vector3(0, 1, 0), slopeDeg: 0, distance: playerPos.y };
        }

        // Ray origin placed slightly above feet
        const origin = new THREE.Vector3(playerPos.x, playerPos.y + stepHeight + 0.06, playerPos.z);
        this.raycaster.set(origin, this.downVector);
        this.raycaster.near = 0.001;
        this.raycaster.far = stepHeight + 0.35;

        const hits = this.raycaster.intersectObject(targetMesh, true);
        if (hits.length > 0) {
            const hit = hits[0];
            let normal = hit.face ? hit.face.normal.clone() : new THREE.Vector3(0, 1, 0);
            normal.transformDirection(hit.object.matrixWorld);

            const dot = Math.max(-1, Math.min(1, normal.dot(new THREE.Vector3(0, 1, 0))));
            const slopeDeg = Math.acos(dot) * (180 / Math.PI);

            return {
                groundY: hit.point.y,
                normal: normal,
                slopeDeg: slopeDeg,
                distance: origin.y - hit.point.y
            };
        }

        return null;
    }

    /**
     * Tests horizontal movement against walls and obstacles.
     * If an obstacle is hit within radius, velocity is deflected along the wall plane.
     * @param {THREE.Vector3} currentPos Current feet position
     * @param {THREE.Vector3} desiredVelocity Desired movement velocity
     * @param {number} radius Player collision radius
     * @param {number} height Player height
     * @returns {THREE.Vector3} Adjusted velocity vector
     */
    collideAndSlide(currentPos, desiredVelocity, radius = 0.03, height = 0.15) {
        const targetMesh = this.collisionMesh || this.walkableMesh;
        if (!targetMesh || desiredVelocity.lengthSq() < 1e-8) {
            return desiredVelocity.clone();
        }

        const moveDir = desiredVelocity.clone().normalize();
        const testHeights = [height * 0.3, height * 0.7]; // Test at knee and chest height
        let adjustedVelocity = desiredVelocity.clone();

        for (const h of testHeights) {
            const origin = new THREE.Vector3(currentPos.x, currentPos.y + h, currentPos.z);
            this.raycaster.set(origin, moveDir);
            this.raycaster.near = 0.001;
            this.raycaster.far = radius + 0.02;

            const hits = this.raycaster.intersectObject(targetMesh, true);
            if (hits.length > 0) {
                const hit = hits[0];
                if (hit.face) {
                    const wallNormal = hit.face.normal.clone();
                    wallNormal.transformDirection(hit.object.matrixWorld);
                    wallNormal.y = 0; // Horizontal wall deflection only
                    wallNormal.normalize();

                    // Deflect velocity along wall: v_slide = v - (v . n) * n
                    const dot = adjustedVelocity.dot(wallNormal);
                    if (dot < 0) {
                        adjustedVelocity.sub(wallNormal.multiplyScalar(dot));
                    }
                }
            }
        }

        return adjustedVelocity;
    }

    /**
     * Checks if player has fallen out of the world boundaries.
     */
    isOutOfBounds(position) {
        if (!this.bounds) return position.y < -5.0;
        return position.y < (this.bounds.min[1] - 0.5);
    }
}

window.CollisionSystem = CollisionSystem;
