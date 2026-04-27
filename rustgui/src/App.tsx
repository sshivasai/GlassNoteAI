import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import Pill from "./components/Pill";
import AnswerOverlay from "./components/AnswerOverlay";
import SessionSetup from "./components/SessionSetup";
import SettingsWindow from "./components/SettingsWindow";

function App() {
  const [sessionActive, setSessionActive] = useState(false);
  const [showSetup, setShowSetup] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [llmResponse, setLlmResponse] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [queueCount, setQueueCount] = useState(0);

  useEffect(() => {
    // Listen for LLM token events
    const unlistenToken = listen<string>("llm-token", (event) => {
      setLlmResponse((prev) => prev + event.payload);
      setIsStreaming(true);
      setOverlayVisible(true);
    });

    // Listen for LLM done events
    const unlistenDone = listen<string>("llm-done", () => {
      setIsStreaming(false);
    });

    // Listen for LLM error events
    const unlistenError = listen<string>("llm-error", (event) => {
      setLlmResponse(`Error: ${event.payload}`);
      setIsStreaming(false);
      setOverlayVisible(true);
    });

    // Listen for transcript events
    const unlistenTranscript = listen<string>("transcript", (event) => {
      console.log("Transcript:", event.payload);
    });

    // Listen for hotkey events
    const unlistenHotkey = listen<string>("hotkey-triggered", (event) => {
      handleHotkey(event.payload);
    });

    // Listen for tray events
    const unlistenTrayNew = listen("tray-new-session", () => {
      setShowSetup(true);
    });

    const unlistenTraySettings = listen("tray-settings", () => {
      setShowSettings(true);
    });

    return () => {
      unlistenToken.then((fn) => fn());
      unlistenDone.then((fn) => fn());
      unlistenError.then((fn) => fn());
      unlistenTranscript.then((fn) => fn());
      unlistenHotkey.then((fn) => fn());
      unlistenTrayNew.then((fn) => fn());
      unlistenTraySettings.then((fn) => fn());
    };
  }, []);

  const handleHotkey = (action: string) => {
    console.log("Hotkey triggered:", action);

    switch (action) {
      case "capture":
        handleCapture();
        break;
      case "solve":
        handleSolve();
        break;
      case "analyze":
        handleAnalyze();
        break;
      case "interview":
        handleInterviewToggle();
        break;
      case "toggle_overlay":
        handleToggleOverlay();
        break;
      case "end_session":
        handleSessionEnd();
        break;
    }
  };

  const handleCapture = async () => {
    if (!sessionActive) return;

    try {
      await invoke("capture_screen");
      const count = await invoke<number>("get_queue_count");
      setQueueCount(count);
    } catch (error) {
      console.error("Capture failed:", error);
    }
  };

  const handleSolve = async () => {
    if (!sessionActive) return;

    try {
      await invoke("solve");
    } catch (error) {
      console.error("Solve failed:", error);
      setLlmResponse(`Error: ${error}`);
      setOverlayVisible(true);
    }
  };

  const handleAnalyze = async () => {
    if (!sessionActive) return;

    try {
      await invoke("analyze");
    } catch (error) {
      console.error("Analyze failed:", error);
    }
  };

  const handleInterviewToggle = async () => {
    if (!sessionActive) return;

    try {
      // Toggle interview mode
      await invoke("start_interview");
    } catch (error) {
      console.error("Interview failed:", error);
    }
  };

  const handleSessionStart = () => {
    setSessionActive(true);
    setShowSetup(false);
  };

  const handleSessionEnd = async () => {
    try {
      await invoke("end_session");
    } catch (error) {
      console.error("End session failed:", error);
    }

    setSessionActive(false);
    setLlmResponse("");
    setIsStreaming(false);
    setOverlayVisible(false);
    setQueueCount(0);
    setShowSetup(true);
  };

  const handleToggleOverlay = () => {
    setOverlayVisible(!overlayVisible);
  };

  return (
    <div className="app">
      {showSetup && (
        <SessionSetup
          onSessionStart={handleSessionStart}
          onOpenSettings={() => setShowSettings(true)}
        />
      )}

      {showSettings && (
        <SettingsWindow onClose={() => setShowSettings(false)} />
      )}

      {sessionActive && (
        <>
          <Pill
            isStreaming={isStreaming}
            queueCount={queueCount}
            onCapture={handleCapture}
            onSolve={handleSolve}
            onAnalyze={handleAnalyze}
            onInterview={handleInterviewToggle}
            onToggleOverlay={handleToggleOverlay}
            onEndSession={handleSessionEnd}
            onOpenSettings={() => setShowSettings(true)}
          />

          <AnswerOverlay
            visible={overlayVisible}
            content={llmResponse}
            isStreaming={isStreaming}
          />
        </>
      )}
    </div>
  );
}

export default App;
