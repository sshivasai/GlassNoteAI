# Connection Lifecycle - Complete Guide

**When connections are established, how pause/resume works, and KeepAlive handling**

---

## 📊 Timeline: Session Start → Interview Mode → Pause → Resume → End

```
┌──────────────────────────────────────────────────────────────────────┐
│ USER ACTION                  CONNECTIONS STATUS                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│ 1. Click "Start Session"     ❌ Nothing connected yet                │
│    ↓                                                                 │
│    Backend registration       🌐 HTTP: POST /api/sessions/start     │
│    ↓                           (closes after response)               │
│                                                                       │
│ 2. Session created ✓          🔄 WARM-UP PHASE BEGINS               │
│    ↓                           (background threads)                  │
│    _on_session_started()                                            │
│    ↓                          ┌─────────────────────────────────┐   │
│                               │ 1. LLM TCP+TLS pre-warm         │   │
│                               │    → api.anthropic.com          │   │
│                               │    → api.openai.com             │   │
│                               │    (connection pool opened)     │   │
│                               │                                 │   │
│                               │ 2. STT DNS pre-resolve          │   │
│                               │    → api.deepgram.com           │   │
│                               │    → api.openai.com             │   │
│                               │    (OS DNS cache populated)     │   │
│                               │                                 │   │
│                               │ 3. Audio pipeline START         │   │
│                               │    → Recorder opens audio dev   │   │
│                               │    → STT WebSocket OPENS        │   │
│                               │    → Voice gate opens mic       │   │
│                               │    → Pipeline PAUSED (gated)    │   │
│                               └─────────────────────────────────┘   │
│    ↓                                                                 │
│    Warm-up complete          ✅ READY STATE                         │
│                               • LLM: HTTP/2 pool open + keepalive   │
│                               • STT: WebSocket OPEN (idle)          │
│                               • Recorder: Running (gated)           │
│                               • Voice gate: Active                  │
│                                                                       │
│    [User sees pill, can use other features]                         │
│                                                                       │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                       │
│ 3. Click "Interview Mode" ▶  ✅ RESUME (instant - already warm)     │
│    ↓                           • Gate opens (_gated=False)          │
│    _start_continuous_recording()                                    │
│    ↓                           • Audio flows to STT immediately     │
│    resume()                    • No connection overhead!            │
│                                                                       │
│    Interviewer speaks         🎤 ACTIVE TRANSCRIPTION               │
│    ↓                           • Recorder: Capturing audio          │
│                               • STT: Sending PCM → receiving text   │
│                               • KeepAlive: Active (every 8s)        │
│                               • Voice gate: Monitoring candidate    │
│                                                                       │
│    STT sends EndOfTurn       📤 LLM DISPATCH                        │
│    ↓                           • HTTP/2 POST (reuses warm pool)     │
│    LLM responds               • LLM: Streaming response             │
│                               • STT: Still listening for next Q     │
│                                                                       │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                       │
│ 4. Click "Interview Mode" ⏸  ⏸️ PAUSE (keeps connections)           │
│    ↓                           • Gate closes (_gated=True)          │
│    _stop_continuous_recording()                                     │
│    ↓                           • Audio stops flowing to STT         │
│    pause()                     • WebSocket STAYS OPEN (idle)        │
│                               • KeepAlive continues (prevents drop) │
│                               • Voice gate: Still running           │
│                               • Recorder: Still running             │
│                                                                       │
│    [Connections alive, ready for instant resume]                    │
│                                                                       │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                       │
│ 5. Click "Interview Mode" ▶  ✅ RESUME (< 1ms, no rebuild)          │
│    (again)                     • Gate opens (_gated=False)          │
│    ↓                           • Audio flows immediately            │
│    resume()                    • Zero latency - WebSocket ready     │
│                                                                       │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                       │
│ 6. Click "End Session"       ❌ FULL TEARDOWN                       │
│    ↓                           • stop_recording() called            │
│    _on_end_session()           • WebSocket closes (CloseStream)     │
│                               • Recorder stops                      │
│                               • Voice gate stops                    │
│                               • LLM keepalive stops                 │
│                               • All resources released              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Questions Answered

### Q1: When are connections established - on session start or interview mode start?

**Answer:** **Connections are established at SESSION START** (not interview mode start)

**Timeline:**
```
1. User clicks "Start Session"
   ↓
2. Backend confirms session
   ↓
3. _on_session_started() fires
   ↓
