# Testing Checklist - Audio Pipeline Fixes

**Quick reference for testing the pause/resume and voice gate fixes**

---

## ✅ Pre-Test Setup

- [ ] Backup current working code (if needed)
- [ ] All changes applied to [audio/pipeline.py](GUI/audio/pipeline.py)
- [ ] `close()` methods added to STT classes
- [ ] Python environment active

---

## 🧪 Test Suite

### TEST 1: Pause Stops Transcription (CRITICAL) 🔴

**Objective:** Verify NO transcriptions appear after pause

**Steps:**
1. Start GlassNote
2. Click "Start Session"
3. Click "Interview Mode" ▶️
4. Play audio or speak: "Testing one two three"
5. Verify transcriptions appear in console:
   ```
   [deepgram] flux [Update]: 'Testing one two three'
   ```
6. Click "Interview Mode" ⏸️ (pause)
7. **CRITICAL:** Continue playing audio / speaking loudly
8. Watch console for 10 seconds

**Expected Result:**
```
[pipeline] ⏸ Paused (recorder stopped, STT closed)
[NO MORE [deepgram] LOGS]
[NO MORE [openai_realtime] LOGS]
```

**Pass Criteria:**
- ✅ No `[deepgram] flux [Update]` logs after pause
- ✅ No `[openai_realtime]` logs after pause
- ✅ Audio plays but nothing transcribed

**If FAILED:**
- ❌ Transcriptions still appear → pause() not stopping recorder/STT properly
- Check: Did `close()` method get called? Add debug logs

---

### TEST 2: Resume Restarts Transcription ✓

**Objective:** Verify transcription works after resume

**Steps:**
1. Continue from Test 1 (paused state)
2. Wait 5 seconds
3. Click "Interview Mode" ▶️ (resume)
4. Wait for connection logs
5. Play audio or speak: "Resuming transcription test"

**Expected Logs:**
```
[pipeline] ▶ Resumed (recorder restarted, STT reconnected — source=system, gate=OFF)
[deepgram] Connecting flux → flux-general-en
[deepgram] flux connected ✓
[deepgram] flux session 019xxx
[deepgram] flux [Update]: 'Resuming transcription test'
```

**Pass Criteria:**
- ✅ Resume takes ~500-800ms (acceptable delay)
- ✅ Transcriptions appear after resume
- ✅ Audio flows normally

**If FAILED:**
- ❌ Resume fails → Check `_create_stt()` error handling
- ❌ No transcriptions → Check recorder.start() succeeded

---

### TEST 3: Voice Gate Conditional (System Mode) ✓

**Objective:** Voice gate should NOT run when `audio_source="system"`

**Steps:**
1. Open Settings → Audio
2. Set `audio_source = "system"`
3. Save settings
4. Start session
5. Start interview mode
6. Speak into microphone (while system audio plays or is silent)

**Expected Logs:**
```
[pipeline] Voice gate disabled for source=system
[pipeline] Dual-stream recording started  source=system  gate=OFF  ...
[NO [voice_gate] LOGS]
[NO "User started speaking" LOGS]
```

**Pass Criteria:**
- ✅ No voice gate logs
- ✅ Your speech into mic does NOT trigger "User started speaking"
- ✅ Only system audio transcribed (if playing)

**If FAILED:**
- ❌ Voice gate logs appear → Conditional logic not working

---

### TEST 4: Voice Gate Conditional (Microphone Mode) ✓

**Objective:** Voice gate SHOULD run when `audio_source="microphone"`

**Steps:**
1. Open Settings → Audio
2. Set `audio_source = "microphone"`
3. Save settings
4. Start session
5. Start interview mode
6. Speak into microphone

**Expected Logs:**
```
[voice_gate] Mic monitoring @ 48000 Hz — calibrating noise floor...
[voice_gate] Calibrated ✓  noise_floor=0.0027  threshold=0.0109
[pipeline] Dual-stream recording started  source=microphone  gate=ON  ...
[pipeline] 🎤 User started speaking — dispatch gated
[deepgram] flux [Update]: 'Your speech text'
[pipeline] 🔇 User stopped speaking — gate releasing
```

**Pass Criteria:**
- ✅ Voice gate logs appear
- ✅ "User started speaking" when you speak
- ✅ Dispatch blocked while speaking
- ✅ Dispatch releases after you stop

**If FAILED:**
- ❌ No voice gate → Check if `source == "microphone"` condition met

---

### TEST 5: Multiple Pause/Resume Cycles ✓

**Objective:** Ensure stability across multiple toggles

**Steps:**
1. Start interview mode
2. Speak: "Cycle one"
3. Pause
4. Resume (wait for reconnect)
5. Speak: "Cycle two"
6. Pause
7. Resume
8. Speak: "Cycle three"
9. Pause
10. Resume
11. Repeat 5 more times

**Expected:**
- ✅ Each pause stops transcriptions
- ✅ Each resume restarts successfully
- ✅ No errors in console
- ✅ No memory leaks (check Task Manager)
- ✅ Transcriptions accurate each cycle

**If FAILED:**
- ❌ Errors after N cycles → Memory leak or resource exhaustion
- ❌ Transcriptions degrade → Check STT reconnect logic

---

### TEST 6: Pause During Active Speech ✓

**Objective:** Pause should work even when audio is actively playing

**Steps:**
1. Start interview mode
2. Play a long audio clip (30+ seconds) or speak continuously
3. **While audio is playing** (mid-sentence), click pause
4. Let audio continue for 10 more seconds

