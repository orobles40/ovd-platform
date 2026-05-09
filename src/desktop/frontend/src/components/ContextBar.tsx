import { User, FolderOpen } from "lucide-react";

interface ContextBarProps {
  email: string;
  projectName: string;
  projectDir: string;
}

export function ContextBar({ email, projectName, projectDir }: ContextBarProps) {
  const shortDir =
    projectDir.length > 40 ? "…" + projectDir.slice(-38) : projectDir;

  return (
    <div className="flex items-center gap-6 px-4 py-2 text-xs border-b"
         style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
      <span className="flex items-center gap-1.5" style={{ color: "var(--ovd-muted)" }}>
        <User size={13} />
        <span style={{ color: "var(--ovd-text)" }}>{email}</span>
      </span>
      <span className="flex items-center gap-1.5" style={{ color: "var(--ovd-muted)" }}>
        <FolderOpen size={13} />
        <span style={{ color: "var(--ovd-text)" }} title={projectDir}>
          <strong>{projectName}</strong>
          <span className="ml-1.5" style={{ color: "var(--ovd-muted)" }}>{shortDir}</span>
        </span>
      </span>
    </div>
  );
}
