import AppShell from "@/components/AppShell";
import { ProjectProvider } from "@/lib/project";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProjectProvider>
      <AppShell>{children}</AppShell>
    </ProjectProvider>
  );
}
