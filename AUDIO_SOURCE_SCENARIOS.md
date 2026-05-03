# Audio Source Scenarios - Quick Reference

## What Should Happen in Each Scenario

### 🎧 Scenario 1: `audio_source = "system"` + Interview Mode ON

**Setup:** Stereo Mix enabled, system audio playing interviewer questions

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ EXPECTED: System audio ONLY                              │
├─────────────────────────────────────────────────────────────┤
│ • System audio (interviewer) → Captured via WASAPI loopback │
│ • Microphone (candidate) → NOT captured                     │
│ • Voice gate → DISABLED (not needed)                        │
│                                                              │
│ When system audio stops and candidate speaks:               │
│ → No audio captured (system is silent)                      │
│ → No transcription                                          │
│ → No LLM dispatch                                           │
│                                                              │
│ When interview mode is paused:                              │
│ → Recorder stops                                            │
│ → STT closes                                                │
│ → No transcriptions appear (even if audio still playing)    │
└─────────────────────────────────────────────────────────────┘
```

**Current Behavior (BUGS):**
- ❌ When Stereo Mix unavailable → Falls back to mic (captures candidate too)
- ❌ Voice gate still runs (unnecessary)
- ❌ **After pause, STT keeps transcribing** (CRITICAL)

---

### 🎤 Scenario 2: `audio_source = "microphone"` + Interview Mode ON

**Setup:** Remote interview, interviewer voice comes through speakers

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ EXPECTED: Microphone captures BOTH voices                │
├─────────────────────────────────────────────────────────────┤
│ • Mic picks up interviewer voice (from speakers)            │
│ • Mic picks up candidate voice (direct)                     │
│ • Voice gate → ENABLED (blocks dispatch when candidate      │
│   speaks to avoid echo/overlap)                             │
│ • STT transcribes mixed audio (no speaker separation)       │
│                                                              │
│ When candidate speaks:                                      │
│ → Voice gate detects speech                                 │
│ → Dispatch BLOCKED (don't send partial response while       │
│   candidate is still answering)                             │
│ → After candidate stops → gate releases → dispatch          │
│                                                              │
│ When interview mode is paused:                              │
│ → Recorder stops                                            │
│ → STT closes                                                │
│ → No transcriptions                                         │
└─────────────────────────────────────────────────────────────┘
```

**Current Behavior:**
- ✅ Works mostly as expected
- ❌ **After pause, STT keeps transcribing** (CRITICAL)

---

### 🎧+🎤 Scenario 3: `audio_source = "both"` + Interview Mode ON

**Setup:** Dual-stream with speaker identification (DESIRED FEATURE)

```
┌─────────────────────────────────────────────────────────────┐
│ 🚀 DESIRED: Separate STT for each speaker                   │
├─────────────────────────────────────────────────────────────┤
│ Stream A: System Audio → STT Instance 1                     │
│   → Transcribed as "INTERVIEWER: question text"            │
│                                                              │
│ Stream B: Microphone → STT Instance 2                       │
│   → Transcribed as "CANDIDATE: answer text"                │
│                                                              │
│ LLM Prompt:                                                  │
│ "You are helping CANDIDATE during an interview.             │
│  INTERVIEWER asks questions, CANDIDATE answers.             │
│  Provide contextual hints to CANDIDATE."                    │
│                                                              │
│ When interviewer asks question:                             │
│ → System audio → "INTERVIEWER: Explain quicksort"          │
│ → Dispatch to LLM                                           │
│ → LLM: "Think about divide-and-conquer, pivot selection"   │
│                                                              │
│ When candidate speaks (system silent):                      │
│ → Mic → "CANDIDATE: So we pick a pivot and..."             │
│ → Dispatch to LLM                                           │
│ → LLM: "Good start! Mention partition step next"           │
│                                                              │
│ When both speak simultaneously:                             │
│ → Both STT instances transcribe independently               │
│ → LLM sees both contexts                                    │
└─────────────────────────────────────────────────────────────┘
```

**Current Behavior (NOT IMPLEMENTED):**
- ❌ No dual STT instances
- ❌ Both streams mixed into single STT
- ❌ No speaker labels
- ❌ LLM can't tell who is speaking
- ❌ Can't provide role-specific coaching

---

### ⏸️ Scenario 4: ANY source + Interview Mode PAUSED

**Expected:**
```
┌─────────────────────────────────────────────────────────────┐
│ User clicks "Pause Interview Mode" button                   │
├─────────────────────────────────────────────────────────────┤
│ ✅ Recorder stops immediately                               │
│ ✅ STT WebSocket closes                                     │
│ ✅ Voice gate stops                                         │
│ ✅ NO transcriptions appear (even if audio playing)         │
│ ✅ Logs silent                                              │
└─────────────────────────────────────────────────────────────┘
```

**Current Behavior (CRITICAL BUG):**
```
┌─────────────────────────────────────────────────────────────┐
│ User clicks "Pause Interview Mode" button                   │
├─────────────────────────────────────────────────────────────┤
│ ⚠️ Sets _gated=True (dispatch blocked)                     │
│ ❌ Recorder KEEPS RUNNING                                   │
│ ❌ STT WebSocket STAYS OPEN                                 │
│ ❌ Audio callback keeps firing                              │
│ ❌ TRANSCRIPTIONS STILL APPEAR IN LOGS                      │
│                                                              │
│ Evidence from your logs:                                    │
│ [pipeline] ⏸ Paused (gate closed — STT still connected)     │
│ [deepgram] flux [Update]: 'So I think the first...'        │
│            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^         │
│            THIS SHOULD NOT HAPPEN!                          │
└─────────────────────────────────────────────────────────────┘
```

