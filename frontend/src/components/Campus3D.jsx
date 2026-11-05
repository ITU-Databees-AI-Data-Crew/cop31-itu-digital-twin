// Middle panel: the campus as a small architectural model.
// Real OSM data: boundary (raised as a plinth), buildings extruded by floor count, roads and paths,
// green areas with low-poly trees (tree positions are decorative, not surveyed), and the lake.
// Only the three modelled buildings (demo_id) can be clicked.

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { api } from "../api";
import { useApp, useDataHour, useFetch } from "../state";
import { HEADLINE, LABEL, SHORT, SYSTEMS, SYSTEM_LABEL, value } from "../util";

const FLOOR_M = 3.4;
const OVERVIEW = [0.12, 1.08, 1.32]; // camera position for the whole campus, in campus widths
const PLINTH_M = 14;
const R = 6371000;
const BG = "#080e12";
const LOW = new THREE.Color("#4fd1a5");
const HIGH = new THREE.Color("#e5604d");
const FOOT = new Set(["footway", "path", "pedestrian", "steps", "cycleway", "track", "corridor"]);

// --- geometry helpers ---------------------------------------------------------

function makeProjector(boundary) {
  const lons = boundary.map((p) => p[0]), lats = boundary.map((p) => p[1]);
  const lon0 = (Math.min(...lons) + Math.max(...lons)) / 2;
  const lat0 = (Math.min(...lats) + Math.max(...lats)) / 2;
  const k = Math.cos((lat0 * Math.PI) / 180);
  return ([lon, lat]) => [((lon - lon0) * Math.PI) / 180 * R * k, ((lat - lat0) * Math.PI) / 180 * R];
}

const shapeOf = (ring) => new THREE.Shape(ring.map(([x, y]) => new THREE.Vector2(x, y)));
const open = (ring) => (ring.length > 1 && ring[0][0] === ring.at(-1)[0] && ring[0][1] === ring.at(-1)[1] ? ring.slice(0, -1) : ring);

// A flat shape lying on the ground at height y (shape y = north = -z).
function flat(ring, y) {
  const g = new THREE.ShapeGeometry(shapeOf(ring));
  g.rotateX(-Math.PI / 2);
  g.translate(0, y, 0);
  return g;
}

// Walls only: in this three.js version ExtrudeGeometry produces no caps at all (0 cap triangles,
// even for a plain square), so roofs are added separately as flat shapes.
function walls(ring, height, base = 0) {
  const g = new THREE.ExtrudeGeometry(shapeOf(ring), { depth: height, bevelEnabled: false });
  g.clearGroups();
  g.rotateX(-Math.PI / 2);
  g.translate(0, base, 0);
  return g;
}

// A closed block: walls + roof.
function extruded(ring, height, base = 0) {
  return mergeGeometries([walls(ring, height, base), flat(ring, base + height).toNonIndexed()], false);
}

