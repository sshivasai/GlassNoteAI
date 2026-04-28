import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface SessionSetupProps {
  onSessionStart: () => void;
  onOpenSettings: () => void;
}

export default function SessionSetup({
  onSessionStart,
  onOpenSettings,
}: SessionSetupProps) {
  const [company, setCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [extraInstructions, setExtraInstructions] = useState("");
  const [language, setLanguage] = useState("English");
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    if (!company || !jobDescription) {
      alert("Please fill in company and job description");
      return;
    }

    setLoading(true);

    try {
      await invoke("start_session", {
        sessionData: {
          company,
          job_description: jobDescription,
          resume_text: resumeText,
          extra_instructions: extraInstructions,
          language,
        },
      });

      onSessionStart();
    } catch (error) {
      console.error("Session start failed:", error);
      alert(`Failed to start session: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-lg shadow-2xl w-[600px] max-h-[90vh] overflow-y-auto border border-gray-800">
        <div className="p-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Start New Session
          </h1>
          <p className="text-gray-400 mb-6">
            Configure your interview assistant
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Company Name *
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="e.g., Google, Microsoft"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Job Description *
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Paste job description or key requirements"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Resume / Background
              </label>
              <textarea
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Paste your resume text or key skills"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Extra Instructions
              </label>
              <textarea
                value={extraInstructions}
                onChange={(e) => setExtraInstructions(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Any specific guidance for the AI"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Response Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option>English</option>
                <option>Spanish</option>
                <option>French</option>
                <option>German</option>
                <option>Chinese</option>
                <option>Japanese</option>
              </select>
            </div>
          </div>

          <div className="flex gap-3 mt-8">
            <button
              onClick={handleStart}
              disabled={loading}
              className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium disabled:opacity-50"
            >
              {loading ? "Starting..." : "Start Session"}
            </button>

            <button
              onClick={onOpenSettings}
              className="px-6 py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition"
            >
              Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
