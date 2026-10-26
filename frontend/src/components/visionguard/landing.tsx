import { useEffect, useState } from "react";

export function Landing() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        overflow: "hidden",
        backgroundColor: "#06181d",
        zIndex: 50,
      }}
    >
      {mounted ? (
        <iframe
          src="/portholevoyage/index.html"
          title="VisionGuard AI — Model Reliability Voyage"
          style={{
            width: "100%",
            height: "100%",
            border: "none",
            display: "block",
          }}
          allow="accelerometer; autoplay; encrypted-media; gyroscope"
        />
      ) : (
        <div
          style={{
            position: "fixed",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#06181d",
            color: "#f4ecdd",
            fontFamily: "system-ui, sans-serif",
            fontSize: "14px",
            letterSpacing: "0.1em",
          }}
        >
          PREPARING VOYAGE...
        </div>
      )}
    </div>
  );
}