// Roads as flat ribbons (lines are 1 px in WebGL, which looks thin and noisy).
function ribbons(lines, width, y, keep = () => true) {
  const pos = [];
  for (const line of lines) {
    for (let i = 0; i < line.length - 1; i++) {
      if (!keep(line[i]) || !keep(line[i + 1])) continue;
      const [x1, y1] = line[i], [x2, y2] = line[i + 1];
      const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
      const nx = (-dy / len) * (width / 2), ny = (dx / len) * (width / 2);
      const a = [x1 + nx, y, -(y1 + ny)], b = [x1 - nx, y, -(y1 - ny)];
      const c = [x2 + nx, y, -(y2 + ny)], d = [x2 - nx, y, -(y2 - ny)];
      pos.push(...a, ...b, ...c, ...b, ...d, ...c);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

function inside([x, y], ring) {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

function seeded(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Deterministic tree spots inside the green areas, away from buildings.
function treeSpots(greens, buildings, max = 1800) {
  const rand = seeded(31);
  const spots = [];
  for (const ring of greens) {
    const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const tries = Math.min(400, Math.ceil(((x1 - x0) * (y1 - y0)) / 220));
    for (let i = 0; i < tries; i++) {
      const p = [x0 + rand() * (x1 - x0), y0 + rand() * (y1 - y0)];
      if (inside(p, ring) && !buildings.some((b) => inside(p, b))) spots.push({ p, s: 3 + rand() * 3.4 });
    }
  }
  const step = Math.max(1, spots.length / max);
  return spots.filter((_, i) => i % Math.ceil(step) === 0).slice(0, max);
}

function buildScene(geojson) {
  const fs = geojson.features;
  const boundary = fs.find((f) => f.properties.kind === "campus");
  const toXY = makeProjector(boundary.geometry.coordinates[0]);
  const ring = (f) => open(f.geometry.coordinates[0].map(toXY));

  const plinthRing = ring(boundary);
  const xs = plinthRing.map((p) => p[0]), ys = plinthRing.map((p) => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));

  const blds = fs.filter((f) => f.properties.kind === "building").map((f) => {
    const p = f.properties;
    const r = ring(f);
    const height = p.height_m || (p.levels ? p.levels * FLOOR_M : 2 * FLOOR_M);
    const cx = r.reduce((s, q) => s + q[0], 0) / r.length, cy = r.reduce((s, q) => s + q[1], 0) / r.length;
    return { ...p, ring: r, height, center: new THREE.Vector3(cx, height, -cy), geometry: extruded(r, height) };
  });
  const plain = blds.filter((b) => !b.demo_id);
  const greens = fs.filter((f) => f.properties.kind === "green").map(ring).filter((r) => r.length >= 3);
  const lake = fs.filter((f) => f.properties.kind === "lake").map(ring);
  const roads = fs.filter((f) => f.properties.kind === "road");
  const roadLine = (f) => f.geometry.coordinates.map(toXY);

  const onCampus = (p) => inside(p, plinthRing);
  const merge = (list) => (list.length ? mergeGeometries(list, false) : null);
  const plainGeom = merge(plain.map((b) => b.geometry));
  return {
    span,
    plinth: walls(plinthRing, PLINTH_M, -PLINTH_M),
    plinthTop: flat(plinthRing, 0.02),
    plinthEdge: new THREE.EdgesGeometry(walls(plinthRing, PLINTH_M, -PLINTH_M), 40),
    greens: merge(greens.map((r) => flat(r, 0.15))),
    lake: merge(lake.map((r) => flat(r, 0.35))),
    roads: ribbons(roads.filter((f) => !FOOT.has(f.properties.highway)).map(roadLine), 6, 0.25, onCampus),
    paths: ribbons(roads.filter((f) => FOOT.has(f.properties.highway)).map(roadLine), 2.4, 0.22, onCampus),
    plain: plainGeom,
    plainEdges: plainGeom ? new THREE.EdgesGeometry(plainGeom, 30) : null,
    demo: blds.filter((b) => b.demo_id).map((b) => ({ ...b, edges: new THREE.EdgesGeometry(b.geometry, 30) })),
    trees: treeSpots(greens, blds.map((b) => b.ring)),
  };
}

// --- scene parts --------------------------------------------------------------

function Trees({ spots }) {
  const crowns = useRef(), trunks = useRef();
  useEffect(() => {
    const m = new THREE.Object3D();
    spots.forEach(({ p, s }, i) => {
      m.position.set(p[0], s * 1.15, -p[1]);
      m.scale.set(s, s * 1.25, s);
      m.rotation.set(0, (i * 2.399) % (Math.PI * 2), 0);
      m.updateMatrix();
      crowns.current.setMatrixAt(i, m.matrix);
      m.position.set(p[0], s * 0.3, -p[1]);
      m.scale.set(0.35, s * 0.6, 0.35);
      m.updateMatrix();
      trunks.current.setMatrixAt(i, m.matrix);
    });
    crowns.current.instanceMatrix.needsUpdate = true;
    trunks.current.instanceMatrix.needsUpdate = true;
  }, [spots]);
  return (
    <>
      <instancedMesh ref={crowns} args={[null, null, spots.length]} raycast={() => null}>
        <icosahedronGeometry args={[1, 0]} />
        <meshStandardMaterial color="#376543" roughness={0.9} flatShading />
      </instancedMesh>
      <instancedMesh ref={trunks} args={[null, null, spots.length]} raycast={() => null}>
        <cylinderGeometry args={[1, 1, 1, 5]} />
        <meshStandardMaterial color="#304237" />
      </instancedMesh>
    </>
  );
}

// Flies the camera to the selected building, or back to the whole campus. Any drag cancels the flight.
function CameraRig({ scene, selected }) {
  const { camera, controls } = useThree();
  const goal = useRef(null);
  useEffect(() => {
    const b = scene.demo.find((d) => d.demo_id === selected);
    const s = scene.span;
    goal.current = b
      ? { target: new THREE.Vector3(b.center.x, 0, b.center.z), pos: new THREE.Vector3(b.center.x + 170, 230, b.center.z + 290) }
      : { target: new THREE.Vector3(0, 0, 0), pos: new THREE.Vector3(OVERVIEW[0] * s, OVERVIEW[1] * s, OVERVIEW[2] * s) };
  }, [selected, scene]);
  useEffect(() => {
    if (!controls) return;
    const stop = () => (goal.current = null);
    controls.addEventListener("start", stop);
    return () => controls.removeEventListener("start", stop);
  }, [controls]);
  useFrame((_, dt) => {
    if (!goal.current || !controls) return;
    const k = 1 - Math.exp(-dt * 3.5);
    camera.position.lerp(goal.current.pos, k);
    controls.target.lerp(goal.current.target, k);
    controls.update();
    if (camera.position.distanceTo(goal.current.pos) < 0.5) goal.current = null;
  });
  return null;
}

function Landmark({ b, colour, selected, label, onSelect }) {
  return (
    <group>
      <mesh
        geometry={b.geometry}
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        onPointerOver={() => (document.body.style.cursor = "pointer")}
        onPointerOut={() => (document.body.style.cursor = "")}
      >
        <meshStandardMaterial
          color={colour ?? "#8fe6c8"}
          roughness={0.55}
          emissive={selected ? "#1d8f73" : "#0e3d33"}
          emissiveIntensity={selected ? 0.7 : 0.35}
        />
      </mesh>
      <lineSegments geometry={b.edges} raycast={() => null}>
        <lineBasicMaterial color={selected ? "#68dfb9" : "#8fb5ad"} />
      </lineSegments>
      <Html position={[b.center.x, b.center.y + 6, b.center.z]} center zIndexRange={[10, 0]}>
        <div className={`tag ${selected ? "tag-on" : ""}`} onClick={onSelect}>
          <b>{SHORT[b.demo_id]}</b>
          {label && <span>{label}</span>}
        </div>
      </Html>
    </group>
  );
}

function Scene({ scene, byBuilding }) {
  const { state, dispatch } = useApp();
  const s = scene.span;
  return (
    <>
      <color attach="background" args={[BG]} />
      <fogExp2 attach="fog" args={[BG, 0.00023]} />
      <hemisphereLight args={["#b3e4e6", "#0c1720", 2.1]} />
      <directionalLight position={[-600, 900, 500]} intensity={3.2} color="#f3fffd" />
      <directionalLight position={[700, 400, -600]} intensity={1.5} color="#5dacae" />

      <gridHelper args={[s * 2.6, 34, "#1d3c42", "#12262d"]} position={[0, -PLINTH_M - 0.5, 0]} />
      <mesh geometry={scene.plinth} raycast={() => null}>
        <meshStandardMaterial color="#0d181c" roughness={0.9} side={THREE.DoubleSide} />
      </mesh>
      {/* everything OSM doesn't mark as green: paved yards, car parks, ground around buildings */}
      <mesh geometry={scene.plinthTop} raycast={() => null}>
        <meshStandardMaterial color="#3b4a47" roughness={0.95} />
      </mesh>
      <lineSegments geometry={scene.plinthEdge} raycast={() => null}>
        <lineBasicMaterial color="#49766e" transparent opacity={0.7} />
      </lineSegments>
      {scene.greens && (
        <mesh geometry={scene.greens} raycast={() => null}>
          <meshStandardMaterial color="#2a5a3f" roughness={1} />
        </mesh>
      )}
      {scene.lake && (
        <mesh geometry={scene.lake} raycast={() => null}>
          <meshStandardMaterial color="#0b4a4a" roughness={0.15} metalness={0.3} emissive="#0a3b3a" emissiveIntensity={0.6} />
        </mesh>
      )}
      <mesh geometry={scene.roads} raycast={() => null}>
        <meshStandardMaterial color="#59656a" roughness={0.95} side={THREE.DoubleSide} />
      </mesh>
      <mesh geometry={scene.paths} raycast={() => null}>
        <meshStandardMaterial color="#465551" roughness={0.95} side={THREE.DoubleSide} />
      </mesh>
      <Trees spots={scene.trees} />
      {scene.plain && (
        <>
          <mesh geometry={scene.plain} raycast={() => null}>
            <meshStandardMaterial color="#b8c7c5" roughness={0.82} />
          </mesh>
          <lineSegments geometry={scene.plainEdges} raycast={() => null}>
            <lineBasicMaterial color="#798f8e" transparent opacity={0.55} />
          </lineSegments>
        </>
      )}
      {scene.demo.map((b) => (
        <Landmark
          key={b.osm_id}
          b={b}
          selected={state.selected === b.demo_id}
          colour={byBuilding[b.demo_id]?.colour}
          label={byBuilding[b.demo_id] && value(byBuilding[b.demo_id].v, byBuilding[b.demo_id].unit)}
          onSelect={() => dispatch({ type: "select", id: b.demo_id })}
        />
      ))}

      <OrbitControls makeDefault enableDamping dampingFactor={0.08} maxPolarAngle={Math.PI / 2.25} minDistance={120} maxDistance={s * 2.4} />
      <CameraRig scene={scene} selected={state.selected} />
    </>
  );
}

export default function Campus3D() {
  const { state, dispatch } = useApp();
  const hour = useDataHour();
  const geo = useFetch(() => api.geojson(), []);
  const scene = useMemo(() => (geo.data ? buildScene(geo.data) : null), [geo.data]);

  const metric = state.colorBy ? HEADLINE[state.colorBy] : null;
  const colours = useFetch(
    () => (state.colorBy && hour ? api.campusNow(state.colorBy, state.scenarioId) : null),
    [state.colorBy, hour, state.scenarioId, state.version],
  );
  const byBuilding = useMemo(() => {
    if (!metric || !colours.data) return {};
    const vals = colours.data.map((r) => r.values[metric] ?? 0);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    return Object.fromEntries(
      colours.data.map((r) => {
        const v = r.values[metric] ?? 0;
        let t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
        if (metric === "recycling_rate") t = 1 - t; // a higher recycling rate is good
        return [r.building_id, { v, unit: r.units[metric], colour: LOW.clone().lerp(HIGH, t) }];
      }),
    );
  }, [colours.data, metric]);

  if (geo.error) return <div className="center-note">Can't load the campus map: {geo.error}</div>;

  return (
    <div className="campus">
      {scene && (
        <Canvas
          camera={{ position: OVERVIEW.map((k) => k * scene.span), fov: 38, near: 2, far: 12000 }}
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
          dpr={[1, 1.75]}
          onPointerMissed={() => state.selected && dispatch({ type: "select", id: null })}
        >
          <Scene scene={scene} byBuilding={byBuilding} />
        </Canvas>
      )}

      <div className="campus-bar">
        <label>
          Colour by
          <select value={state.colorBy ?? ""} onChange={(e) => dispatch({ type: "colorBy", system: e.target.value || null })}>
            <option value="">nothing</option>
            {SYSTEMS.map((s) => <option key={s} value={s}>{SYSTEM_LABEL[s]}</option>)}
          </select>
        </label>
        {metric && (
          <span className="legend">
            {LABEL[metric]} this hour{state.scenarioId ? " (with what-if)" : ""}:
            <i className="sw" style={{ background: metric === "recycling_rate" ? "#e5604d" : "#4fd1a5" }} /> low
            <i className="sw" style={{ background: metric === "recycling_rate" ? "#4fd1a5" : "#e5604d" }} /> high
          </span>
        )}
      </div>
      {!state.selected && <div className="campus-hint">Click a highlighted building · drag to rotate · scroll to zoom</div>}
    </div>
  );
}
