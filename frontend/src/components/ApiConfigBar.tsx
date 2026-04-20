import { useState } from "react";
import { Server, Check, Pencil } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { config, setApiUrl } from "@/config";

export function ApiConfigBar() {
  const [editing, setEditing] = useState(false);
  const [url, setUrl] = useState(config.apiUrl);

  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs">
      <Server className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-mono text-muted-foreground">API</span>
      {editing ? (
        <>
          <Input value={url} onChange={(e) => setUrl(e.target.value)}
            className="h-6 w-56 font-mono text-xs px-2" autoFocus />
          <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => setApiUrl(url)}>
            <Check className="h-3.5 w-3.5" />
          </Button>
        </>
      ) : (
        <>
          <span className="font-mono truncate max-w-[200px]">{config.apiUrl}</span>
          <button className="text-muted-foreground hover:text-foreground" onClick={() => setEditing(true)} aria-label="Изменить">
            <Pencil className="h-3 w-3" />
          </button>
        </>
      )}
    </div>
  );
}
