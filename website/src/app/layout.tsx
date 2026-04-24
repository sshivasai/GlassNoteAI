import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { AuthModal } from "@/components/auth/auth-modal";

export const metadata: Metadata = {
  title: "GlassNote — AI-Powered Meeting Assistant",
  description: "GlassNote is an invisible AI meeting companion that listens to your conversation, captures your screen, and provides real-time answers through a transparent overlay. Powered by Claude & GPT.",
  keywords: "AI meeting assistant, meeting prep, real-time AI, coding meeting, GlassNote",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          {children}
          <AuthModal />
        </AuthProvider>
      </body>
    </html>
  );
}
