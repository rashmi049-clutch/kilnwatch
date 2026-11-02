"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase, ACTION_LABEL, type Edit } from "@/lib/supabase";
import { useMapData, BasemapPicker } from "./MapExplorer";
import type { Basemap, Pick } from "./MapView";

const MapView = dynamic(() => import("./MapView"), { ssr: false });
const LAYERS = { districts: false, rings: true, kilns: true, schools: true, stopped: true };
const IMAGERY = ["Esri World Imagery (latest)", "Esri Wayback (dated release)", "Google Earth history", "Google Maps listing / label", "Street-level photo", "Field visit"];

type Form = { feature: "kiln" | "school"; action: Edit["action"]; target_id: string; name: string;
              lat: number | null; lon: number | null; evidence: string; imagery: string; imagery_date: string };
const EMPTY: Form = { feature: "school", action: "add", target_id: "", name: "", lat: null, lon: null, evidence: "", imagery: IMAGERY[0], imagery_date: "" };

function Setup() {
  return (
    <div className="panel text-sm flex flex-col gap-2">
      <div className="h2">Editing is not connected yet</div>
      <p>Edits are saved in a Supabase database. To switch this on:</p>
      <ol className="list-decimal pl-5 flex flex-col gap-1">
        <li>Create a free project at supabase.com.</li>
        <li>In its SQL editor, run <code>dashboard/supabase/schema.sql</code>.</li>
        <li>Put the project URL and publishable (anon) key in <code>dashboard/.env.local</code> as
          <code> NEXT_PUBLIC_SUPABASE_URL</code> and <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code>, then rebuild.</li>
      </ol>
    </div>
  );
}

