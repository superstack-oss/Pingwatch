const styles: Record<string, string> = {
  Up: "text-up",
  Down: "text-down",
  Warning: "text-warn",
  Unknown: "text-unknown",
  Paused: "text-blue-600 dark:text-blue-400",
};

export function StatusPill({ status, live = false }: { status: string; live?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-1 text-[0.78rem] dark:border-[#30363d] dark:bg-[#161b22]">
      <i
        className={`inline-block h-2 w-2 rounded-full ${live ? "status-live" : ""} ${
          status === "Up"
            ? "bg-up"
            : status === "Down"
              ? "bg-down"
              : status === "Warning"
                ? "bg-warn"
                : status === "Paused"
                  ? "bg-blue-600"
                  : "bg-unknown"
        }`}
      />
      <span className={styles[status] ?? ""}>{status}</span>
    </span>
  );
}