**Expected:**
```
[deepgram] flux [Update]: 'This is a long sent...'
[pipeline] ⏸ Paused (recorder stopped, STT closed)
[NO MORE TRANSCRIPTION LOGS DESPITE AUDIO CONTINUING]
```

**Pass Criteria:**
- ✅ Pause works immediately (mid-sentence)
- ✅ No transcriptions after pause
- ✅ Can resume and continue normally

---

### TEST 7: Stereo Mix Warning (Already Tested) ✓

**Objective:** Warning appears when Stereo Mix not available

**Steps:**
1. Disable Stereo Mix in Windows
2. Set `audio_source = "system"`
3. Click "Start Session"

**Expected:**
- ✅ Warning dialog appears
- ✅ Three buttons: "Open Settings", "Continue Anyway", "Cancel"
- ✅ Instructions shown
- ✅ "Don't show again" checkbox works

**Pass Criteria:**
- ✅ Warning appears before session starts
- ✅ Can change settings or continue
- ✅ Suppression works if checkbox checked

---

### TEST 8: Settings UI Status Indicator ✓

**Objective:** Real-time Stereo Mix status shown in Settings

**Steps:**
1. Open Settings → Audio
2. Note current audio source
3. Check Stereo Mix status below dropdown

**Expected (Stereo Mix enabled):**
```
✅ Stereo Mix available: Stereo Mix (Realtek(R) Audio)
[Green text]
```

**Expected (Stereo Mix disabled):**
```
⚠️ Stereo Mix not available: No loopback device found
System audio capture will fall back to microphone.
[Orange text]
```

**Pass Criteria:**
- ✅ Status updates when changing audio source dropdown
- ✅ Hidden when "microphone" selected (not needed)
- ✅ Shown for "system" or "both"

---

### TEST 9: End Session Cleanup ✓

**Objective:** All resources released on session end

**Steps:**
1. Start interview mode
2. Let it run for 1 minute
3. Pause and resume a few times
4. Click "End Session"
5. Check Task Manager for python.exe

**Expected Logs:**
```
[llm] keepalive heartbeat stopped
[pipeline] All resources released
[app] Session ended — ...
```

**Pass Criteria:**
- ✅ All threads stopped
- ✅ WebSockets closed
- ✅ Audio devices released
- ✅ CPU usage drops to near 0%

---

## 🔍 Log Patterns to Watch

### ✅ GOOD (Fixed)
```
[pipeline] ⏸ Paused (recorder stopped, STT closed)
[pipeline] ▶ Resumed (recorder restarted, STT reconnected — source=system, gate=OFF)
[pipeline] Voice gate disabled for source=system
```

### ❌ BAD (Bug still present)
```
[pipeline] ⏸ Paused (gate closed — STT still connected)
[deepgram] flux [Update]: 'Text after pause'  ← SHOULD NOT APPEAR!
```

### ⚠️ WARNING (Check carefully)
```
[pipeline] Recorder stop error (non-fatal): ...
[pipeline] STT close error (non-fatal): ...
[pipeline] Resume failed: ...
```

---

## 📊 Performance Benchmarks

### Measure Resume Latency

**Test:**
1. Start interview mode
2. Pause
3. Note timestamp
4. Resume
5. Note timestamp when first transcription appears

**Expected:**
- Resume latency: 500-800ms
- First transcription: 500-800ms + VAD delay (~200ms) = 700-1000ms total

**Acceptable Range:** < 1.5 seconds

**If TOO SLOW (> 2 seconds):**
- Check DNS cache (may need to pre-resolve again)
- Check network latency
- Verify KeepAlive for LLM still active (shouldn't be affected)

---

## 🚨 Regression Tests

### Ensure No Regressions in Other Features

- [ ] **Solve mode** still works (capture + solve)
- [ ] **Analyze mode** still works (instant capture + analyze)
- [ ] **LLM streaming** still works
- [ ] **Session duration** countdown still works
- [ ] **Settings save** still works
- [ ] **Hotkeys** all work

---

## 🐞 Debugging Tips

### If pause still doesn't work:

1. **Check if `close()` is called:**
   ```python
   # Add debug log to pause()
   print(f"[DEBUG] Calling stt.close(), has_close={hasattr(self._stt, 'close')}")
   ```

2. **Check if recorder stops:**
   ```python
   # Add debug log
   print(f"[DEBUG] Recorder stopped: {self._recorder is None}")
   ```

3. **Check audio callback:**
   ```python
   # In recorder.py _audio_callback, add:
   print(f"[DEBUG] Audio callback fired (should not happen when paused)")
   ```

### If resume fails:

1. **Check STT creation:**
   ```python
   # Add debug log to resume()
   print(f"[DEBUG] STT created: {self._stt is not None}")
   print(f"[DEBUG] STT type: {type(self._stt)}")
   ```

2. **Check recorder restart:**
   ```python
   print(f"[DEBUG] Recorder started: {self._recorder.is_recording()}")
   ```

---

## ✅ Sign-off Checklist

Before marking as complete:

- [ ] All 9 tests passed
- [ ] No transcriptions after pause (Test 1)
- [ ] Resume works correctly (Test 2)
- [ ] Voice gate conditional (Tests 3a & 3b)
- [ ] Multiple cycles stable (Test 4)
- [ ] Pause during speech works (Test 5)
- [ ] Clean session end (Test 6)
- [ ] Stereo Mix warning works (Test 7)
- [ ] Settings status indicator works (Test 8)
- [ ] No regressions in other features
- [ ] Performance acceptable (~500-800ms resume)
- [ ] No memory leaks
- [ ] Logs show expected patterns

---

**Created:** 2026-05-03  
**Status:** Ready for testing  
**Priority:** P0 (Critical fixes)
