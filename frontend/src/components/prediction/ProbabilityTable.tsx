// Probability table showing mineral class confidence values.
import type { MineralProbability } from "@/types/prediction";

type ProbabilityTableProps = {
  composition: MineralProbability[];
};

export const ProbabilityTable = ({ composition }: ProbabilityTableProps) => (
  <div className="overflow-hidden rounded-xl border border-space-border">
    <table className="w-full text-left text-sm">
      <thead className="bg-white/[0.04] text-xs uppercase tracking-[0.08em] text-slate-400">
        <tr>
          <th className="px-4 py-3">Mineral</th>
          <th className="px-4 py-3">Probability</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-space-border">
        {composition.map((item) => (
          <tr key={item.mineral}>
            <td className="px-4 py-3 text-slate-200">
              <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
              {item.mineral}
            </td>
            <td className="px-4 py-3 font-semibold text-white">{item.probability}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
