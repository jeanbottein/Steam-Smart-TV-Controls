import { useEffect, useState } from "react";
import { isReachable } from "../api";

export function ReachabilityIndicator({ host }: { host: string }) {
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const ok = await isReachable(host);
        if (active) setOnline(ok);
      } catch {
        if (active) setOnline(false);
      }
    };
    setOnline(false);
    check();
    const timer = setInterval(check, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [host]);

  const color = online ? "#2ecc71" : "#e74c3c";
  const title = online ? "Reachable" : "Unreachable";
  return (
    <span
      title={title}
      style={{
        width: "10px",
        height: "10px",
        borderRadius: "50%",
        background: color,
        marginLeft: "8px",
        flexShrink: 0,
        display: "inline-block",
      }}
    />
  );
}
