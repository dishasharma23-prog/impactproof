"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { API } from "@/lib/api";

export default function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"IDLE" | "UPLOADING" | "PROCESSING" | "COMPLETED" | "FAILED" | "PARTIAL">("IDLE");
  const [errorMsg, setErrorMsg] = useState("");
  const router = useRouter();

  const handleUpload = async () => {
    if (!file) return;
    setStatus("UPLOADING");
    setErrorMsg("");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(`${API}/api/evidence/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      if (res.data.ai?.status === "FAILED") {
        setStatus("PARTIAL");
        setErrorMsg("Evidence saved. AI analysis unavailable.");
        setTimeout(() => router.push(`/evidence/${res.data.evidence_id}`), 2000);
      } else {
        setStatus("COMPLETED");
        router.push(`/evidence/${res.data.evidence_id}`);
      }
    } catch (err: any) {
      setStatus("FAILED");
      const msg = err.response?.data?.detail || err.message || "Upload failed";
      setErrorMsg(msg);
    }
  };

  return (
    <div className="bg-[#111] p-6 border border-gray-800 rounded-lg max-w-md">
      <h2 className="text-lg font-serif mb-4">Upload Evidence</h2>
      <input type="file" accept="image/jpeg, image/png, image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} className="block w-full text-sm text-gray-500 mb-4 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-[#d4af37] file:text-black hover:file:bg-white" />
      <button onClick={handleUpload} disabled={!file || status === 'UPLOADING'} className="w-full bg-[#378b99] text-white py-2 text-sm font-semibold hover:bg-[#2c717c] disabled:opacity-50">
        {status === 'IDLE' ? 'Check this photo' : status === 'UPLOADING' ? 'Checking…' : status === 'FAILED' ? 'Try again' : 'Done'}
      </button>
      {(status === 'FAILED' || status === 'PARTIAL') && <p className="text-amber-500 text-xs mt-2">{errorMsg}</p>}
    </div>
  );
}