4. IMMEDIATE CONNECTION WARM-UP (background threads):
   
   ┌─────────────────────────────────────────────────┐
   │ LLM Connection Pool                             │
   │ • TCP handshake to api.anthropic.com           │
   │ • TLS negotiation                              │
   │ • HTTP/2 connection pool opens                 │
   │ • Keepalive heartbeat starts (45s interval)    │
   │   - Sends /health ping every 45s               │
   │   - Prevents connection timeout                │
   │ Duration: ~200-500ms                           │
   └─────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────┐
   │ STT WebSocket                                   │
   │ • DNS pre-resolution (api.deepgram.com)        │
   │ • Audio pipeline starts                        │
   │ • Recorder opens audio device                  │
   │ • WebSocket CONNECTS to Deepgram/OpenAI       │
   │ • Pipeline immediately PAUSED (_gated=True)    │
   │ • KeepAlive thread starts                      │
   │ Duration: ~300-800ms                           │
   └─────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────┐
   │ Voice Activity Gate                             │
   │ • Microphone opens                             │
   │ • Calibrates noise floor (~2s)                 │
   │ • Monitors user speech continuously            │
   │ Duration: ~2-3s                                │
   └─────────────────────────────────────────────────┘

5. Pill appears with "warming" indicator (amber)
6. After all warm-ups complete: dot turns green
7. User can now click "Interview Mode" → INSTANT START (no connection overhead)
```

**Why this approach?**
- **Zero latency** when user starts interview mode
- User can use other features (Solve, Analyze) without waiting
- Connections are ready the moment user needs them
- Warm connections prevent 2-5 second delay on first question

**Evidence in code:**
- [app_controller.py:1051-1244](GUI/app_controller.py#L1051-L1244) - `_on_session_started()` method
- [app_controller.py:1109-1114](GUI/app_controller.py#L1109-L1114) - Speculative warm thread
- [app_controller.py:1125-1241](GUI/app_controller.py#L1125-L1241) - STT prefetch thread

---

### Q2: When pause interview mode, are connections disconnected or kept alive?

**Answer:** **Connections are KEPT ALIVE** (not disconnected)

**Current Implementation:**
```python
# app_controller.py:561-588
def _stop_continuous_recording(self):
    """Exit interview mode - pause but keep connections warm."""
    self._recording = False
    self._silence_timer.stop()
    
    # Use pause() to close gate but keep STT WebSocket alive
    self._audio.pause()  # ← Does NOT call stop_recording()
    
    print("[app] Interview mode paused (WebSocket kept alive for fast resume)")
```

```python
# pipeline.py:263-276
def pause(self):
    """Gate the dispatch — stop forwarding audio to LLM."""
    if self._gated:
        return
    self._gated = True
    self._reset_segment_state()
    self.partial_transcript.emit("")
    print("[pipeline] ⏸ Paused (gate closed — STT still connected)")
    # ↑ Note: WebSocket NOT closed
```

**What stays connected:**
```
✅ STT WebSocket    → OPEN (idle, sending KeepAlive)
✅ Recorder         → RUNNING (but gated, no audio to STT)
✅ Voice gate       → ACTIVE (still monitoring mic)
✅ LLM HTTP/2 pool  → OPEN (keepalive pings every 45s)

❌ Audio flow       → BLOCKED (_gated=True check)
❌ Transcriptions   → NOT dispatched to LLM
❌ Silence timer    → STOPPED
```

**Why keep alive?**
- **Fast resume:** < 1ms to restart (just open gate)
- **No reconnect overhead:** Avoid 500-1000ms WebSocket handshake
- **Session continuity:** Same WebSocket session ID preserved
- **Battery/CPU efficient:** KeepAlive messages are tiny (few bytes every 8s)

---

### Q3: Can interview mode only be paused, or closed completely?

**Answer:** Interview mode can be **PAUSED** (toggle on/off) but connections **only close when session ends**

**Interview Mode Lifecycle:**
```
Session Start
    ↓
[Warm connections established - WebSocket OPEN]
    ↓
    ┌──────────────────────────────────────┐
    │  Interview Mode Toggle Loop          │
    │                                      │
    │  User: Click "Interview" ▶           │
    │  → resume() → _gated=False           │
    │  → Audio flows to STT                │
    │                                      │
    │  User: Click "Interview" ⏸           │
    │  → pause() → _gated=True             │
    │  → Audio blocked, WebSocket kept     │
    │                                      │
    │  [Can toggle on/off multiple times]  │
    │  [Each resume is instant - < 1ms]    │
    └──────────────────────────────────────┘
    ↓
Session End
    ↓
[Full teardown - WebSocket CLOSED]
```

**Code Evidence:**
```python
# app_controller.py:515-559
def _start_continuous_recording(self):
    if not self._audio.is_running():
        # ↑ First time only - start full pipeline
        self._audio.start_recording(source=source)
    
    # Subsequent times: just resume (instant)
    self._audio.resume()  # ← Opens gate only

