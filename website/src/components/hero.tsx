"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Mic, Monitor, Cpu, Activity, Bot, EyeOff } from "lucide-react";
import { DOWNLOAD_URL } from "@/lib/config";

type Tab = 'stt' | 'screen' | 'model' | 'perf' | 'stealth';

export function Hero() {
  const [activeTab, setActiveTab] = useState<Tab>('stt');

  return (
    <section className="relative min-h-screen flex items-center justify-center pt-20 pb-20 px-4 overflow-hidden perspective-1000">
      {/* Background glow and floating particles */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[var(--cyan)] rounded-full mix-blend-screen opacity-20 animate-glow-pulse" />
        <div className="absolute top-1/2 right-1/4 w-[500px] h-[500px] bg-[var(--lime)] rounded-full mix-blend-screen opacity-10 animate-glow-pulse" style={{ animationDelay: '2s' }} />

        {/* Floating particles */}
        <div className="absolute top-1/4 left-1/4 w-4 h-4 bg-[var(--cyan)] rounded-full blur-sm opacity-50 animate-float" style={{ animationDelay: '0s' }} />
        <div className="absolute bottom-1/3 right-1/3 w-6 h-6 bg-[var(--lime)] rounded-full blur-md opacity-30 animate-float" style={{ animationDelay: '2s' }} />
        <div className="absolute top-1/2 left-1/3 w-3 h-3 bg-white rounded-full blur-[2px] opacity-40 animate-float" style={{ animationDelay: '4s' }} />
      </div>

      <div className="max-w-4xl mx-auto text-center z-10">
        <div className="mb-8 animate-fade-in">
          <Badge className="bg-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.12)] text-white border border-[rgba(255,255,255,0.2)] px-4 py-1.5 backdrop-blur-md shadow-[0_0_20px_rgba(255,255,255,0.05)] transition-all">
            ✨ Powered by Claude, GPT & OpenRouter
          </Badge>
        </div>

        {/* Main heading */}
        <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight tracking-tighter animate-fade-in text-glow" style={{ animationDelay: "0.1s" }}>
          Speak Confidently in
          <br />
          <span className="bg-gradient-to-r from-[var(--cyan)] via-[var(--lime)] to-[var(--cyan)] bg-clip-text text-transparent">
            Every Meeting
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-xl text-[var(--text-secondary)] max-w-2xl mx-auto mb-8 leading-relaxed animate-fade-in" style={{ animationDelay: "0.2s" }}>
          Real-time AI assistance that helps you communicate clearly and confidently. Get instant answers through a transparent overlay that only you can see.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16 animate-fade-in" style={{ animationDelay: "0.3s" }}>
          <a href={DOWNLOAD_URL} target="_blank" rel="noopener noreferrer">
            <Button
              size="lg"
              className="bg-[var(--cyan)] text-white hover:opacity-90 font-semibold px-8 h-12 flex items-center gap-2 shadow-[0_0_20px_var(--cyan-dim)] transition-transform duration-300 hover:scale-105"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.951-1.801" />
              </svg>
              Download for Windows
            </Button>
          </a>
          <Button
            size="lg"
            variant="outline"
            onClick={() => { document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' }); }}
            className="border-[var(--border)] text-white hover:bg-[var(--cyan-dim)] font-semibold px-8 h-12 glass-panel transition-transform duration-300 hover:scale-105"
          >
            See How It Works →
          </Button>
        </div>

        {/* Animated 3D Mockup */}
        <div className="relative max-w-3xl mx-auto mb-16 animate-fade-in" style={{ animationDelay: "0.4s" }}>
          <div className="animate-float-tilt glass-panel rounded-xl overflow-hidden shadow-2xl border border-[var(--border-glow)]">
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[rgba(0,0,0,0.3)]">
              <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.5)]" />
              <div className="w-3 h-3 rounded-full bg-yellow-500 shadow-[0_0_5px_rgba(234,179,8,0.5)]" />
              <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_5px_rgba(34,197,94,0.5)]" />
              <span className="text-xs text-[var(--text-muted)] ml-auto font-mono">GlassNote — Active Meeting</span>
            </div>

            {/* Content */}
            <div className="flex h-80">
              {/* Sidebar */}
              <div className="w-44 border-r border-[var(--border)] bg-[rgba(0,0,0,0.2)] p-3 flex flex-col gap-2">
                <button
                  onClick={() => setActiveTab('stt')}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono transition-colors w-full text-left ${activeTab === 'stt' ? 'bg-[var(--cyan-dim)] text-[var(--cyan)] shadow-[inset_0_0_10px_rgba(0,217,255,0.1)]' : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'}`}
                >
                  <Mic className="w-4 h-4" /> Listening...
                </button>
                <button
                  onClick={() => setActiveTab('screen')}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-colors w-full text-left ${activeTab === 'screen' ? 'bg-[var(--cyan-dim)] text-[var(--cyan)] shadow-[inset_0_0_10px_rgba(0,217,255,0.1)]' : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'}`}
                >
                  <div className="flex items-center gap-2"><Monitor className="w-4 h-4" /> Screen</div>
                  {activeTab !== 'screen' && <span className="text-[var(--lime)] font-bold">Active</span>}
                </button>
                <button
                  onClick={() => setActiveTab('model')}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-colors w-full text-left ${activeTab === 'model' ? 'bg-[var(--cyan-dim)] text-[var(--cyan)] shadow-[inset_0_0_10px_rgba(0,217,255,0.1)]' : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'}`}
                >
                  <div className="flex items-center gap-2"><Cpu className="w-4 h-4" /> Model</div>
                  {activeTab !== 'model' && <span className="text-white">Sonnet</span>}
                </button>
                <button
                  onClick={() => setActiveTab('perf')}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-colors w-full text-left ${activeTab === 'perf' ? 'bg-[var(--cyan-dim)] text-[var(--cyan)] shadow-[inset_0_0_10px_rgba(0,217,255,0.1)]' : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'}`}
                >
                  <div className="flex items-center gap-2"><Activity className="w-4 h-4" /> Perf</div>
                  {activeTab !== 'perf' && <span className="text-[var(--cyan)]">187ms</span>}
                </button>
                <button
                  onClick={() => setActiveTab('stealth')}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-colors w-full text-left mt-auto ${activeTab === 'stealth' ? 'bg-[var(--cyan-dim)] text-[var(--cyan)] shadow-[inset_0_0_10px_rgba(0,217,255,0.1)]' : 'text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)]'}`}
                >
                  <div className="flex items-center gap-2"><EyeOff className="w-4 h-4" /> Stealth</div>
                  {activeTab !== 'stealth' && <span className="text-[var(--lime)]">ON</span>}
                </button>
              </div>

              {/* Main content */}
              {activeTab === 'stt' && (
                <div className="flex-1 p-4 flex flex-col gap-3 text-left">
                  <div className="bg-[rgba(0,0,0,0.3)] border border-[var(--border)] rounded-lg p-3">
                    <div className="text-xs font-bold text-[var(--text-muted)] mb-2 tracking-widest">SPEAKER</div>
                    <div className="text-sm text-[var(--text-secondary)] font-mono">Design a rate limiter for a distributed API gateway...</div>
                  </div>
                  <div className="bg-[rgba(0,217,255,0.05)] border border-[rgba(0,217,255,0.15)] rounded-lg p-3 flex-1 relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-50" />
                    <div className="text-xs font-bold text-[var(--cyan)] mb-3 tracking-widest flex items-center gap-2">
                      <Bot className="w-4 h-4" /> AI ANSWER
                      <span className="inline-block w-2 h-2 rounded-full bg-[var(--cyan)] animate-pulse shadow-[0_0_8px_var(--cyan)]" />
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] font-mono space-y-1">
                      <p>Use a <span className="text-[var(--text-primary)]">token bucket algorithm</span> with Redis:</p>
                      <p className="text-[var(--cyan)]">1. Each user gets a bucket with N tokens/second</p>
                      <p className="text-[var(--cyan)]">2. Redis EVAL + Lua script for atomic ops</p>
                      <p className="text-[var(--lime)] mt-2">TTFT: 187ms • Claude Sonnet</p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'screen' && (
                <div className="flex-1 p-4 flex flex-col gap-3 text-left">
                  <div className="bg-[rgba(0,0,0,0.3)] border border-[var(--border)] rounded-lg p-3 relative h-32 overflow-hidden flex items-center justify-center">
                    <img src="/leetcode.png" alt="Leetcode Capture" className="absolute inset-0 w-full h-full object-cover opacity-80 mix-blend-screen" />
                    <div className="absolute top-2 left-2 text-[10px] font-bold text-white bg-black/60 px-2 py-1 rounded backdrop-blur-sm border border-white/10 shadow-lg">
                      <span className="text-[var(--lime)] animate-pulse">●</span>SCREEN CAPTURED
                    </div>
                  </div>
                  <div className="bg-[rgba(0,217,255,0.05)] border border-[rgba(0,217,255,0.15)] rounded-lg p-3 flex-1 overflow-auto">
                    <div className="text-xs font-bold text-[var(--cyan)] mb-2 tracking-widest flex items-center gap-2">
                      <Bot className="w-4 h-4" /> AI SOLUTION
                    </div>
                    <div className="text-[11px] text-[var(--text-secondary)] font-mono space-y-1">
                      <p className="text-pink-400">def <span className="text-blue-300">sumSubseqWidths</span>(nums):</p>
                      <p className="pl-4 text-orange-300">MOD = 10**9 + 7</p>
                      <p className="pl-4 text-white">nums.sort()</p>
                      <p className="pl-4 text-white">res, n = 0, len(nums)</p>
                      <p className="pl-4 text-pink-400">for <span className="text-white">i</span> in <span className="text-blue-300">range</span>(n):</p>
                      <p className="pl-8 text-white">res += nums[i] * (pow(2, i, MOD) - pow(2, n - 1 - i, MOD))</p>
                      <p className="pl-4 text-pink-400">return <span className="text-white">res % MOD</span></p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'model' && (
                <div className="flex-1 p-4 flex flex-col gap-3 text-left">
                  <div className="bg-[rgba(0,0,0,0.3)] border border-[var(--border)] rounded-lg p-3 flex-1 overflow-auto">
                    <div className="text-xs font-bold text-[var(--text-muted)] mb-2 tracking-widest">LLMs (REASONING)</div>
                    <div className="grid grid-cols-2 gap-2 mb-4">
                      <div className="flex items-center gap-2 p-2 rounded bg-white/5 border border-white/5 hover:border-[var(--cyan)] transition-colors cursor-pointer">
                        <div className="w-6 h-6 rounded flex items-center justify-center overflow-hidden bg-white p-0.5">
                          <img src="/openai.png" alt="OpenAI" className="w-full h-full object-contain" />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold text-white">OpenAI</div>
                          <div className="text-[9px] text-[var(--text-muted)]">GPT-4o, o1, o3</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 rounded bg-[var(--cyan-dim)] border border-[var(--cyan)] transition-colors cursor-pointer">
                        <div className="w-6 h-6 rounded flex items-center justify-center overflow-hidden bg-white p-0.5">
                          <img src="/anthropic.png" alt="Anthropic" className="w-full h-full object-contain" />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold text-white">Anthropic</div>
                          <div className="text-[9px] text-[var(--cyan)]">Sonnet, Opus, etc</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 rounded bg-white/5 border border-white/5 hover:border-[var(--lime)] transition-colors cursor-pointer col-span-2">
                        <div className="w-6 h-6 rounded flex items-center justify-center overflow-hidden bg-black border border-white/10 text-[8px] font-bold text-[var(--lime)] shrink-0">OR</div>
                        <div>
                          <div className="text-[10px] font-bold text-white">OpenRouter</div>
                          <div className="text-[9px] text-[var(--lime)]">100+ models • Free tier available</div>
                        </div>
                      </div>
                    </div>

                    <div className="text-xs font-bold text-[var(--text-muted)] mb-2 tracking-widest">STT (TRANSCRIPTION)</div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="flex items-center gap-2 p-2 rounded bg-[var(--cyan-dim)] border border-[var(--cyan)] transition-colors cursor-pointer">
                        <div className="w-6 h-6 rounded flex items-center justify-center overflow-hidden bg-black border border-white/20">
                          <img src="https://avatars.githubusercontent.com/u/16142100?s=200&v=4" alt="Deepgram" className="w-full h-full object-contain" />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold text-white">Deepgram</div>
                          <div className="text-[9px] text-[var(--cyan)]">Nova-3/2, Flux</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 rounded bg-white/5 border border-white/5 hover:border-[var(--cyan)] transition-colors cursor-pointer">
                        <div className="w-6 h-6 rounded flex items-center justify-center overflow-hidden bg-white p-0.5">
                          <img src="/openai.png" alt="OpenAI" className="w-full h-full object-contain" />
                        </div>
                        <div>
                          <div className="text-[10px] font-bold text-white">OpenAI</div>
                          <div className="text-[9px] text-[var(--text-muted)]">Whisper, Gpt 4.0 Mini-Transcribe</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-[rgba(0,217,255,0.05)] border border-[rgba(0,217,255,0.15)] rounded-lg p-2 flex items-center justify-between">
                    <span className="text-[10px] text-[var(--text-secondary)] font-mono">Use your own API keys. No markup.</span>
                    <Badge className="bg-[var(--cyan)] text-black text-[9px] px-2 py-0.5 h-auto rounded">Supported</Badge>
                  </div>
                </div>
              )}

              {activeTab === 'perf' && (
                <div className="flex-1 p-4 flex flex-col gap-3 text-left">
                  <div className="bg-[rgba(0,0,0,0.3)] border border-[var(--border)] rounded-lg p-3">
                    <div className="text-xs font-bold text-[var(--text-muted)] mb-3 tracking-widest">SYSTEM TELEMETRY</div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-[var(--text-secondary)] mb-1">Audio Latency</div>
                        <div className="text-lg font-bold text-[var(--lime)]">42ms</div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--text-secondary)] mb-1">TTFT</div>
                        <div className="text-lg font-bold text-[var(--cyan)]">187ms</div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-[rgba(0,217,255,0.05)] border border-[rgba(0,217,255,0.15)] rounded-lg p-3 flex-1">
                    <div className="text-xs text-[var(--text-secondary)] font-mono space-y-2">
                      <p>Overlay FPS: <span className="text-white">60.0</span></p>
                      <p>Memory: <span className="text-white">124 MB</span></p>
                      <p>Connection: <span className="text-[var(--lime)]">WSS HTTP/2 Secure</span></p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'stealth' && (
                <div className="flex-1 p-4 flex flex-col items-center justify-center relative bg-[rgba(0,0,0,0.2)]">
                  <div className="absolute inset-2 border-2 border-dashed border-[var(--lime)] opacity-20 rounded-xl" />
                  <EyeOff className="w-12 h-12 text-[var(--lime)] mb-3 animate-pulse" />
                  <h3 className="text-sm font-bold text-white tracking-widest mb-4">STEALTH MODE ACTIVE</h3>
                  <div className="text-xs font-mono text-[var(--text-secondary)] space-y-2 text-center">
                    <p className="text-[var(--lime)]">🟢 Hardware Overlay Bypassed</p>
                    <p className="text-[var(--lime)]">🟢 Capture APIs Hooked</p>
                    <div className="mt-4 inline-block text-[var(--cyan)] bg-[rgba(0,217,255,0.1)] border border-[rgba(0,217,255,0.2)] px-3 py-1.5 rounded font-sans font-bold">
                      Invisible to Zoom, Teams & Meet
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-8 max-w-2xl mx-auto animate-fade-in" style={{ animationDelay: "0.5s" }}>
          <div className="text-center">
            <div className="text-3xl font-bold text-[var(--cyan)] mb-2">187ms</div>
            <div className="text-sm text-[var(--text-muted)]">First Token (TTFT)</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-[var(--lime)] mb-2">100%</div>
            <div className="text-sm text-[var(--text-muted)]">Invisible on Screen Share</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-[var(--cyan)] mb-2">Open</div>
            <div className="text-sm text-[var(--text-muted)]">Source on GitHub</div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        .animate-fade-in {
          animation: fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards;
          opacity: 0;
        }
      `}</style>
    </section>
  );
}
