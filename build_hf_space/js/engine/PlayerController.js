/**
 * PlayerController.js
 * First-person kinematic character controller with PointerLockControls,
 * sprint, jump, gravity, and collision integration.
 */
class PlayerController {
    constructor(camera, domElement, collisionSystem) {
        this.camera = camera;
        this.domElement = domElement;
        this.collision = collisionSystem;

        // Player Physical Dimensions (calibrated to map scale)
        this.height = 0.18;
        this.eyeHeight = 0.16;
        this.radius = 0.035;
        this.stepHeight = 0.03;

        // Kinematic state
        this.position = new THREE.Vector3(0, 0.5, 0);
        this.velocity = new THREE.Vector3();
        this.grounded = false;
        this.movementState = "IDLE"; // "IDLE", "WALKING", "SPRINTING", "IN_AIR"

        // Speeds
        this.baseWalkSpeed = 0.35;
        this.baseSprintSpeed = 0.70;
        this.jumpVelocity = 0.85;
        this.gravity = 2.8;

        // PointerLock
        this.controls = new THREE.PointerLockControls(this.camera, this.domElement);
        this.isLocked = false;

        // Input state
        this.inputs = {
            forward: false,
            backward: false,
            left: false,
            right: false,
            sprint: false,
            jump: false
        };

        this.spawnPoint = { position: [0, 0.5, 0], lookYaw: 0 };
        this._setupInputListeners();
    }

    _setupInputListeners() {
        this.controls.addEventListener('lock', () => {
            this.isLocked = true;
            if (this.onLockChange) this.onLockChange(true);
        });

        this.controls.addEventListener('unlock', () => {
            this.isLocked = false;
            if (this.onLockChange) this.onLockChange(false);
        });

        const onKeyDown = (e) => {
            switch (e.code) {
                case 'KeyW': case 'ArrowUp': this.inputs.forward = true; break;
                case 'KeyS': case 'ArrowDown': this.inputs.backward = true; break;
                case 'KeyA': case 'ArrowLeft': this.inputs.left = true; break;
                case 'KeyD': case 'ArrowRight': this.inputs.right = true; break;
                case 'ShiftLeft': case 'ShiftRight': this.inputs.sprint = true; break;
                case 'Space':
                    if (this.grounded) {
                        this.velocity.y = this.jumpVelocity;
                        this.grounded = false;
                    }
                    break;
            }
        };

        const onKeyUp = (e) => {
            switch (e.code) {
                case 'KeyW': case 'ArrowUp': this.inputs.forward = false; break;
                case 'KeyS': case 'ArrowDown': this.inputs.backward = false; break;
                case 'KeyA': case 'ArrowLeft': this.inputs.left = false; break;
                case 'KeyD': case 'ArrowRight': this.inputs.right = false; break;
                case 'ShiftLeft': case 'ShiftRight': this.inputs.sprint = false; break;
            }
        };

        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('keyup', onKeyUp);
    }

    /**
     * Resets player position and view to current map's safe spawn point.
     */
    respawn() {
        this.position.set(this.spawnPoint.position[0], this.spawnPoint.position[1], this.spawnPoint.position[2]);
        this.velocity.set(0, 0, 0);
        this.grounded = false;
        this.camera.position.set(this.position.x, this.position.y + this.eyeHeight, this.position.z);
        if (this.spawnPoint.lookYaw !== undefined) {
            this.camera.rotation.set(0, THREE.MathUtils.degToRad(this.spawnPoint.lookYaw), 0);
        }
    }

    /**
     * Configures the safe spawn point and calibrates controller parameters to map extents.
     */
    setSpawn(spawnData, mapExtents) {
        this.spawnPoint = spawnData;

        // Calibrate scale based on map vertical extent
        const extentY = mapExtents ? mapExtents[1] : 0.4;
        const scale = Math.max(0.4, Math.min(2.5, extentY / 0.35));

        this.height = 0.16 * scale;
        this.eyeHeight = 0.14 * scale;
        this.radius = 0.03 * scale;
        this.stepHeight = 0.025 * scale;
        this.baseWalkSpeed = 0.35 * scale;
        this.baseSprintSpeed = 0.70 * scale;
        this.jumpVelocity = 0.85 * Math.sqrt(scale);
        this.gravity = 3.2 * scale;

        this.respawn();
    }

    update(delta) {
        if (delta > 0.1) delta = 0.1; // Clamp large time steps

        // 1. Calculate horizontal intent vector in camera space
        const inputVec = new THREE.Vector3();
        if (this.inputs.forward) inputVec.z -= 1;
        if (this.inputs.backward) inputVec.z += 1;
        if (this.inputs.left) inputVec.x -= 1;
        if (this.inputs.right) inputVec.x += 1;

        const isMoving = inputVec.lengthSq() > 0;
        if (isMoving) inputVec.normalize();

        const currentSpeed = this.inputs.sprint ? this.baseSprintSpeed : this.baseWalkSpeed;

        // Transform input vector to world space horizontal heading
        const yawEuler = new THREE.Euler(0, this.camera.rotation.y, 0, 'YXZ');
        const worldMove = inputVec.applyEuler(yawEuler).multiplyScalar(currentSpeed);

        // 2. Wall collision & sliding
        const horizontalVelocity = this.collision.collideAndSlide(
            this.position,
            worldMove,
            this.radius,
            this.height
        );

        // Apply horizontal movement
        this.position.x += horizontalVelocity.x * delta;
        this.position.z += horizontalVelocity.z * delta;

        // 3. Ground check & Gravity
        const groundHit = this.collision.checkGround(this.position, this.stepHeight);

        if (groundHit && this.velocity.y <= 0) {
            // Player is touching ground
            this.grounded = true;
            this.velocity.y = 0;
            // Smooth snap to ground
            this.position.y = groundHit.groundY;

            if (isMoving) {
                this.movementState = this.inputs.sprint ? "SPRINTING" : "WALKING";
            } else {
                this.movementState = "IDLE";
            }
        } else {
            // In air
            this.grounded = false;
            this.movementState = "IN_AIR";
            this.velocity.y -= this.gravity * delta;
            this.position.y += this.velocity.y * delta;
        }

        // 4. Out of bounds check & auto recovery
        if (this.collision.isOutOfBounds(this.position)) {
            console.warn("Player fell out of world, resetting to safe spawn.");
            this.respawn();
        }

        // 5. Sync camera position to eye level
        this.camera.position.set(
            this.position.x,
            this.position.y + this.eyeHeight,
            this.position.z
        );
    }
}

window.PlayerController = PlayerController;
