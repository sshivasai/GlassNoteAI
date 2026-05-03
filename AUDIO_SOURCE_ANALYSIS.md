# Audio Source Logic - Comprehensive Analysis Report

**Date:** 2026-05-03  
**Project:** GlassNote Interview Mode  
**Codebase Versions Analyzed:**
- Current: `C:\Users\sanko\OneDrive\Desktop\Proj_AI\GUI\`
- Prototype: `C:\Users\sanko\OneDrive\Desktop\Proj_AI_Copy\`

---

## Executive Summary

This report documents the **current behavior**, **expected behavior**, and **identified bugs** in the audio source handling logic for GlassNote's interview mode. The analysis covers all three audio source configurations: `system`, `microphone`, and `both`.

### Critical Issues Found

1. **STT continues transcribing after interview mode is paused** - The gate mechanism doesn't fully stop audio processing
2. **Audio source fallback is automatic and opaque** - When `source=system` but Stereo Mix is unavailable, falls back to mic without clear indication
3. **Voice gate always monitors microphone** - Even when `source=system`, the mic-based voice activity detector runs
4. **No support for dual-stream STT** - When `source=both`, audio is mixed; there's no separate "interviewer" vs "candidate" labeling for the LLM

---

## Architecture Overview

### Current Implementation (Proj_AI)

```
┌─────────────────────────────────────────────────────────────┐
│                    AudioPipeline                             │
│  - Manages STT connection (Deepgram/OpenAI)                 │
│  - Dispatch gate (_gated flag)                              │
│  - Smart answering / silence detection                       │
└───────┬─────────────────────────────────┬───────────────────┘
        │                                 │
        ▼                                 ▼
┌──────────────────┐            ┌──────────────────┐
│  AudioRecorder   │            │  VoiceActivityGate│
│  - Stream A      │            │  - Stream B       │
│  - Interview     │            │  - ALWAYS mic     │
│    audio         │            │  - Energy VAD     │
└──────────────────┘            └──────────────────┘
        │                                 │
        ▼                                 ▼
  ┌─────────┐                      ┌─────────┐
  │ System  │                      │  Mic    │
  │   OR    │                      │ (gate)  │
  │  Mic    │                      └─────────┘
  └─────────┘
