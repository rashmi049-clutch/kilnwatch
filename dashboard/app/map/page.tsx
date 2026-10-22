import { Suspense } from "react";
import MapExplorer from "@/components/MapExplorer";

export const metadata = { title: "Map · KilnWatch" };

export default function MapPage() {
  return (
    <Suspense fallback={<div className="wrap muted">Loading map…</div>}>
      <MapExplorer />
    </Suspense>
  );
}
