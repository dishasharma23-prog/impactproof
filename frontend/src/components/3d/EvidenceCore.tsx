"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Sphere, MeshDistortMaterial, Float, Ring } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";

function CoreShape() {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.002;
      meshRef.current.rotation.x += 0.001;
    }
  });

  return (
    <Float speed={2} rotationIntensity={0.5} floatIntensity={1}>
      <Sphere ref={meshRef} args={[1, 64, 64]}>
        <MeshDistortMaterial 
          color="#a3b8c2" 
          envMapIntensity={1} 
          clearcoat={1} 
          clearcoatRoughness={0.1} 
          metalness={0.9} 
          roughness={0.1}
          distort={0.4}
          speed={2}
          transparent
          opacity={0.85}
        />
      </Sphere>
      <Ring args={[1.5, 1.52, 64]} rotation={[Math.PI / 2, 0, 0]}>
        <meshBasicMaterial color="#d4af37" transparent opacity={0.3} side={THREE.DoubleSide} />
      </Ring>
      <Ring args={[2, 2.02, 64]} rotation={[Math.PI / 3, Math.PI / 4, 0]}>
        <meshBasicMaterial color="#378b99" transparent opacity={0.2} side={THREE.DoubleSide} />
      </Ring>
    </Float>
  );
}

export default function EvidenceCore() {
  return (
    <div className="w-full h-full min-h-[500px]">
      <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1.5} color="#fff" />
        <directionalLight position={[-10, -10, -5]} intensity={0.5} color="#d4af37" />
        <CoreShape />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
      </Canvas>
    </div>
  );
}