```

### Key Components

1. **AudioPipeline** ([pipeline.py](GUI/audio/pipeline.py))
   - Coordinates STT, recorder, and voice gate
   - Has `_gated` flag for pause/resume (lines 132, 263-296)
   - Dispatches transcripts to LLM

2. **AudioRecorder** ([recorder.py](GUI/audio/recorder.py))
   - Captures audio from system (WASAPI loopback) or microphone
   - Source logic: lines 98-105
   - Single audio callback feeds STT (line 238-239)

3. **VoiceActivityGate** ([voice_gate.py](GUI/audio/voice_gate.py))
   - **Always** monitors microphone
   - Energy-based VAD (no STT)
   - Blocks dispatch when user is speaking

---

## Audio Source Scenarios - What SHOULD Happen vs What ACTUALLY Happens

### Scenario 1: `audio_source = "system"` (Interview Mode ON)

#### Expected Behavior
```
┌─────────────────────────────────────────────────────────────┐
│ System Audio (Interviewer)        Microphone (Candidate)    │
│                                                              │
│ ✓ Captured via WASAPI loopback    ✗ NOT captured           │
│ ✓ Sent to STT                     ✗ NOT monitored          │
│ ✓ Transcribed                     ✗ Voice gate OFF         │
│ ✓ Dispatched to LLM               ✗ No influence           │
│                                                              │
│ When system audio stops playing and candidate speaks:       │
│ → System captures NOTHING (no audio to transcribe)          │
│ → STT receives silence                                      │
│ → No dispatch (no meaningful speech detected)               │
└─────────────────────────────────────────────────────────────┘
```

#### Actual Behavior (CURRENT BUG)
```
┌─────────────────────────────────────────────────────────────┐
│ System Audio (Interviewer)        Microphone (Candidate)    │
│                                                              │
│ ✓ ATTEMPTED via loopback          ⚠️ FALLBACK ACTIVE       │
│ ⚠️ If Stereo Mix unavailable      ✓ Captured as fallback   │
│    → Falls back to mic            ✓ Sent to STT            │
│                                   ✓ Voice gate ACTIVE       │
│                                                              │
│ When system audio stops and candidate speaks:               │
│ → Mic captures candidate voice                              │
│ → Voice gate detects user speaking → BLOCKS dispatch        │
│ → BUT STT still transcribes (visible in logs!)              │
│ → Transcript buffered but not sent to LLM                   │
│                                                              │
│ ISSUE: STT WebSocket keeps processing audio even when       │
│        _gated=True (gate check in _on_audio_chunk not       │
│        effective)                                            │
└─────────────────────────────────────────────────────────────┘
```

**Evidence from logs:**
```
[pipeline] ⏸ Paused (gate closed — STT still connected)
[deepgram] flux [StartOfTurn]: 'So I think'
[deepgram] flux [Update]: 'So I think the'
```
☝️ Transcriptions continue appearing after pause

**Root Cause:**
1. [pipeline.py:604-609](GUI/audio/pipeline.py#L604-L609) - `_on_audio_chunk()` has gate check but audio still reaches STT
2. [recorder.py:238-239](GUI/audio/recorder.py#L238-L239) - Audio callback always fires `on_chunk()` as long as `_recording=True`
3. The `_gated` check happens in the pipeline, but the recorder doesn't know about gating

---

### Scenario 2: `audio_source = "microphone"` (Interview Mode ON)

#### Expected Behavior
```
┌─────────────────────────────────────────────────────────────┐
│ Microphone captures BOTH interviewer and candidate voices   │
│                                                              │
│ ✓ Mic stream sent to STT                                    │
│ ✓ Transcriptions include both speakers (mixed)              │
│ ✓ Voice gate monitors mic → detects when candidate speaks   │
│ ✓ Dispatch blocked while candidate is speaking              │
│                                                              │
│ Use case: Remote interview via speakers + mic               │
│ → Interviewer voice comes through speakers                  │
│ → Mic picks up interviewer voice from speakers              │
│ → Mic picks up candidate voice directly                     │
│ → STT transcribes everything                                │
│ → LLM sees mixed transcript (no speaker separation)         │
└─────────────────────────────────────────────────────────────┘
```

#### Actual Behavior
✅ **Works as expected** in this mode

**Limitation:** No speaker diarization - both voices appear in one transcript

---

### Scenario 3: `audio_source = "both"` (Interview Mode ON)

#### Expected Behavior (YOUR REQUIREMENT)
```
┌─────────────────────────────────────────────────────────────┐
│ DUAL-STREAM STT with speaker labels                         │
│                                                              │
│ Stream 1: System Audio (WASAPI loopback)                    │
│ ✓ Sent to STT Instance A                                    │
│ ✓ Transcribed → labeled "INTERVIEWER: ..."                  │
│                                                              │
│ Stream 2: Microphone                                         │
│ ✓ Sent to STT Instance B                                    │
│ ✓ Transcribed → labeled "CANDIDATE: ..."                    │
│                                                              │
│ LLM Prompt:                                                  │
│ "You are assisting a candidate in a technical interview.    │
│  INTERVIEWER: asks questions                                │
│  CANDIDATE: provides answers                                │
│  Give contextual responses to help the candidate."          │
│                                                              │
│ When candidate speaks (while system audio silent):          │
│ → Mic stream transcribes candidate speech                   │
│ → Transcript sent to LLM with CANDIDATE label               │
│ → LLM provides coaching/hints based on context              │
└─────────────────────────────────────────────────────────────┘
```

#### Actual Behavior (NOT IMPLEMENTED)
```
┌─────────────────────────────────────────────────────────────┐
│ MIXED AUDIO - No speaker separation                         │
│                                                              │
│ ✓ Both system loopback AND mic streams open                 │
│ ✓ Both call the SAME audio callback                         │
│ ✓ Audio mixed into single buffer                            │
│ ✓ Single STT instance receives mixed audio                  │
│ ⚠️ No speaker labels                                         │
│ ⚠️ LLM receives combined transcript without context         │
│                                                              │
│ [recorder.py:98-105] - Opens both streams                   │
│ [recorder.py:217-239] - Single _audio_callback handles both │
│                                                              │
│ When candidate speaks while system audio plays:             │
│ → Both streams active                                        │
│ → Audio overlaps in the same STT stream                     │
│ → Transcript: "interviewer question candidate response"     │
│      (no way to tell who said what)                         │
└─────────────────────────────────────────────────────────────┘
```

**Missing Implementation:**
1. ❌ No dual STT instances
2. ❌ No speaker labeling
3. ❌ No separate dispatch for interviewer vs candidate audio
4. ❌ LLM prompt doesn't handle dual roles

---

### Scenario 4: Interview Mode Paused (Stop Button Clicked)

#### Expected Behavior
```
┌─────────────────────────────────────────────────────────────┐
│ User clicks "Stop Interview Mode"                           │
│                                                              │
│ ✓ Audio recorder stops                                      │
│ ✓ STT WebSocket closes                                      │
│ ✓ Voice gate stops                                          │
│ ✓ No audio processing                                       │
│ ✓ No transcriptions appear in logs                          │
│                                                              │
│ If audio is still playing from system/speakers:             │
│ → Pipeline ignores it completely                            │
│ → No transcription                                          │
│ → No LLM dispatch                                           │
└─────────────────────────────────────────────────────────────┘
```

#### Actual Behavior (CRITICAL BUG)
```
┌─────────────────────────────────────────────────────────────┐
│ User clicks "Stop Interview Mode"                           │
│                                                              │
│ CURRENT CODE (pipeline.py:263-276):                         │
│ ✓ Sets _gated = True                                        │
│ ✓ Calls _reset_segment_state()                              │
│ ✗ Recorder keeps running (_continuous_mode still True)      │
│ ⚠️ STT WebSocket STAYS CONNECTED                            │
│ ⚠️ Audio callback keeps firing                              │
│                                                              │
│ Evidence from logs:                                          │
│ [pipeline] ⏸ Paused (gate closed — STT still connected)     │
│ [pipeline] 🎤 User started speaking — dispatch gated        │
│ [deepgram] flux [Update]: 'So I think the first...'         │
│                                                              │
│ ☝️ Transcriptions STILL APPEAR after pause!                 │
│                                                              │
│ Root Cause:                                                  │
│ 1. pause() only sets _gated=True (line 273)                 │
│ 2. _on_audio_chunk() gate check (line 604-605) should block │
│ 3. BUT audio still reaches STT somehow                      │
│ 4. Likely: buffered audio in STT WebSocket not flushed      │
└─────────────────────────────────────────────────────────────┘
```

**Code Analysis:**

[pipeline.py:263-276](GUI/audio/pipeline.py#L263-L276) - `pause()` method:
```python
def pause(self):
    if self._gated:
        return
    self._gated = True
    self._reset_segment_state()
    self.partial_transcript.emit("")
    print("[pipeline] ⏸ Paused (gate closed — STT still connected)")
