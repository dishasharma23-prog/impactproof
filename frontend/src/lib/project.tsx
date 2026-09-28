"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, Project } from "./api";

interface Ctx {
  projects: Project[];
  project: Project | null;
  setProjectId: (id: number) => void;
  reload: () => Promise<void>;
  error: string;
}

const ProjectContext = createContext<Ctx>({
  projects: [],
  project: null,
  setProjectId: () => {},
  reload: async () => {},
  error: "",
});

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      const list = await api<Project[]>("/api/projects");
      setProjects(list);
      setError("");
      let saved: number | null = null;
      try {
        saved = Number(localStorage.getItem("ip.project")) || null;
      } catch {}
      setId((cur) => {
        const want = cur ?? saved;
        return list.some((p) => p.id === want) ? want : list[0]?.id ?? null;
      });
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const setProjectId = (id: number) => {
    setId(id);
    try {
      localStorage.setItem("ip.project", String(id));
    } catch {}
  };

  const project = projects.find((p) => p.id === projectId) || null;
  return (
    <ProjectContext.Provider value={{ projects, project, setProjectId, reload, error }}>
      {children}
    </ProjectContext.Provider>
  );
}

export const useProject = () => useContext(ProjectContext);
