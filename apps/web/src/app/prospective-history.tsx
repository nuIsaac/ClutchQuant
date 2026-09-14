import { loadProspective } from "@/lib/prospective";
import { modelLabel } from "@/lib/upcoming";

export default async function ProspectiveHistory({ apiUrl }: { apiUrl: string }) {
  const report = await loadProspective(apiUrl);
  return <section className="border-t border-zinc-800 py-8" aria-labelledby="history-heading">
    <h2 id="history-heading" className="text-2xl font-semibold">Recorded prediction history</h2>
    <p className="mt-2 text-sm text-zinc-400">Prospective scores use actual frozen forecasts and observed outcomes. Legacy diagnostics and historical replay experiments are excluded.</p>
    {!report ? <p role="alert" className="mt-4 text-amber-400">Prediction history is temporarily unavailable.</p> : <>
      <p className="mt-4 text-xs text-zinc-400">Pipeline: {report.last_run_status} · Report as of {report.as_of ?? "not yet generated"}</p>
      {Object.entries(report.models).map(([source, model]) => <div key={source} className="mt-4 rounded border border-zinc-800 p-4 text-sm">
        <p>{modelLabel(source)} · {model.count} verified outcomes</p>
        <p className="mt-1 text-zinc-400">Accuracy {(model.accuracy * 100).toFixed(1)}% · Brier {model.brier.toFixed(3)} · Log loss {model.log_loss.toFixed(3)}</p>
        <p className="mt-1 text-xs text-zinc-500">Calibration: {model.calibration_status.toLowerCase().replaceAll("_", " ")} · Descriptive results; no superiority claim.</p>
      </div>)}
      {Object.keys(report.models).length === 0 && <p className="mt-4 text-zinc-400">No verified prospective outcomes yet. Performance metrics will appear after frozen forecasts resolve.</p>}
      {report.records.length > 0 && <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-xs">
        <thead className="text-zinc-500"><tr><th className="p-2">Match / forecast</th><th>Model</th><th>Saved team 1 probability</th><th>Lock time (UTC)</th><th>Result / evidence</th></tr></thead>
        <tbody>{report.records.map(row => <tr key={row.forecast_id} className="border-t border-zinc-800">
          <td className="p-2">#{row.match_id} / #{row.forecast_id}</td><td>{modelLabel(row.source_key)}</td>
          <td>{(row.probability * 100).toFixed(1)}%</td><td>{row.lock_time}</td>
          <td>{row.team1_score !== undefined ? `${row.team1_score}–${row.team2_score} · ` : ""}{row.status.toLowerCase().replaceAll("_", " ")}</td>
        </tr>)}</tbody>
      </table><p className="mt-2 text-zinc-500">Showing latest {report.records.length} of {report.total} records. API supports pagination.</p></div>}
    </>}
  </section>;
}