```
❌ Does NOT stop recorder  
❌ Does NOT close STT  
✅ Only sets gate flag

[pipeline.py:604-609](GUI/audio/pipeline.py#L604-L609) - `_on_audio_chunk()`:
```python
def _on_audio_chunk(self, pcm_bytes: bytes, native_sr: int):
    if self._gated:
        return  # ← Should block audio when paused
    if self._stt is None:
        return
    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
    self._stt.feed(pcm, native_sr)
```
✅ Has gate check  
❌ But transcriptions still appear in logs!

**Why the gate doesn't work:**
1. Audio callback fires before gate check can intercept
2. STT may have buffered audio that continues to process
3. The gate check is at the Python layer, but native audio threads keep running

---

## Comparison: Current vs Prototype Code

| Feature | Current (Proj_AI) | Prototype (Proj_AI_Copy) |
|---------|-------------------|--------------------------|
| **pause() method** | ✅ Lines 263-276 | ❌ **Missing** |
| **resume() method** | ✅ Lines 278-296 | ❌ **Missing** |
| **_gated flag** | ✅ Line 132 | ❌ **Missing** |
| **Gate check in _on_audio_chunk** | ✅ Line 604-605 | ❌ **Missing** |
| **Gate check in _on_partial** | ✅ Line 624-625 | ❌ **Missing** |
| **stop_recording() behavior** | Calls `_cleanup()` → stops all | Calls `_cleanup()` → stops all |
| **Smart answering** | ✅ Implemented | ✅ Implemented |
| **Dual-stream STT** | ❌ Not implemented | ❌ Not implemented |

### Key Difference
**Current code ADDED gating for fast pause/resume**, but the gate implementation is incomplete:
- ✅ Gate checks exist
- ❌ Gate doesn't fully stop audio flow to STT
- ❌ Transcriptions leak through after pause

**Prototype code has NO gating** - it's a simpler "start/stop only" design where `stop_recording()` tears down everything.

---

## The Voice Gate Problem

### Current Behavior
[pipeline.py:201-212](GUI/audio/pipeline.py#L201-L212):
```python
# ── Start voice gate (ALWAYS on mic) ───────────────────────────────────
self._voice_gate = VoiceActivityGate(
    on_user_started = self._on_user_started_speaking,
    on_user_stopped = self._on_user_stopped_speaking,
    hold_time       = 0.8,
)
```
☝️ Comment says "ALWAYS on mic" - this is correct but problematic

### The Issue
**When `audio_source="system"`:**
- System audio should be the ONLY source
- Voice gate monitors mic anyway
- If candidate speaks, gate blocks dispatch
- BUT in a real interview scenario:
  - Interviewer audio comes from system
  - Candidate should NOT be able to respond verbally (they type or use the app)
  - The voice gate is unnecessary noise

**When `audio_source="microphone"`:**
- Mic captures both interviewer (from speakers) and candidate
- Voice gate blocks dispatch when candidate speaks
- ✅ This makes sense

**When `audio_source="both"`:**
- Should have separate handling for each stream
- Voice gate should only monitor candidate mic
- NOT block when candidate speaks (we WANT to capture that!)

### Proposed Fix
Voice gate should be **conditional**:
```python
# Only start voice gate when it's needed
if source == "microphone":
    # Mic captures both voices - gate prevents echo/overlap
    self._voice_gate = VoiceActivityGate(...)