# app_controller.py:561-588
def _stop_continuous_recording(self):
    # Does NOT call stop_recording() - uses pause() instead
    self._audio.pause()  # ← Closes gate, keeps WebSocket
```

**Full close only happens on session end:**
```python
# app_controller.py:977-1043
def _on_end_session(self):
    llm_streamer.cancel()
    llm_client.stop_keepalive()  # ← Stop LLM keepalive
    self._audio.stop_recording()  # ← NOW we close everything
    # ↑ This calls pipeline.stop_recording() → _cleanup()
    #   → closes WebSocket, stops recorder, stops voice gate
```

---

## 🔄 KeepAlive Handling

### Yes, we ARE using KeepAlive! Two types:

### 1️⃣ **Deepgram KeepAlive** (JSON message)

**Location:** [stt_deepgram.py:406-460](GUI/audio/stt_deepgram.py#L406-L460)

```python
def _keepalive_loop(self, ws, is_flux: bool = False):
    """
    Bug D fix — sends Deepgram KeepAlive every 8s for nova models.
    
    Why needed: Deepgram closes WebSocket if no data for 60s.
    When pipeline is paused, no audio is sent → connection drops.
    
    KeepAlive message: {"type": "KeepAlive"}
    """
    if is_flux:
        # Flux: Use WebSocket ping frames (RFC 6455)
        while self._running:
            time.sleep(30)  # Every 30s
            ws.ping()  # Protocol-level ping
    else:
        # Nova: Use Deepgram JSON KeepAlive
        keepalive_msg = json.dumps({"type": "KeepAlive"})
        while self._running:
            time.sleep(8)  # Every 8s
            ws.send(keepalive_msg)
```

**Two different approaches:**

#### Nova Models (v1 API: nova-2, nova-3)
```json
{"type": "KeepAlive"}
```
Sent every **8 seconds** via WebSocket

#### Flux Models (v2 API: flux-general-en)
```
WebSocket ping frame (opcode 0x9)
```
Sent every **30 seconds** via protocol-level ping

**Why different?**
- Flux v2 API doesn't accept JSON KeepAlive (causes error)
- Flux accepts WebSocket protocol pings (RFC 6455)
- Nova v1 accepts both, but JSON is more reliable

**Evidence in logs:**
```
[deepgram] Connecting nova → nova-3  vad_events=yes
[deepgram] nova connected ✓
[deepgram] session 019dee19
[pipeline] ⏸ Paused (gate closed — STT still connected)
# ↑ WebSocket stays open, KeepAlive thread keeps pinging every 8s
```

---

### 2️⃣ **LLM HTTP/2 KeepAlive** (connection pool heartbeat)

**Location:** [llm/client.py:308-449](GUI/llm/client.py#L308-L449)

```python
# HTTP/2 connection pool — keepalive heartbeat
pool = httpx.Client(
    http2=True,
    timeout=httpx.Timeout(90.0, connect=10.0),
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,  # ← Keep 5 alive
        keepalive_expiry=300,         # ← 5 min timeout
    ),
)

# Keepalive heartbeat (sends /health ping every 45s)
def _beat():
    while client._keepalive_active:
        time.sleep(45)  # Every 45s
        try:
            client._pool.get(
                f"{provider_url}/health",
                timeout=5.0
            )
        except Exception:
            pass  # Non-fatal

