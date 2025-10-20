import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Disclosure Comparison Tool",
  description: "Upload and compare statutory disclosure documents",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-background text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
