"use client";

import { getScoreLabel } from "@/lib/utils";

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
}

function getScoreHex(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#84cc16";
  if (score >= 40) return "#eab308";
  if (score >= 20) return "#f97316";
  return "#ef4444";
}

export default function ScoreRing({
  score,
  size = 80,
  strokeWidth = 8,
  showLabel = true,
}: ScoreRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;
  const color = getScoreHex(score);
  const cx = size / 2;
  const cy = size / 2;

  const fontSize = size < 70 ? size * 0.22 : size * 0.20;
  const labelSize = size < 70 ? size * 0.12 : size * 0.11;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          {/* Track */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-muted/30"
          />
          {/* Progress */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.8s ease-in-out" }}
          />
        </svg>
        {/* Center text */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center"
          style={{ transform: "none" }}
        >
          <span
            className="font-display font-bold tabular-nums"
            style={{ fontSize, color, lineHeight: 1 }}
          >
            {Math.round(score)}
          </span>
        </div>
      </div>
      {showLabel && size >= 70 && (
        <span className="text-xs text-muted-foreground" style={{ fontSize: labelSize }}>
          {getScoreLabel(score)}
        </span>
      )}
    </div>
  );
}