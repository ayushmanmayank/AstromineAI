// Recharts visualization for mineral probability distributions.
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { MineralProbability } from "@/types/prediction";

type MineralCompositionChartProps = {
  data: MineralProbability[];
};

export const MineralCompositionChart = ({ data }: MineralCompositionChartProps) => (
  <div className="h-80 w-full">
    <ResponsiveContainer>
      <PieChart>
        <Pie data={data} dataKey="probability" nameKey="mineral" innerRadius={70} outerRadius={110} paddingAngle={4}>
          {data.map((entry) => (
            <Cell key={entry.mineral} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [`${value}%`, "Probability"]}
          contentStyle={{
            background: "#111722",
            border: "1px solid rgba(148, 163, 184, 0.18)",
            borderRadius: 8,
            color: "#fff",
          }}
        />
        <Legend iconType="circle" wrapperStyle={{ color: "#CBD5E1", fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  </div>
);
