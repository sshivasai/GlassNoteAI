import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Config {
  selected_provider?: string;
  anthropic_api_key?: string;
  anthropic_model?: string;
  openai_api_key?: string;
  openai_model?: string;
  deepgram_api_key?: string;
  stt_provider?: string;
  audio_source?: string;
}

interface SettingsWindowProps {
  onClose: () => void;
}

export default function SettingsWindow({ onClose }: SettingsWindowProps) {
  const [config, setConfig] = useState<Config>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const cfg = await invoke<Config>("load_config");
      setConfig(cfg);
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await invoke("save_config", { config });
      onClose();
    } catch (error) {
      console.error("Failed to save config:", error);
      alert(`Failed to save: ${error}`);
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (key: keyof Config, value: string) => {
    setConfig({ ...config, [key]: value });
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
        <div className="text-white">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-lg shadow-2xl w-[700px] max-h-[90vh] overflow-y-auto border border-gray-800">
        <div className="p-8">
          <h1 className="text-3xl font-bold text-white mb-6">Settings</h1>

          <div className="space-y-6">
            {/* LLM Provider */}
            <div>
              <h2 className="text-xl font-semibold text-white mb-3">
                LLM Provider
              </h2>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Provider
                  </label>
                  <select
                    value={config.selected_provider || "anthropic"}
                    onChange={(e) =>
                      updateConfig("selected_provider", e.target.value)
                    }
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  >
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="openai">OpenAI (GPT)</option>
                  </select>
                </div>

                {config.selected_provider === "anthropic" ? (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">
                        Anthropic API Key
                      </label>
                      <input
                        type="password"
                        value={config.anthropic_api_key || ""}
                        onChange={(e) =>
                          updateConfig("anthropic_api_key", e.target.value)
                        }
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                        placeholder="sk-ant-..."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">
                        Model
                      </label>
                      <select
                        value={
                          config.anthropic_model ||
                          "claude-sonnet-4-20250514"
                        }
                        onChange={(e) =>
                          updateConfig("anthropic_model", e.target.value)
                        }
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      >
                        <option value="claude-opus-4-20250514">
                          Claude Opus 4
                        </option>
                        <option value="claude-sonnet-4-20250514">
                          Claude Sonnet 4
                        </option>
                        <option value="claude-haiku-4-20250514">
                          Claude Haiku 4
                        </option>
                      </select>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">
                        OpenAI API Key
                      </label>
                      <input
                        type="password"
                        value={config.openai_api_key || ""}
                        onChange={(e) =>
                          updateConfig("openai_api_key", e.target.value)
                        }
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                        placeholder="sk-..."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">
                        Model
                      </label>
                      <select
                        value={config.openai_model || "gpt-4o"}
                        onChange={(e) =>
                          updateConfig("openai_model", e.target.value)
                        }
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      >
                        <option value="gpt-4o">GPT-4o</option>
                        <option value="gpt-4o-mini">GPT-4o Mini</option>
                        <option value="gpt-4-turbo">GPT-4 Turbo</option>
                      </select>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* STT Provider */}
            <div>
              <h2 className="text-xl font-semibold text-white mb-3">
                Speech-to-Text
              </h2>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Provider
                  </label>
                  <select
                    value={config.stt_provider || "deepgram"}
                    onChange={(e) =>
                      updateConfig("stt_provider", e.target.value)
                    }
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  >
                    <option value="deepgram">Deepgram</option>
                    <option value="openai_realtime">OpenAI Realtime</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Deepgram API Key
                  </label>
                  <input
                    type="password"
                    value={config.deepgram_api_key || ""}
                    onChange={(e) =>
                      updateConfig("deepgram_api_key", e.target.value)
                    }
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                    placeholder="Your Deepgram API key"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Audio Source
                  </label>
                  <select
                    value={config.audio_source || "system"}
                    onChange={(e) =>
                      updateConfig("audio_source", e.target.value)
                    }
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  >
                    <option value="system">System (WASAPI Loopback)</option>
                    <option value="microphone">Microphone</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-3 mt-8">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>

            <button
              onClick={onClose}
              className="px-6 py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
