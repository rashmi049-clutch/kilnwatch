import EditWorkbench from "@/components/EditWorkbench";

export const metadata = { title: "Edit · KilnWatch" };

export default function EditPage() {
  return (
    <main className="wrap flex flex-col gap-4" style={{ maxWidth: 1400 }}>
      <div>
        <h1 className="h1">Edit kilns and schools</h1>
        <p className="lead">For analysts: add a missing school or kiln, correct a location, or flag one that isn&apos;t real. Every edit carries your name,
          the evidence and the imagery used, and only changes the published numbers when the analysis is re-run.</p>
      </div>
      <EditWorkbench />
    </main>
  );
}
