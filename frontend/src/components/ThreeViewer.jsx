import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import * as BufferGeometryUtils from "three/addons/utils/BufferGeometryUtils.js";

// ─── Constants ────────────────────────────────────────────────────────────────
const WALL_HEIGHT = 2.5;

// Unified material palette for visual parity
const WALL_COLOR = 0x1e293b;  // Slate/Charcoal
const SLAB_COLOR = 0xf8fafc;  // Clean Off-White/Beige
const SCENE_BG   = 0x020617;  // Deep Navy/Black

// ─── Component ────────────────────────────────────────────────────────────────
export default function ThreeViewer({ analysis, file }) {
  const containerRef = useRef(null);
  const canvasRef    = useRef(null);
  const tooltipRef   = useRef(null);

  const [showOverlay, setShowOverlay] = useState(false);

  // We keep track of the created scene primitives to dynamically toggle wireframe/overlay
  const wallMeshRef = useRef(null);
  const overlayPlaneRef = useRef(null);

  useEffect(() => {
    if (!analysis || !canvasRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const canvas    = canvasRef.current;
    const tooltip   = tooltipRef.current;
    const W = container.clientWidth  || 800;
    const H = container.clientHeight || 500;

    // ── Renderers ─────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;

    // CSS2D for room labels only
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(W, H);
    labelRenderer.domElement.style.cssText =
      "position:absolute;top:0;left:0;pointer-events:none;overflow:hidden;";
    // Remove stale label renderer if any
    container.querySelectorAll(".css2d-layer").forEach(el => el.remove());
    labelRenderer.domElement.classList.add("css2d-layer");
    container.appendChild(labelRenderer.domElement);

    // ── Scene ─────────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(SCENE_BG);

    // Adjusted camera for better overview
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 1000);
    
    // DECOUPLED FROM PIXELS:
    // Scale building mapping to exactly 20.0 physical units
    const mapWidthM = 20.0;
    const aspect = (analysis.image_height_px || 600) / (analysis.image_width_px || 800);
    const mapHeightM = 20.0 * aspect;
    
    // Default look target is the center of the structure
    const target = new THREE.Vector3(mapWidthM / 2, 0, mapHeightM / 2);
    
    camera.position.set(mapWidthM / 2, 25, mapHeightM + 15);
    camera.lookAt(target);

    // Lighting: High-Visibility Setup
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    
    // Top-down intense directional lighting to highlight the new polished floor material
    const sun = new THREE.DirectionalLight(0xffffff, 1.5);
    sun.position.set(mapWidthM / 2, 20, mapHeightM / 2 + 5);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 2048;
    sun.shadow.mapSize.height = 2048;
    sun.shadow.camera.left = -15;
    sun.shadow.camera.right = 15;
    sun.shadow.camera.top = 15;
    sun.shadow.camera.bottom = -15;
    sun.shadow.bias = -0.0001;
    scene.add(sun);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 1.0);
    scene.add(hemiLight);

    // Grid (scale it to the building size logically)
    const grid = new THREE.GridHelper(Math.max(mapWidthM, mapHeightM) * 1.5, 40, 0x112244, 0x0d1a2e);
    grid.position.set(mapWidthM / 2, -0.01, mapHeightM / 2);
    scene.add(grid);

    const interactable = [];

    // ── Walls via Merged ExtrudeGeometry ─────────────────────────────────────
    const rawWalls = analysis.model_3d?.walls_3d || [];
    
    // Fallback: If backend is stale and missing start/end XZ, reconstruct them from center/length/rotation
    const safeWalls = rawWalls.map(w => {
      if (w.start_x !== undefined) return w;
      const dx = (w.length / 2) * Math.cos(w.rotation_y || 0);
      const dz = (w.length / 2) * Math.sin(w.rotation_y || 0);
      return {
        ...w,
        start_x: w.center_x - dx,
        start_z: w.center_z - dz,
        end_x: w.center_x + dx,
        end_z: w.center_z + dz,
        thickness: w.thickness || 0.2
      };
    });
    
    // 1. JS-side vertex snapping (threshold 0.05)
    const pts = [];
    safeWalls.forEach((w, wi) => {
      pts.push({ x: w.start_x, z: w.start_z, wi, end: 0 });
      pts.push({ x: w.end_x,   z: w.end_z,   wi, end: 1 });
    });

    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x;
        const dz = pts[i].z - pts[j].z;
        if (Math.sqrt(dx * dx + dz * dz) < 0.05 && pts[i].wi !== pts[j].wi) {
          const mx = (pts[i].x + pts[j].x) / 2;
          const mz = (pts[i].z + pts[j].z) / 2;
          pts[i].x = pts[j].x = mx;
          pts[i].z = pts[j].z = mz;
        }
      }
    }

    const snappedWalls = safeWalls.map((w, wi) => {
      const s = pts.find(p => p.wi === wi && p.end === 0);
      const e = pts.find(p => p.wi === wi && p.end === 1);
      return { ...w, start_x: s.x, start_z: s.z, end_x: e.x, end_z: e.z };
    });

    // 2. Build Extrude geometries
    const wallGeometries = [];
    snappedWalls.forEach(wall => {
      const { start_x, start_z, end_x, end_z, thickness, height } = wall;
      const dx = end_x - start_x;
      const dz = end_z - start_z;
      const len = Math.sqrt(dx * dx + dz * dz);
      if (len < 0.01) return;

      const px = -dz / len;
      const pz =  dx / len;
      const half = (thickness || 0.2) / 2; // uniform architectural thickness

      const shape = new THREE.Shape();
      shape.moveTo(start_x + px * half, start_z + pz * half);
      shape.lineTo(end_x   + px * half, end_z   + pz * half);
      shape.lineTo(end_x   - px * half, end_z   - pz * half);
      shape.lineTo(start_x - px * half, start_z - pz * half);
      shape.closePath();

      const fixedWallHeight = 2.5;
      const geo = new THREE.ExtrudeGeometry(shape, {
        depth: fixedWallHeight,
        bevelEnabled: false,
      });
      // Rotate +90deg on X to map 2D Shape (X, Y) to World (X, Z).
      // This sends the extrusion depth down into -Y. Translate back up by height.
      geo.rotateX(Math.PI / 2);
      geo.translate(0, fixedWallHeight, 0);
      
      wallGeometries.push(geo);
    });

    // 3. Merge all geometries into ONE contiguous mesh
    if (wallGeometries.length > 0) {
      try {
        const mergedGeo = BufferGeometryUtils.mergeGeometries(wallGeometries, false);
        const wallMat = new THREE.MeshStandardMaterial({ 
          color: WALL_COLOR, 
          roughness: 0.6,
          wireframe: showOverlay 
        });
        const wallMeshComponent = new THREE.Mesh(mergedGeo, wallMat);
        wallMeshComponent.castShadow = !showOverlay;
        wallMeshComponent.receiveShadow = !showOverlay;
        
        wallMeshComponent.userData = {
          type: "Contiguous Wall Structure",
          classification: "Structural Walls",
          dimensions: "Unified Mesh",
        };
        scene.add(wallMeshComponent);
        interactable.push(wallMeshComponent);
        wallMeshRef.current = wallMeshComponent;

        // Wall Edges: Cyan Glow Wireframe Overlay via EdgesGeometry
        if (!showOverlay) {
          const edgesGeo = new THREE.EdgesGeometry(mergedGeo);
          const edgesMat = new THREE.LineBasicMaterial({
            color: 0x22d3ee,
            transparent: true,
            opacity: 0.6,
            depthTest: true
          });
          const edgesMesh = new THREE.LineSegments(edgesGeo, edgesMat);
          // Nudge slightly up to avoid strictly identical Z-fighting with mesh
          edgesMesh.position.y += 0.001;
          scene.add(edgesMesh);
        }
      } catch (err) {
        console.error("Failed to merge wall geometries:", err);
      }
    }

    // ── Windows (translucent panes) ───────────────────────────────────────────
    const openings = analysis.model_3d?.openings_3d || [];
    openings.forEach(op => {
      if (op.opening_type !== "window" || showOverlay) return; // Hide windows if overlay is on
      const mat = new THREE.MeshStandardMaterial({
        color: 0x22d3ee, roughness: 0.05, metalness: 0.3,
        transparent: true, opacity: 0.55,
      });
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(op.width, op.height, op.thickness + 0.03),
        mat
      );
      mesh.position.set(op.center_x, op.center_y, op.center_z);
      mesh.rotation.y = op.rotation_y || 0;
      mesh.userData = {
        type: "Window",
        classification: "Aperture — Glass",
        dimensions: `${op.width.toFixed(2)}m × ${op.height.toFixed(2)}m`,
      };
      scene.add(mesh);
      interactable.push(mesh);
    });

    // ── Unified Baseplate (Floor Parity Fix) ─────────────────────────────────
    const baseplatePts = analysis.model_3d?.baseplate_polygon || [];
    if (baseplatePts.length > 2 && !showOverlay) {
      const shape = new THREE.Shape();
      shape.moveTo(baseplatePts[0][0], baseplatePts[0][1]);
      for (let i = 1; i < baseplatePts.length; i++) {
        shape.lineTo(baseplatePts[i][0], baseplatePts[i][1]);
      }
      shape.closePath();

      // Generates a proper single 2D flat geometric mesh without overlapping doorways
      const baseGeo = new THREE.ShapeGeometry(shape);
      
      // Map 2D Shape (X, Y) up to 3D World (X, Z)
      baseGeo.rotateX(Math.PI / 2);
      
      // Procedural Terrazzo / Polished Concrete Noise Map Generator
      const noiseSize = 512;
      const cvs = document.createElement("canvas");
      cvs.width = noiseSize; cvs.height = noiseSize;
      const ctx = cvs.getContext("2d");
      const imgData = ctx.createImageData(noiseSize, noiseSize);
      for (let i = 0; i < imgData.data.length; i += 4) {
        // Generate very subtle high-frequency architectural noise
        const val = 245 + Math.random() * 10;
        imgData.data[i] = val;
        imgData.data[i+1] = val;
        imgData.data[i+2] = val;
        imgData.data[i+3] = 255;
      }
      ctx.putImageData(imgData, 0, 0);
      const floorTex = new THREE.CanvasTexture(cvs);
      floorTex.wrapS = THREE.RepeatWrapping;
      floorTex.wrapT = THREE.RepeatWrapping;
      floorTex.repeat.set(15, 15);
      
      const baseMat = new THREE.MeshStandardMaterial({
        color: 0xfcfcfc,          // Carrara Marble Off-White
        roughness: 0.2,           // Very polished surface
        metalness: 0.05,          // Slight sheen reflection
        map: floorTex,            // Subtle Albedo texture
        bumpMap: floorTex,        // Micro-texture normal relief
        bumpScale: 0.001,         // Invisible except for speculative glints
      });
      const baseMesh = new THREE.Mesh(baseGeo, baseMat);
      // Place exactly at Z=0 (actually Y= -0.01 in Three.js coordinates to prevent Z-fighting)
      baseMesh.position.set(0, -0.01, 0);
      baseMesh.receiveShadow = true;
      baseMesh.userData = {
        type: "Foundation Baseplate",
        classification: "Continuous Floor",
        dimensions: "Unified Mesh"
      };
      scene.add(baseMesh);
      interactable.push(baseMesh);
    }
    
    // ── Room floor slabs + CSS2D labels ───────────────────────────────────────
    const slabs = analysis.model_3d?.slabs || [];
    slabs.forEach((slab, i) => {
      if (slab.width < 0.1 || slab.depth < 0.1) return;
      
      // FRAGMENTED BOX GEOMETRY SLABS REMOVED TO PREVENT TRIANGULATION GAPS ON OPEN DOORS

      // CSS2D room label at centroid
      const labelDiv = document.createElement("div");
      labelDiv.style.cssText = `
        color: #f8fafc;
        background: rgba(15, 23, 42, 0.7);
        padding: 4px 8px;
        border-radius: 4px;
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        pointer-events: none;
        white-space: nowrap;
        border: 1px solid rgba(34, 211, 238, 0.3);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
      `;
      labelDiv.textContent = slab.room_name || `Room ${i + 1}`;

      const label = new CSS2DObject(labelDiv);
      // float label slightly above walls
      label.position.set(
        slab.centroid_x ?? slab.center_x,
        WALL_HEIGHT + 0.5,
        slab.centroid_z ?? slab.center_z
      );
      scene.add(label);
    });

    // ── Reference Overlay Plane ───────────────────────────────────────────────
    if (showOverlay && file) {
      const imgUrl = URL.createObjectURL(file);
      const textureLoader = new THREE.TextureLoader();
      textureLoader.load(imgUrl, (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        // Flip Y if needed, normally ThreeJS textures have Y flipped vs Web
        const planeGeo = new THREE.PlaneGeometry(mapWidthM, mapHeightM);
        const planeMat = new THREE.MeshBasicMaterial({ 
          map: texture, 
          side: THREE.FrontSide 
        });
        const plane = new THREE.Mesh(planeGeo, planeMat);
        
        // PlaneGeometry faces Z by default. Rotate to face Y (up).
        plane.rotation.x = -Math.PI / 2;
        // Position it at half width/height so it matches the 0->Width coordinate space
        plane.position.set(mapWidthM / 2, -0.05, mapHeightM / 2);
        
        scene.add(plane);
        overlayPlaneRef.current = plane;
      });
    }

    // ── Camera orbit ──────────────────────────────────────────────────────────
    let isDragging = false, prevMouse = { x: 0, y: 0 };
    // Start zoomed out enough to see the whole model
    let sph = { theta: 0, phi: Math.PI / 3, radius: Math.max(mapWidthM, mapHeightM) * 1.2 };

    function updateCamera() {
      camera.position.set(
        target.x + sph.radius * Math.sin(sph.phi) * Math.sin(sph.theta),
        target.y + sph.radius * Math.cos(sph.phi),
        target.z + sph.radius * Math.sin(sph.phi) * Math.cos(sph.theta)
      );
      camera.lookAt(target);
    }
    updateCamera();

    // ── Raycaster + cursor-tracked tooltip ───────────────────────────────────
    const raycaster = new THREE.Raycaster();
    const mouse2D   = new THREE.Vector2();

    const onDown = e => {
      isDragging = true;
      prevMouse  = { x: e.clientX, y: e.clientY };
      tooltip.style.display = "none";
    };

    const onUp = () => { isDragging = false; };

    const onLeave = () => {
      isDragging = false;
      tooltip.style.display = "none";
    };

    const onMove = e => {
      const rect = container.getBoundingClientRect();
      const cx = e.clientX, cy = e.clientY;

      if (isDragging) {
        sph.theta -= (cx - prevMouse.x) * 0.008;
        sph.phi    = Math.max(0.1, Math.min(Math.PI / 2.1,
                       sph.phi + (cy - prevMouse.y) * 0.008));
        prevMouse  = { x: cx, y: cy };
        updateCamera();
        return; // skip raycasting while orbiting
      }

      mouse2D.x = ((cx - rect.left) / rect.width)  *  2 - 1;
      mouse2D.y = ((cy - rect.top)  / rect.height) * -2 + 1;

      raycaster.setFromCamera(mouse2D, camera);
      const hits = raycaster.intersectObjects(interactable);

      if (hits.length > 0) {
        const { object, point } = hits[0];
        const d = object.userData;

        tooltip.innerHTML = `
          <div style="color:#22d3ee;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">${d.type}</div>
          <div style="color:#94a3b8;font-size:9px">Class</div>
          <div style="color:#f1f5f9;font-size:10px;margin-bottom:4px">${d.classification}</div>
          <div style="color:#94a3b8;font-size:9px">Dims</div>
          <div style="color:#f1f5f9;font-size:10px;margin-bottom:4px">${d.dimensions}</div>
          <div style="color:#94a3b8;font-size:9px">XYZ</div>
          <div style="font-family:ui-monospace,monospace;font-size:10px;color:#38bdf8">(${point.x.toFixed(2)}, ${point.y.toFixed(2)}, ${point.z.toFixed(2)})</div>
        `;
        // Anchor to cursor with strict 20px offset
        tooltip.style.display = "block";
        tooltip.style.left = `${cx - rect.left + 20}px`;
        tooltip.style.top  = `${cy - rect.top  + 20}px`;
      } else {
        tooltip.style.display = "none";
      }
    };

    const onWheel = e => {
      e.preventDefault();
      sph.radius = Math.max(8, Math.min(150, sph.radius + e.deltaY * 0.05));
      updateCamera();
    };

    container.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    container.addEventListener("mousemove", onMove);
    container.addEventListener("mouseleave", onLeave);
    container.addEventListener("wheel", onWheel, { passive: false });

    const onResize = () => {
      const nW = container.clientWidth, nH = container.clientHeight;
      camera.aspect = nW / nH;
      camera.updateProjectionMatrix();
      renderer.setSize(nW, nH);
      labelRenderer.setSize(nW, nH);
    };
    window.addEventListener("resize", onResize);

    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      container.removeEventListener("mousemove", onMove);
      container.removeEventListener("mouseleave", onLeave);
      container.removeEventListener("wheel", onWheel);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      labelRenderer.domElement?.remove();
    };
  }, [analysis, file, showOverlay]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        height: "100%",
      }}
    >
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={() => setShowOverlay(!showOverlay)}
          style={{
            background: showOverlay ? "#3b82f6" : "transparent",
            color: showOverlay ? "#fff" : "#3b82f6",
            border: "1px solid #3b82f6",
            padding: "4px 12px",
            borderRadius: "6px",
            fontSize: "12px",
            fontWeight: "600",
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          {showOverlay ? "Hide Wireframe Overlay" : "Verify 1:1 Wireframe Overlay"}
        </button>
      </div>
      
      <div
        ref={containerRef}
        style={{
          position: "relative",
          width: "100%",
          flex: 1,
          minHeight: "460px",
          background: "#020617",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      >
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%", display: "block", cursor: "grab" }}
        />

        {/* Cursor-tracked tooltip — completely non-intrusive styling */}
        <div
          ref={tooltipRef}
          style={{
            display: "none",
            position: "absolute",
            width: "140px",
            background: "rgba(15, 23, 42, 0.45)",
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
            border: "1px solid #22d3ee",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
            borderRadius: "6px",
            padding: "10px",
            pointerEvents: "none",
            lineHeight: "1.4",
            zIndex: 20,
          }}
        />

        <div
          style={{
            position: "absolute", bottom: 10, left: 10,
            background: "rgba(0,0,0,0.45)",
            padding: "4px 8px", borderRadius: "4px",
            fontSize: "10px", color: "#64748b",
            pointerEvents: "none", zIndex: 5,
          }}
        >
          Drag to orbit · Scroll to zoom · Hover for details
        </div>
      </div>
    </div>
  );
}