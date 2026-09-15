import type { ProspectiveRecord } from "@/lib/prospective";
import { formatTime, percent } from "@/lib/market";
export default function AuditTable({
  records,
  total,
}: {
  records: ProspectiveRecord[];
  total: number;
}) {
  return (
    <details className="mt-5 rounded-lg bg-[#111722] p-4">
      <summary className="cursor-pointer text-sm text-slate-300">
        Evaluation &amp; audit trail{" "}
        <span className="ml-2 text-xs text-slate-500">{total} records</span>
      </summary>
      <div className="mt-4 max-w-full overflow-x-auto">
        <table className="w-full min-w-[620px] text-left text-xs">
          <caption className="sr-only">
            Saved prospective probabilities and outcome evidence
          </caption>
          <thead className="text-slate-500">
            <tr>
              {[
                "Match / forecast",
                "Model / version",
                "Saved probability",
                "Lock time (Eastern)",
                "Result / evidence",
              ].map((h) => (
                <th key={h} scope="col" className="p-2 font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr
                key={r.forecast_id}
                className="border-t border-slate-800 text-slate-400"
              >
                <td className="p-2">
                  #{r.match_id} / #{r.forecast_id}
                </td>
                <td className="p-2 break-all font-mono text-[10px]">
                  {r.source_key}
                </td>
                <td className="p-2 font-mono">{percent(r.probability)}</td>
                <td className="whitespace-nowrap p-2">
                  {formatTime(r.lock_time)}
                </td>
                <td className="p-2">
                  {r.team1_score !== undefined
                    ? `${r.team1_score}–${r.team2_score} · `
                    : ""}
                  {r.status.toLowerCase().replaceAll("_", " ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Latest {records.length} of {total} records. Saved probabilities are
        never replaced by current previews.
      </p>
    </details>
  );
}
