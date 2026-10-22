import SchoolSearch from "@/components/SchoolSearch";

export const metadata = { title: "Find a school · KilnWatch" };

export default function SchoolsPage() {
  return (
    <main className="wrap flex flex-col gap-4">
      <div>
        <h1 className="h1">Find a school</h1>
        <p className="lead">Search any of the ~29,000 location-checked schools in the NCR outside Delhi and see the firing brick kilns around it.</p>
      </div>
      <SchoolSearch />
    </main>
  );
}