elif source == "both":
    # Gate monitors candidate mic, but doesn't block dispatch
    # (we want to transcribe candidate speech separately)
    self._voice_gate = VoiceActivityGate(
        on_user_started=..., 
        on_user_stopped=None  # Don't block dispatch
    )
else:  # source == "system"
    # No voice gate needed - system audio only
    self._voice_gate = None
```

---

## Detailed Flow Diagrams

### Current Flow: `source="system"` + Interview Mode ON

```
Time    System Audio    Recorder          STT               Voice Gate      Dispatch
─────────────────────────────────────────────────────────────────────────────────────
T=0     Playing         Loopback open     WebSocket open    Mic monitoring  Idle
        "Question?"     ↓ captures        ↓ receives PCM    ↓ calibrating   

T=2     Still playing   Chunks flowing    Transcribing      Silent          Idle
                        to STT            "Question?"       (no speech)     

T=3     Stops           Silence           Silence detected  Still silent    Idle
                        
T=4.5   Silent          Silence > 1.5s    End-of-turn       Still silent    ✅ DISPATCH
                                          fires                             → LLM

T=5     Silent          [USER PAUSES INTERVIEW MODE]
                        ↓
        Silent          _gated = True     ⚠️ Still open     Still running   ❌ Blocked
                        ↓
        Silent          Chunks still      ⚠️ Still          Mic hears       ❌ Blocked
                        flowing!          transcribing!     candidate       by gate

T=6     Candidate       [BUG] Mic as      ⚠️ Transcribes    ✅ Detects      ❌ Blocked
        speaks          fallback active   candidate         user speaking   by _gated
                        ↓
                        [deepgram] flux [Update]: 'The second one could be...'
                        ☝️ THIS SHOULDN'T HAPPEN WHEN PAUSED!
```

### Desired Flow: `source="both"` + Interview Mode ON

```
Time    System Audio    Recorder          STT A (System)    STT B (Mic)     Dispatch
──────────────────────────────────────────────────────────────────────────────────────
T=0     Playing         Loopback open     WS open           WS open         Idle
        "Question?"     Mic open          ↓ "INTERVIEWER:   (silent)        
                        ↓                 Question?"                        

