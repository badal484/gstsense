"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Factor {
  name: string;
  status: "good" | "warning" | "critical";
  description: string;
  points: string;
}

interface ComplianceScoreWidgetProps {
  score: number;
  grade: string;
  color: string;
  factors: Factor[];
  recommendations: string[];
  size?: "sm" | "md" | "lg";
  showDetails?: boolean;
}

function scoreToColor(score: number): string {
  if (score >= 90) return "#1D9E75";
  if (score >= 75) return "#639922";
  if (score >= 60) return "#BA7517";
  if (score >= 45) return "#D85A30";
  return "#E24B4A";
}

function FactorIcon({ status }: { status: Factor["status"] }) {
  if (status === "good")
    return <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />;
  if (status === "warning")
    return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />;
  return <X className="w-4 h-4 text-red-600 shrink-0" />;
}

function ScoreCircle({
  score,
  color,
  size,
}: {
  score: number;
  color: string;
  size: "sm" | "md" | "lg";
}) {
  const [displayed, setDisplayed] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    let start: number | null = null;
    const duration = 900;
    function animate(ts: number) {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(eased * score));
      if (progress < 1) raf.current = requestAnimationFrame(animate);
    }
    raf.current = requestAnimationFrame(animate);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [score]);

  const dim = size === "sm" ? 64 : size === "md" ? 96 : 140;
  const strokeW = size === "sm" ? 5 : size === "md" ? 7 : 10;
  const r = (dim - strokeW * 2) / 2;
  const circ = 2 * Math.PI * r;
  const filled = (displayed / 100) * circ;
  const textSize = size === "sm" ? "text-lg" : size === "md" ? "text-2xl" : "text-4xl";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={dim} height={dim} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={r}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth={strokeW}
        />
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ - filled}`}
          style={{ transition: "stroke-dasharray 0.1s linear" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("font-bold leading-none", textSize)} style={{ color }}>
          {displayed}
        </span>
      </div>
    </div>
  );
}

export function ComplianceScoreWidget({
  score,
  grade,
  color,
  factors,
  recommendations,
  size = "lg",
  showDetails = true,
}: ComplianceScoreWidgetProps) {
  const computedColor = scoreToColor(score);

  if (size === "sm") {
    return (
      <div className="inline-flex flex-col items-center gap-1">
        <ScoreCircle score={score} color={computedColor} size="sm" />
        <span className="text-xs font-semibold" style={{ color: computedColor }}>
          {grade}
        </span>
      </div>
    );
  }

  if (size === "md") {
    return (
      <div className="inline-flex flex-col items-center gap-2">
        <ScoreCircle score={score} color={computedColor} size="md" />
        <span className="text-sm font-bold" style={{ color: computedColor }}>
          Grade {grade}
        </span>
      </div>
    );
  }

  // Large
  return (
    <div className="space-y-5">
      <div className="flex flex-col items-center gap-2">
        <ScoreCircle score={score} color={computedColor} size="lg" />
        <div className="text-center">
          <span
            className="text-lg font-bold px-3 py-0.5 rounded-full"
            style={{ background: `${computedColor}20`, color: computedColor }}
          >
            Grade {grade}
          </span>
          <p className="text-xs text-gray-400 mt-1">Compliance Health Score</p>
        </div>
      </div>

      {showDetails && factors.length > 0 && (
        <div className="grid grid-cols-1 gap-2">
          {factors.map((f) => (
            <div
              key={f.name}
              className="flex items-start gap-2.5 bg-gray-50 rounded-xl px-3 py-2.5"
            >
              <FactorIcon status={f.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-gray-800">{f.name}</span>
                  <span
                    className={cn(
                      "text-xs font-bold shrink-0",
                      f.points.startsWith("+")
                        ? "text-green-600"
                        : f.points === "0"
                        ? "text-gray-400"
                        : "text-red-600"
                    )}
                  >
                    {f.points !== "0" ? f.points : ""}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{f.description}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {showDetails && recommendations.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
            Recommendations
          </p>
          {recommendations.map((r, i) => (
            <div key={i} className="flex gap-2 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800 leading-relaxed">{r}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
