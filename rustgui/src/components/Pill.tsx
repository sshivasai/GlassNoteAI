import { Camera, Mic, Settings, X } from "lucide-react";

interface PillProps {
  isStreaming: boolean;
  queueCount: number;
  onCapture: () => void;
  onSolve: () => void;
  onAnalyze: () => void;
  onInterview: () => void;
  onToggleOverlay: () => void;
  onEndSession: () => void;
  onOpenSettings: () => void;
}

export default function Pill({
  isStreaming,
  queueCount,
  onCapture,
  onSolve,
  onAnalyze,
  onInterview,
  onToggleOverlay,
  onEndSession,
  onOpenSettings,
}: PillProps) {
  return (
    <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50">
      <div className="bg-pill-bg backdrop-blur-sm rounded-full px-4 py-2 shadow-2xl border border-gray-800">
        <div className="flex items-center gap-3">
          {/* Status Indicator */}
          <div
            className={`w-2 h-2 rounded-full ${
              isStreaming ? "bg-green-500 animate-pulse" : "bg-gray-600"
            }`}
          />

          {/* Capture */}
          <button
            onClick={onCapture}
            className="p-2 hover:bg-gray-800 rounded-full transition relative"
            title="Capture Screenshot (Ctrl+Shift+C)"
          >
            <Camera size={18} className="text-pill-text" />
            {queueCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-green-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                {queueCount}
              </span>
            )}
          </button>

          {/* Solve */}
          <button
            onClick={onSolve}
            className="px-3 py-1 bg-pill-accent text-white rounded-full hover:bg-green-600 transition text-sm font-medium"
            title="Solve (Ctrl+Shift+S)"
          >
            Solve
          </button>

          {/* Analyze */}
          <button
            onClick={onAnalyze}
            className="px-3 py-1 bg-blue-600 text-white rounded-full hover:bg-blue-700 transition text-sm font-medium"
            title="Analyze (Ctrl+Shift+A)"
          >
            Analyze
          </button>

          {/* Interview */}
          <button
            onClick={onInterview}
            className="p-2 hover:bg-gray-800 rounded-full transition"
            title="Interview Mode (Ctrl+Shift+I)"
          >
            <Mic size={18} className="text-pill-text" />
          </button>

          {/* Settings */}
          <button
            onClick={onOpenSettings}
            className="p-2 hover:bg-gray-800 rounded-full transition"
            title="Settings"
          >
            <Settings size={18} className="text-pill-text" />
          </button>

          {/* Toggle Overlay */}
          <button
            onClick={onToggleOverlay}
            className="px-2 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 transition text-xs"
            title="Toggle Overlay (Ctrl+Shift+O)"
          >
            Hide
          </button>

          {/* End Session */}
          <button
            onClick={onEndSession}
            className="p-2 hover:bg-red-800 rounded-full transition"
            title="End Session (Ctrl+Shift+E)"
          >
            <X size={18} className="text-red-400" />
          </button>
        </div>
      </div>

      {/* Hotkey hints */}
      <div className="mt-2 text-center">
        <div className="text-xs text-gray-500 bg-black bg-opacity-50 px-3 py-1 rounded-full inline-block">
          Ctrl+Shift+C/S/A/I/O/E
        </div>
      </div>
    </div>
  );
}