T=2     Stops           Silence           End-of-turn       (silent)        
                        Candidate speaks  ↓                 ↓               
                                          (silent)          "CANDIDATE:     
                                                            answer..."      

T=3     Silent          Candidate done    (silent)          End-of-turn     ✅ DISPATCH
                                                            ↓               "CANDIDATE: 
                                                                            answer..."
                                                                            → LLM
```

---

## Recommended Architecture for Dual-Stream Mode

### New Components Needed

1. **Dual STT Manager**
   ```python
   class DualSTTManager:
       def __init__(self):
           self._stt_interviewer = None  # System audio STT
           self._stt_candidate = None    # Mic audio STT
           
       def on_interviewer_transcript(self, text: str):
           labeled = f"INTERVIEWER: {text}"
           self._dispatch_with_role(labeled, role="interviewer")
           
       def on_candidate_transcript(self, text: str):
           labeled = f"CANDIDATE: {text}"
           self._dispatch_with_role(labeled, role="candidate")
   ```

2. **Separate Audio Callbacks**
   ```python
   # recorder.py modifications
   def __init__(self, 
                source: str,
                on_system_chunk: Callable,  # NEW
                on_mic_chunk: Callable):    # NEW
       ...
       
   def _loopback_callback(self, indata, ...):
       chunk = indata.flatten()
       if self._on_system_chunk:
           self._on_system_chunk(chunk.tobytes(), self._native_sr)
           
   def _mic_callback(self, indata, ...):
       chunk = indata.flatten()
       if self._on_mic_chunk:
           self._on_mic_chunk(chunk.tobytes(), self._native_sr)
   ```

3. **Enhanced LLM Prompt**
   ```python
   def build_interview_prompt_dual_role(base: str) -> str:
       return f"""You are an AI assistant helping a candidate during a technical interview.

   The conversation has two speakers:
   - INTERVIEWER: asks technical questions
   - CANDIDATE: provides answers (the person you're helping)

   Your role:
   - When INTERVIEWER asks a question, provide brief, relevant hints to CANDIDATE
   - Don't give away the full answer - guide their thinking
   - Keep responses under 30 words so they're easy to absorb during the interview

   Context:
   {base}
   """
   ```

---

## Bug Summary & Severity

| # | Bug | Severity | Component | Line |
|---|-----|----------|-----------|------|
| 1 | STT continues transcribing after pause | 🔴 **CRITICAL** | [pipeline.py](GUI/audio/pipeline.py#L604) | 604-609 |
| 2 | Voice gate always runs (even when `source=system`) | 🟡 **MEDIUM** | [pipeline.py](GUI/audio/pipeline.py#L201) | 201-212 |
| 3 | Automatic fallback from system → mic is opaque | 🟡 **MEDIUM** | [recorder.py](GUI/audio/recorder.py#L101) | 101-105 |
| 4 | No dual-stream STT support for `source=both` | 🟠 **FEATURE** | N/A | N/A |
| 5 | No speaker diarization/labeling | 🟠 **FEATURE** | N/A | N/A |

---

## Fixing the Critical Bug (#1)

### Root Cause
The `_gated` flag blocks NEW audio from being sent to STT, but:
1. Audio already in the STT WebSocket buffer continues to process
2. The recorder's audio callback keeps firing (native thread)
3. There's a race between `_gated=True` and audio already en route

### Solution Options

#### Option A: Flush STT on pause (Quick Fix)
```python
def pause(self):
    if self._gated:
        return
    self._gated = True
    self._reset_segment_state()
    
    # NEW: Reset STT segment to clear buffer
    if self._stt and hasattr(self._stt, "reset_segment"):
        self._stt.reset_segment()
    
    # NEW: Close and reopen STT WebSocket to force buffer flush
    if self._stt and hasattr(self._stt, "close"):
        self._stt.close()
        cfg = config.load_config()
        self._stt = self._create_stt(cfg)
        if hasattr(self._stt, "start"):
            self._stt.start(self._recorder.get_native_sr())
    
    self.partial_transcript.emit("")
    print("[pipeline] ⏸ Paused (gate closed, STT flushed)")