threading.Thread(
    target=_beat,
    daemon=True,
    name="llm-keepalive"
).start()
```

**Why needed:**
- Prevents TCP connection timeout (typically 60-120s)
- Reuses same connection for all LLM requests in session
- Saves 100-300ms per request (no TCP+TLS handshake)

**Stopped on session end:**
```python
# app_controller.py:981
llm_client.stop_keepalive()  # ← Stops heartbeat thread
```

---

### 3️⃣ **OpenAI Realtime** (if using gpt-4o-mini-transcribe)

**Location:** [stt_openai_realtime.py](GUI/audio/stt_openai_realtime.py)

```python
# WebSocket: wss://api.openai.com/v1/realtime?intent=transcription
# No explicit KeepAlive needed - server doesn't timeout on silence
# But we do send audio commitments to keep session alive
```

**No separate KeepAlive needed because:**
- OpenAI Realtime has built-in session management
- Server-side VAD handles silence gracefully
- Connection stays alive as long as WebSocket is open

---

## 📋 Connection State Table

| Event | LLM HTTP/2 | STT WebSocket | Recorder | Voice Gate | Audio Flow |
|-------|-----------|---------------|----------|------------|------------|
| **Session Start** | ❌ Closed | ❌ Closed | ❌ Stopped | ❌ Stopped | ❌ |
| **Session Created** | 🔄 Connecting | 🔄 Connecting | 🔄 Opening | 🔄 Opening | ❌ |
| **Warm-up Complete** | ✅ Pool open + keepalive | ✅ WebSocket open + keepalive | ✅ Running (gated) | ✅ Active | ❌ Blocked |
| **Interview ▶ Start** | ✅ Same | ✅ Same | ✅ Running (ungated) | ✅ Same | ✅ Flowing |
| **Interview ⏸ Pause** | ✅ Same | ✅ Same | ✅ Running (gated) | ✅ Same | ❌ Blocked |
| **Interview ▶ Resume** | ✅ Same | ✅ Same | ✅ Running (ungated) | ✅ Same | ✅ Flowing |
| **Session End** | ❌ Closed | ❌ Closed | ❌ Stopped | ❌ Stopped | ❌ |

---

## 🎯 Performance Benefits

### Without Warm-up (old approach)
```
User clicks "Interview Mode"
    ↓
    [2-5 seconds delay]
    ↓ DNS resolve (100-300ms)
    ↓ TCP handshake (50-150ms)
    ↓ TLS negotiation (200-500ms)
    ↓ WebSocket upgrade (50-100ms)
    ↓ Audio device open (100-200ms)
    ↓
Interview mode starts (user waited 2-5s)
```

### With Warm-up (current approach)
```
Session Start
    ↓
    [Warm-up in background while user sees pill]
    ↓
User clicks "Interview Mode"
    ↓
    [< 1ms - just open gate]
    ↓
Interview mode starts INSTANTLY ✨
```

### With KeepAlive (pause/resume)
```
Interview paused
    ↓
    [WebSocket kept alive, KeepAlive pings every 8s]
    ↓
User resumes (30 seconds later)
    ↓
    [< 1ms - just open gate]
    ↓
Interview continues INSTANTLY ✨

Without KeepAlive, would need:
- Reconnect (500-1000ms)
- New session ID
- Risk of dropped audio during reconnect
```

---

## 🐛 Current Bug: Pause Doesn't Fully Work

**Issue:** Even though gate closes, STT still transcribes after pause

**Root Cause:**
```python
# pipeline.py:604-609
def _on_audio_chunk(self, pcm_bytes: bytes, native_sr: int):
    if self._gated:
        return  # ← Should block audio
    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
    self._stt.feed(pcm, native_sr)
```

**Problem:** Audio already in STT WebSocket buffer continues processing

**Evidence:** Your logs show transcriptions AFTER pause:
```
[pipeline] ⏸ Paused (gate closed — STT still connected)
[deepgram] flux [Update]: 'So I think the first...'
                           ^^^^^^^^^^^^^^^^^^^^^^
                           SHOULDN'T HAPPEN!
```

**Fix:** See [AUDIO_SOURCE_ANALYSIS.md](AUDIO_SOURCE_ANALYSIS.md) section "Fixing the Critical Bug"

---

## 🔧 Code References

### Connection Warm-up
- [app_controller.py:1051-1244](GUI/app_controller.py#L1051-L1244) - Session start warm-up
- [app_controller.py:647-689](GUI/app_controller.py#L647-L689) - Speculative warm

### Interview Mode Toggle
- [app_controller.py:515-559](GUI/app_controller.py#L515-L559) - Start (resume)
- [app_controller.py:561-588](GUI/app_controller.py#L561-L588) - Stop (pause)

### KeepAlive Implementation
- [stt_deepgram.py:406-460](GUI/audio/stt_deepgram.py#L406-L460) - Deepgram KeepAlive
- [llm/client.py:308-449](GUI/llm/client.py#L308-L449) - LLM keepalive

### Pause/Resume
- [pipeline.py:263-276](GUI/pipeline.py#L263-L276) - pause() method
- [pipeline.py:278-296](GUI/pipeline.py#L278-L296) - resume() method

---

## 📝 Summary

1. **Connections established:** At session start (not interview mode start)
2. **Interview mode start:** Instant (< 1ms) - just opens gate
3. **Pause behavior:** Keeps connections alive (WebSocket + KeepAlive active)
4. **Resume behavior:** Instant (< 1ms) - just reopens gate
5. **Full close:** Only on session end
6. **KeepAlive:** YES, both STT (every 8-30s) and LLM (every 45s)
7. **Why:** Zero latency on interview mode toggle, fast resume

**Key Insight:** The architecture is optimized for **instant responsiveness** by pre-warming connections and keeping them alive during pause. This is a deliberate design choice to provide the best user experience.