export default function EditWorkbench() {
  const { kilns, schools, districts, wayback } = useMapData();
  const [session, setSession] = useState<Session | null>(null);
  const [isEditor, setIsEditor] = useState<boolean | null>(null);
  const [editorName, setEditorName] = useState("");
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [basemap, setBasemap] = useState<Basemap>("satellite");
  const [form, setForm] = useState<Form>(EMPTY);
  const [pickTarget, setPickTarget] = useState(false);
  const [edits, setEdits] = useState<Edit[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  const loadEdits = useCallback(async () => {
    if (!supabase) return;
    const { data, error } = await supabase.from("edits").select("*").order("created_at", { ascending: false }).limit(500);
    if (!error && data) setEdits(data as Edit[]);
  }, []);

  useEffect(() => {
    if (!supabase || !session) { setIsEditor(null); return; }
    supabase.from("editors").select("name").eq("user_id", session.user.id).maybeSingle().then(({ data }) => {
      setIsEditor(!!data); setEditorName(data?.name || "");
      if (data) loadEdits();
    });
  }, [session, loadEdits]);

  const onPick = useCallback((p: Pick) => {
    setForm((f) => {
      if (p.kiln && (pickTarget || f.action !== "add"))
        return { ...f, feature: "kiln", target_id: String(p.kiln[0]), name: `Kiln #${p.kiln[0]}`, lat: f.action === "move" ? f.lat : p.lat, lon: f.action === "move" ? f.lon : p.lon };
      if (p.school && (pickTarget || f.action !== "add"))
        return { ...f, feature: "school", target_id: p.school.id, name: p.school.name, lat: f.action === "move" ? f.lat : p.lat, lon: f.action === "move" ? f.lon : p.lon };
      return { ...f, lat: p.lat, lon: p.lon };
    });
    setPickTarget(false);
  }, [pickTarget]);

  const extra = useMemo(() => [
    ...edits.filter((e) => e.lat && e.lon).map((e) => ({ lat: e.lat!, lon: e.lon!, label: `${ACTION_LABEL[e.action]}: ${e.name || e.target_id || e.feature} (${e.status})`, color: "#7c3aed" })),
    ...(form.lat && form.lon ? [{ lat: form.lat, lon: form.lon, label: "New edit position", color: "#16a34a" }] : []),
  ], [edits, form.lat, form.lon]);

  if (!supabase) return <Setup />;

  async function signIn(e: React.FormEvent) {
    e.preventDefault(); setMsg("");
    const { error } = await supabase!.auth.signInWithOtp({ email, options: { emailRedirectTo: window.location.href, shouldCreateUser: true } });
    setMsg(error ? `Could not send the link: ${error.message}` : "Check your email for a sign-in link, then come back here.");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setMsg("");
    if (form.action !== "note" && (form.lat === null || form.lon === null)) { setMsg("Click the map to set the position."); return; }
    if (form.action !== "add" && !form.target_id) { setMsg("Click the existing kiln or school this edit is about."); return; }
    if (form.evidence.trim().length < 10) { setMsg("Evidence must say what you saw and where (at least 10 characters)."); return; }
    setBusy(true);
    const { error } = await supabase!.from("edits").insert({
      editor_name: editorName, feature: form.feature, action: form.action, target_id: form.target_id || null,
      name: form.name || null, lat: form.lat, lon: form.lon, evidence: form.evidence.trim(),
      imagery: form.imagery, imagery_date: form.imagery_date || null });
    setBusy(false);
    if (error) { setMsg(`Not saved: ${error.message}`); return; }
    setMsg("Saved. It will be applied the next time the analysis is re-run."); setForm({ ...EMPTY, feature: form.feature }); loadEdits();
  }

  async function withdraw(id: number) {
    const { error } = await supabase!.from("edits").delete().eq("id", id);
    if (error) setMsg(`Could not withdraw: ${error.message}`); else loadEdits();
  }

  if (!session) return (
    <form onSubmit={signIn} className="panel flex max-w-md flex-col gap-3">
      <div className="h2">Sign in to edit</div>
      <p className="text-sm muted">Editing is limited to the project&apos;s analysts. You&apos;ll get a one-time sign-in link by email.</p>
      <input className="input" type="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
      <button className="btn btn-primary" type="submit">Send sign-in link</button>
      {msg && <p className="text-sm">{msg}</p>}
    </form>
  );

  if (isEditor === false) return (
    <div className="panel text-sm flex flex-col gap-2 max-w-xl">
      <div className="h2">Signed in, but not an editor</div>
      <p>Signed in as {session.user.email}. Add this account to the <code>editors</code> table (see the last lines of <code>dashboard/supabase/schema.sql</code>), then reload.</p>
      <button className="btn w-fit" onClick={() => supabase!.auth.signOut()}>Sign out</button>
    </div>
  );

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ position: "relative", height: "68vh", minHeight: 420 }}>
          <MapView kilns={kilns} schools={schools} districts={districts} wayback={wayback} basemap={basemap}
                   layers={LAYERS} extra={extra} onPick={onPick} />
        </div>
        <div className="p-3 flex flex-col gap-2">
          <BasemapPicker value={basemap} onChange={setBasemap} wayback={wayback} />
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] muted">
            {[["#7c3aed", "Saved edit (click for name)"], ["#16a34a", "Position being placed, not saved"],
              ["var(--kiln)", "Kiln"], ["var(--school-near)", "School within 800 m of a kiln"]].map(([c, l]) => (
              <span key={l}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 99, background: c, marginRight: 6 }} />{l}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <form onSubmit={submit} className="panel flex flex-col gap-3 text-sm">
          <div className="flex items-baseline justify-between"><div className="h2" style={{ marginBottom: 0 }}>New edit</div>
            <span className="muted text-[12px]">{editorName} · <button type="button" className="underline" onClick={() => supabase!.auth.signOut()}>sign out</button></span></div>
          <div className="flex gap-2">
            {(["school", "kiln"] as const).map((f) => <button key={f} type="button" className="btn" aria-pressed={form.feature === f} onClick={() => set("feature", f)}>{f === "school" ? "School" : "Kiln"}</button>)}
          </div>
          <select className="input" value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value as Edit["action"], target_id: "", name: "" })}>
            {Object.entries(ACTION_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <p className="muted text-[12px]">
            {form.action === "add" && "Click the map where the missing feature is (on its building or kiln)."}
            {form.action === "move" && "Click the existing feature to select it, then click its true position."}
            {form.action === "not_present" && "Click the existing feature that is not real."}
            {form.action === "note" && "Click the existing feature the note is about."}
          </p>
          {form.action === "move" && <button type="button" className="btn w-fit" aria-pressed={pickTarget} onClick={() => setPickTarget(true)}>
            {form.target_id ? "Re-select the feature" : "Select the feature to move"}</button>}
          {form.action !== "add" && <div>Feature: <b>{form.name || "none selected"}</b>{form.target_id && <span className="muted"> ({form.target_id})</span>}</div>}
          <div>Position: <b className="tabular-nums">{form.lat !== null ? `${form.lat}, ${form.lon}` : "not set"}</b></div>
          {form.action === "add" && <input className="input" placeholder={form.feature === "school" ? "School name as on its listing or sign" : "Name (optional)"} value={form.name} onChange={(e) => set("name", e.target.value)} />}
          <textarea className="input" rows={3} placeholder="Evidence: source and what it showed, e.g. Google listing 'Indraprastha Public School' (category School), not in UDISE; building identified on Esri imagery"
                    value={form.evidence} onChange={(e) => set("evidence", e.target.value)} />
          <div className="grid grid-cols-2 gap-2">
            <select className="input" value={form.imagery} onChange={(e) => set("imagery", e.target.value)} aria-label="Imagery or source used">
              {IMAGERY.map((i) => <option key={i}>{i}</option>)}
            </select>
            <input className="input" placeholder="Image date(s) seen" value={form.imagery_date} onChange={(e) => set("imagery_date", e.target.value)} />
          </div>
          <button className="btn btn-primary w-fit" type="submit" disabled={busy}>{busy ? "Saving…" : "Save edit"}</button>
          {msg && <p>{msg}</p>}
          <p className="note">Positions are placed by you on Esri imagery. Google listings may be cited as evidence that a school exists, but don&apos;t copy coordinates from Google.</p>
        </form>

        <div className="panel text-sm">
          <div className="h2">Edits ({edits.length})</div>
          <ul className="flex flex-col">
            {edits.map((e) => (
              <li key={e.id} className="py-2" style={{ borderBottom: "1px solid var(--line)" }}>
                <div><b>{ACTION_LABEL[e.action]}</b> · {e.feature} {e.name || e.target_id || ""} <span className="tag">{e.status}</span></div>
                <div className="muted text-[12px]">{e.evidence}</div>
                <div className="muted text-[12px]">{e.editor_name}, {new Date(e.created_at).toLocaleDateString("en-IN")} · {e.imagery}{e.imagery_date ? ` (${e.imagery_date})` : ""}
                  {e.status === "pending" && e.created_by === session.user.id && <> · <button className="underline" onClick={() => withdraw(e.id)}>withdraw</button></>}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
