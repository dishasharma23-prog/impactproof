import type { Metadata } from "next";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/outfit";
import "@fontsource-variable/figtree";
import "@fontsource/dm-mono/400.css";
import "@fontsource/dm-mono/500.css";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ImpactProof · Evidence you can trace", template: "%s · ImpactProof" },
  description: "Offline-first field evidence for NGOs: volunteers capture and search proof with no signal (Qdrant Edge), every photo is verified, and donors fund work that is proven.",
  openGraph: {
    title: "ImpactProof · Evidence you can trace. Impact you can trust.",
    description: "Field proof that works with no signal, verified photo by photo, with donations released on proof.",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* apply the saved theme before the first paint, so there is no flash */}
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem("ip-theme");if(t)document.documentElement.dataset.theme=t}catch(e){}` }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
