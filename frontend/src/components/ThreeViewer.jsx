import { useEffect, useRef } from "react";
import * as THREE from "three";

const SCALE = 20;
const WALL_HEIGHT = 3;
const WALL_COLORS = { exterior: 0xe74c3c, interior_load_bearing: 0xf39c12, partition: 0x3498db };
const ROOM_COLORS = [0x1abc9c, 0x9b59b6, 0x3498db, 0xe67e22, 0x2ecc71, 0xe91e63, 0x00bcd4, 0xff5722];

export default function ThreeViewer({ analysis }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!analysis || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const W = canvas.clientWidth || 800;
    const H = canvas.clientHeight || 500;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 500);
    camera.position.set(15, 18, 22);
    camera.lookAt(10, 0, 10);

    scene.add(new THREE.AmbientLight(0x334466, 0.8));
    const sun = new THREE.DirectionalLight(0xffeedd, 1.5);
    sun.position.set(20, 30, 20);
    scene.add(sun);

    scene.add(new THREE.GridHelper(60, 60, 0x112244, 0x0d1a2e));

    // Draw Walls
    (analysis.walls || []).forEach((wall) => {
      const sp = wall.start_point, ep = wall.end_point;
      if (!sp || !ep) return;
      
      const x1 = sp.x * SCALE, z1 = sp.y * SCALE;
      const x2 = ep.x * SCALE, z2 = ep.y * SCALE;
      const dx = x2 - x1, dz = z2 - z1;
      const length = Math.sqrt(dx * dx + dz * dz);
      if (length < 0.05) return;

      const thickness = wall.thickness === "thick" ? 0.35 : wall.thickness === "standard" ? 0.25 : 0.15;
      const color = WALL_COLORS[wall.type] || 0x888888;

      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(length, WALL_HEIGHT, thickness),
        new THREE.MeshStandardMaterial({ color, roughness: 0.7 })
      );
      mesh.position.set((x1 + x2) / 2, WALL_HEIGHT / 2, (z1 + z2) / 2);
      mesh.rotation.y = -Math.atan2(dz, dx);
      scene.add(mesh);
    });

    // Draw Rooms (Floors)
    (analysis.rooms || []).forEach((room, i) => {
      const bb = room.bounding_box;
      if (!bb) return;
      const rx = bb.x_min * SCALE, rz = bb.y_min * SCALE;
      const rw = (bb.x_max - bb.x_min) * SCALE, rd = (bb.y_max - bb.y_min) * SCALE;
      if (rw < 0.1 || rd < 0.1) return;

      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(rw, 0.05, rd),
        new THREE.MeshStandardMaterial({ color: ROOM_COLORS[i % ROOM_COLORS.length], transparent: true, opacity: 0.35 })
      );
      mesh.position.set(rx + rw / 2, 0.03, rz + rd / 2);
      scene.add(mesh);
    });

    // Camera Controls
    let isDragging = false, prevMouse = { x: 0, y: 0 };
    let spherical = { theta: Math.PI / 4, phi: Math.PI / 3.5, radius: 35 };
    let target = new THREE.Vector3(10, 0, 10);

    function updateCamera() {
      camera.position.set(
        target.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta),
        target.y + spherical.radius * Math.cos(spherical.phi),
        target.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta)
      );
      camera.lookAt(target);
    }
    updateCamera();

    const onDown = (e) => { isDragging = true; prevMouse = { x: e.clientX, y: e.clientY }; };
    const onUp = () => isDragging = false;
    const onMove = (e) => {
      if (!isDragging) return;
      spherical.theta -= (e.clientX - prevMouse.x) * 0.008;
      spherical.phi = Math.max(0.1, Math.min(Math.PI / 2.1, spherical.phi + (e.clientY - prevMouse.y) * 0.008));
      prevMouse = { x: e.clientX, y: e.clientY };
      updateCamera();
    };
    const onWheel = (e) => {
      spherical.radius = Math.max(8, Math.min(80, spherical.radius + e.deltaY * 0.05));
      updateCamera();
    };

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("mousemove", onMove);
    canvas.addEventListener("wheel", onWheel);

    let animId;
    function animate() {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("wheel", onWheel);
      renderer.dispose();
    };
  }, [analysis]);

  return (
    <div style={{ position: "relative", width: "100%", height: "400px", background: "#0a0f1a", borderRadius: "10px", overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", cursor: "grab" }} />
      <div style={{ position: "absolute", bottom: 10, left: 10, background: "rgba(0,0,0,0.5)", padding: "4px 8px", borderRadius: "4px", fontSize: "10px", color: "#94a3b8" }}>
        Drag to rotate • Scroll to zoom
      </div>
    </div>
  );
}