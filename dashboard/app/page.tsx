import summaryJson from "@/public/data/summary.json";
import type { Summary } from "@/lib/data";
import DashboardApp from "@/components/DashboardApp";

export default function Home() {
  return <DashboardApp summary={summaryJson as unknown as Summary} />;
}
