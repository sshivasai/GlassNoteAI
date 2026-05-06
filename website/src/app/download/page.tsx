"use client";
import { useEffect } from "react";
import { Logo } from "@/components/logo";

const DOWNLOAD_URL =
  "https://storage.googleapis.com/glassnote-downloads/GlassNote_Setup_v1.0.0.exe";

export default function DownloadPage() {
  useEffect(() => {
    const timer = setTimeout(() => {
      window.location.href = DOWNLOAD_URL;
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      style={{
        background: "#0d0d10",
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Segoe UI', Arial, sans-serif",
      }}
    >
      <div style={{ textAlign: "center", padding: "40px" }}>
        <Logo />
        <h1
          style={{ color: "#e0e0e8", fontSize: "24px", marginTop: "24px" }}
        >
          Your download is starting...
        </h1>
        <p style={{ color: "#888", fontSize: "14px", marginTop: "12px" }}>
          If it doesn&apos;t start automatically,{" "}
          <a href={DOWNLOAD_URL} style={{ color: "#5b8ff9" }}>
            click here to download
          </a>
          .
        </p>
        <p style={{ color: "#555", fontSize: "12px", marginTop: "8px" }}>
          GlassNote v1.0.0 for Windows
        </p>
      </div>
    </div>
  );
}
