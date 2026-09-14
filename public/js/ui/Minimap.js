/**
 * Minimap.js
 * Real-time 2D top-down orthographic minimap rendering map bounds,
 * walkable terrain contours, and player position with heading vision cone.
 */
class Minimap {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.bounds = null;
        this.walkablePoints = [];
    }

    setMapData(manifest, walkMesh) {
        this.bounds = manifest.bounds;
        this.walkablePoints = [];

        if (walkMesh && walkMesh.geometry && walkMesh.geometry.attributes.position) {
            const pos = walkMesh.geometry.attributes.position;
            // Subsample up to 600 points for crisp 2D minimap rendering
            const step = Math.max(1, Math.floor(pos.count / 600));
            for (let i = 0; i < pos.count; i += step) {
                this.walkablePoints.push([pos.getX(i), pos.getZ(i)]);
            }
        }
    }

    worldToMap(x, z, width, height, padding = 12) {
        if (!this.bounds) return [width / 2, height / 2];
        const minX = this.bounds.min[0];
        const maxX = this.bounds.max[0];
        const minZ = this.bounds.min[2];
        const maxZ = this.bounds.max[2];

        const normX = (x - minX) / Math.max(1e-4, (maxX - minX));
        const normZ = (z - minZ) / Math.max(1e-4, (maxZ - minZ));

        const canvasX = padding + normX * (width - padding * 2);
        const canvasY = padding + normZ * (height - padding * 2);

        return [canvasX, canvasY];
    }

    update(playerPos, cameraRotationY) {
        if (!this.ctx || !this.bounds) return;

        const w = this.canvas.width = this.canvas.clientWidth;
        const h = this.canvas.height = this.canvas.clientHeight;

        // Background
        this.ctx.fillStyle = "#090d12";
        this.ctx.fillRect(0, 0, w, h);

        // Map boundary box
        this.ctx.strokeStyle = "#30363d";
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(12, 12, w - 24, h - 24);

        // Walkable surface points
        this.ctx.fillStyle = "rgba(0, 229, 255, 0.35)";
        for (const pt of this.walkablePoints) {
            const [cx, cy] = this.worldToMap(pt[0], pt[1], w, h);
            this.ctx.fillRect(cx - 1, cy - 1, 2, 2);
        }

        // Player marker
        const [px, py] = this.worldToMap(playerPos.x, playerPos.z, w, h);

        // Heading vision cone
        const heading = cameraRotationY; // In Three.js, Y rotation is yaw
        const coneLength = 16;
        const coneFov = 0.5; // radians (~30 deg)

        this.ctx.fillStyle = "rgba(255, 152, 0, 0.25)";
        this.ctx.beginPath();
        this.ctx.moveTo(px, py);
        // Note: in 2D top-down X is right, Z is down, so rotation maps:
        const dirAngle = -heading - Math.PI / 2;
        this.ctx.arc(px, py, coneLength, dirAngle - coneFov, dirAngle + coneFov);
        this.ctx.closePath();
        this.ctx.fill();

        // Player dot
        this.ctx.fillStyle = "#f4511e";
        this.ctx.beginPath();
        this.ctx.arc(px, py, 3.5, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = "#ffffff";
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
    }
}

window.Minimap = Minimap;
