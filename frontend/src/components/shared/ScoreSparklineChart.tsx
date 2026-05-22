"use client";

import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";

interface Point {
  date: string;
  score: number;
}

export default function ScoreSparklineChart({
  data,
  color,
}: {
  data: Point[];
  color: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="score"
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          formatter={(val) => [`${val}`, "Score"]}
          labelFormatter={(label) => String(label)}
          contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #e5e7eb" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