```

#### Option B: Stop recorder on pause (Cleaner)
```python
def pause(self):
    if self._gated:
        return
    self._gated = True
    
    # Stop recorder to prevent audio callback from firing
    if self._recorder:
        self._recorder.stop()
        self._recorder = None
    
    # Close STT to drop WebSocket
    if self._stt and hasattr(self._stt, "close"):
        self._stt.close()
        self._stt = None
    
    # Voice gate can stay active (for resume speed)
    self._reset_segment_state()
    self.partial_transcript.emit("")
    print("[pipeline] ⏸ Paused (recorder+STT stopped)")
```

Then modify `resume()` to restart:
```python
def resume(self):
    if not self._gated:
        return
    self._gated = False
    
    # Restart recorder
    cfg = config.load_config()
    source = cfg.get("audio_source", "system")
    
    self._recorder = AudioRecorder(
        source=source,
        on_level=lambda lvl: self.level_update.emit(lvl),
        on_chunk=self._on_audio_chunk,
    )
    self._recorder.start()
    
    # Restart STT
    self._stt = self._create_stt(cfg)
    if hasattr(self._stt, "start"):
        self._stt.start(self._recorder.get_native_sr())
    
    self._reset_segment_state()
    self._last_dispatch_time = time.time()
    print("[pipeline] ▶ Resumed")
```

**Trade-off:** Option B is slower to resume (~500ms vs instant) but fully stops audio processing.

---

## Implementation Roadmap

### Phase 1: Fix Critical Bug (Priority 1)
- [ ] Implement Option A or B above
- [ ] Test that transcriptions stop after pause
- [ ] Verify logs show no STT activity when paused

### Phase 2: Voice Gate Conditional Logic (Priority 2)
- [ ] Make voice gate conditional based on `audio_source`
- [ ] When `source=system`, disable voice gate
- [ ] Test scenario: system audio + candidate speaking → no gate interference

### Phase 3: Improve Fallback Transparency (Priority 3)
- [ ] Add user-facing warning when system audio fallback occurs
- [ ] Suggest enabling Stereo Mix in Settings
- [ ] Show audio source status in pill UI

### Phase 4: Dual-Stream STT (Feature)
- [ ] Create `DualSTTManager` class
- [ ] Separate audio callbacks in recorder
- [ ] Implement speaker labeling
- [ ] Update LLM prompts for dual-role context
- [ ] Test with real interview scenarios

---

## Testing Checklist

### Scenario: `source=system` + Stereo Mix Enabled
- [ ] Interview mode starts
- [ ] System audio transcribed correctly
- [ ] Candidate speaks → NO transcription (system is silent)
- [ ] Pause interview → transcriptions STOP immediately
- [ ] Resume → system audio transcribed again

### Scenario: `source=system` + Stereo Mix Disabled
- [ ] Shows warning about Stereo Mix
- [ ] Falls back to microphone
- [ ] Captures both voices (expected behavior)
- [ ] Pause → transcriptions stop

### Scenario: `source=microphone`
- [ ] Captures both voices
- [ ] Voice gate blocks dispatch when candidate speaks
- [ ] LLM receives mixed transcript
- [ ] Pause → transcriptions stop

### Scenario: `source=both` (Future)
- [ ] Separate STT instances for system and mic
- [ ] Transcripts labeled INTERVIEWER: / CANDIDATE:
- [ ] LLM receives dual-role context
- [ ] Candidate speech dispatched separately
- [ ] Pause → both STT instances stop

---

## Conclusion

The current implementation has a **critical bug** where STT continues processing audio after interview mode is paused. This is caused by the incomplete gate mechanism that blocks dispatch but not audio flow.

The **desired dual-stream behavior** for `source=both` is not implemented - currently both streams are mixed into a single STT instance without speaker labels.

### Immediate Actions Required
1. Fix the pause/resume bug (Phase 1)
2. Make voice gate conditional (Phase 2)
3. Plan dual-stream architecture (Phase 4)

### Long-term Vision
A robust dual-stream system where:
- System audio = Interviewer
- Microphone = Candidate
- Separate transcripts with role labels
- LLM understands who is speaking
- Contextual assistance based on speaker role

---

**Report prepared by:** Claude (Sonnet 4.5)  
**Analysis includes:** Code review, log analysis, architecture recommendations
