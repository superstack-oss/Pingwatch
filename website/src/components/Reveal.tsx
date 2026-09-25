import type { ReactNode } from "react";
import { useInView } from "../hooks/useInView";

export function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { ref, visible } = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${visible ? "reveal-in" : ""} ${className}`}>
      {children}
    </div>
  );
}