---

## The Voice Gate Problem

### What Voice Gate Does
- Monitors microphone using energy-based VAD
- Detects when candidate (user) is speaking
- **Blocks LLM dispatch** while user speaks
- Prevents sending incomplete/interrupted questions

### Current Behavior (WRONG)
Voice gate **ALWAYS runs**, regardless of audio source:

```python
# pipeline.py line 201
# ── Start voice gate (ALWAYS on mic) ───────────────────────────────────
self._voice_gate = VoiceActivityGate(...)
```

### Problems

#### When `source="system"`
- ❌ Voice gate monitors mic (shouldn't - system audio only!)
- ❌ If candidate speaks, gate blocks dispatch (wrong - we only capture system)
- ❌ Unnecessary processing overhead

#### When `source="microphone"`
- ✅ Voice gate makes sense (blocks dispatch when candidate speaks)
- ✅ Works correctly

#### When `source="both"`
- ❌ Voice gate blocks ALL dispatch when candidate speaks
- ❌ But we WANT to transcribe candidate speech!
- ❌ Should monitor but not block (separate handling needed)

---

## Audio Source Fallback Logic

### Current Code ([recorder.py:98-105](GUI/audio/recorder.py#L98-L105))

```python
if self._source in ("system", "both") and sys.platform == "win32":
    opened_loopback = self._start_loopback(sd)

if self._source in ("microphone", "both") or not opened_loopback:
    self._start_microphone(sd)
```

### What This Means

#### Case 1: `source="system"` + Stereo Mix enabled
```
✅ Loopback opens successfully
❌ Microphone ALSO opens (line 104: "or not opened_loopback" is False)
   Wait, no - this is correct, mic won't open
```
Actually on second read: `if ... or not opened_loopback` means:
- If source is "microphone" → open mic
- If source is "both" → open mic
- **If loopback failed (opened_loopback=False) → open mic as fallback**

#### Case 2: `source="system"` + Stereo Mix DISABLED
```
❌ Loopback fails (opened_loopback=False)
✅ Condition "or not opened_loopback" is True
✅ Microphone opens as FALLBACK
⚠️ User thinks they're getting system audio only
⚠️ But actually getting mic (both voices)
```

**Problem:** Silent fallback - user is not clearly warned

---

## Summary Table

| Audio Source | Stereo Mix | What Opens | Voice Gate | Transcribes | LLM Gets | Bugs |
|--------------|------------|------------|------------|-------------|----------|------|
| `system` | ✅ Enabled | Loopback only | ❌ Still runs (wrong) | System audio only | Single stream | Pause bug |
| `system` | ❌ Disabled | **Mic fallback** | ✅ Runs | Both voices | Single stream | Pause bug, silent fallback |
| `microphone` | N/A | Mic only | ✅ Runs | Both voices | Single stream | Pause bug |
| `both` | ✅ Enabled | Loopback + Mic | ❌ Wrong behavior | **Mixed** audio | Single stream (no labels) | Pause bug, no dual STT |
| `both` | ❌ Disabled | Mic only | ❌ Wrong behavior | Both voices | Single stream | Same as `microphone` mode |

---

## Priority Fixes

### 🔴 P0 - Critical (Interview Mode Broken)
**Issue:** STT keeps transcribing after pause  
**Impact:** Can't stop interview mode properly  
**Files:** [pipeline.py:604-609](GUI/audio/pipeline.py#L604-L609), [pipeline.py:263-276](GUI/audio/pipeline.py#L263-L276)  
**Fix:** Stop recorder and close STT on pause, restart on resume

### 🟠 P1 - High (Incorrect Behavior)
**Issue:** Voice gate always runs (even when source=system)  
**Impact:** Unnecessary processing, wrong behavior for dual-stream  
**Files:** [pipeline.py:201-212](GUI/audio/pipeline.py#L201-L212)  
**Fix:** Make voice gate conditional based on audio source

### 🟡 P2 - Medium (Poor UX)
**Issue:** Silent fallback from system → mic  
**Impact:** User confusion, unexpected behavior  
**Files:** [recorder.py:104-105](GUI/audio/recorder.py#L104-L105)  
**Fix:** Show warning dialog when fallback occurs, suggest enabling Stereo Mix

### 🟢 P3 - Feature Request
**Issue:** No dual-stream STT for `source="both"`  
**Impact:** Can't separate interviewer/candidate speech  
**Files:** New architecture needed  
**Fix:** Implement DualSTTManager, separate callbacks, speaker labeling

---

## Next Steps

1. **Read the full analysis:** [AUDIO_SOURCE_ANALYSIS.md](AUDIO_SOURCE_ANALYSIS.md)
2. **Review proposed fixes** in the "Fixing the Critical Bug" section
3. **Choose Option A or B** for pause/resume fix
4. **Test thoroughly** using the testing checklist
5. **Plan Phase 4** (dual-stream) after fixing critical bugs

---

**Quick Decision Matrix:**

| Your Priority | Start With |
|---------------|------------|
| "Just make pause work" | Fix P0 (Option A - quick fix) |
| "Clean architecture" | Fix P0 (Option B - proper stop) |
| "Dual-stream feature" | Fix P0 + P1, then build Phase 4 |
| "Ship fast" | Fix P0 only, defer others |
