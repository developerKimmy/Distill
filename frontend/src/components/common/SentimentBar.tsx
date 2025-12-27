interface SentimentBarProps {
  score: number; // -1 to 1
  showLabels?: boolean;
}

export function SentimentBar({ score, showLabels = true }: SentimentBarProps) {
  const percentage = ((score + 1) / 2) * 100;

  return (
    <div className="mb-3 sm:mb-4">
      {showLabels && (
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>부정</span>
          <span>중립</span>
          <span>긍정</span>
        </div>
      )}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-red-400 via-yellow-400 to-green-400"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
