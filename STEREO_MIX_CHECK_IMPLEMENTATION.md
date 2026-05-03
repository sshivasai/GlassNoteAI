# Stereo Mix Detection & Warning System - Implementation Guide

**Status:** ✅ Implemented  
**Date:** 2026-05-03

---

## Overview

This implementation adds automatic Stereo Mix detection when the user creates a new session, preventing silent fallback to microphone mode and ensuring users are aware of their audio source configuration.

---

## Components Created

### 1. **Stereo Mix Checker Module** ([audio/stereo_mix_checker.py](GUI/audio/stereo_mix_checker.py))

**Purpose:** Utility functions for detecting Stereo Mix availability

**Key Functions:**
```python
def check_stereo_mix_available() -> Tuple[bool, str]:
    """
    Checks if WASAPI loopback device (Stereo Mix) is available.
    Returns: (is_available, device_name or error_message)
    """

def should_check_stereo_mix(audio_source: str) -> bool:
    """
    Returns True if audio_source requires Stereo Mix ("system" or "both")
    """

def get_warning_message(audio_source: str) -> str:
    """
    Returns appropriate warning text based on audio source.
    """

def get_stereo_mix_instructions() -> str:
    """
    Returns markdown-formatted instructions for enabling Stereo Mix.
    """
```

**Detection Logic:**
- Only runs on Windows (WASAPI loopback is Windows-only)
- Searches for keywords: "stereo mix", "what u hear", "loopback", "monitor", etc.
- Returns device name if found, error message otherwise

**Standalone Testing:**
```bash
cd GUI/audio
python stereo_mix_checker.py
```

Output:
```
Checking for Stereo Mix...
✅ Found: Stereo Mix (Realtek(R) Audio)
# OR
❌ Not available: No loopback device found
[Instructions shown]
```

---

### 2. **Warning Dialog** ([session/stereo_mix_warning_dialog.py](GUI/session/stereo_mix_warning_dialog.py))

**Purpose:** Modal dialog that warns users when Stereo Mix is not available

**Features:**
- ⚠️ Warning icon + clear title
- Context-specific warning message (different for "system" vs "both")
- Expandable instructions (how to enable Stereo Mix)
- "Don't show again" checkbox
- Three action buttons:
  - **Open Settings** → Opens Settings to change audio source
  - **Continue Anyway** → Proceeds with session (falls back to mic)
  - **Cancel** → Returns to session setup

**Dialog Flow:**
```
User clicks "Start Session" 
    ↓
Stereo Mix check fails
    ↓
[Dialog appears]
    ↓
User clicks "Open Settings" → Settings UI opens, session setup stays open
User clicks "Continue" → Session starts with mic fallback
User clicks "Cancel" → Back to session setup, no session created
```

**Standalone Testing:**
```bash
cd GUI/session
python stereo_mix_warning_dialog.py
```

---

### 3. **Session Setup Integration** ([session/setup_ui.py](GUI/session/setup_ui.py))

**Modified:** `_start_session()` method

**New Flow:**
```
┌─────────────────────────────────────────────────────────────┐
│ User clicks "Start Session"                                  │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
          ┌───────────────┐
          │ Step 0 (NEW)  │
          │ Check         │ ← audio_source = "system" or "both"?
          │ Stereo Mix    │
          └───────┬───────┘
                  ↓
          ┌───────────────┐
          │ Available?    │
          └───────┬───────┘
                  │
        ┌─────────┴─────────┐
        │                   │
       Yes                 No
        │                   │
        │           ┌───────────────┐
        │           │ Show warning  │
        │           │ dialog        │
        │           └───────┬───────┘
        │                   │
        │           ┌───────┴────────────┐
        │           │                    │
        │      "Settings"            "Continue"
        │           │                    │
        │     [Open Settings]            │
        │     [Return to setup]          │
        │                                │
        └────────────────────────────────┘
                     ↓
             Step 1: Check JWT token
             Step 2: Verify plan
             Step 3: Register session
             Step 4: Start session
```

**Code Changes:**
```python
# session/setup_ui.py line ~907
def _start_session(self):
    # ... existing setup ...
    
    # ── NEW: Step 0 - Check Stereo Mix ──
    audio_source = cfg.get("audio_source", "system")
    suppress_stereo_warning = cfg.get("suppress_stereo_mix_warning", False)

    if should_check_stereo_mix(audio_source) and not suppress_stereo_warning:
        available, info = check_stereo_mix_available()
        if not available:
            # Show warning dialog
            choice, suppress_future = show_stereo_mix_warning(...)
            
            if suppress_future:
                cfg["suppress_stereo_mix_warning"] = True
                config.save_config(cfg)
            
            if choice == "settings":
                self.open_settings.emit()
                return  # Don't start session
            elif choice == "cancel":
                return  # Don't start session
            # choice == "continue" falls through to start session
    
    # ... existing flow continues ...
```

---

### 4. **Settings UI Integration** ([settings/ui.py](GUI/settings/ui.py))

**New Feature:** Live Stereo Mix status indicator in Audio settings

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────┐
│ Audio Source                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ system  (video call — captures speaker via Stereo Mix) │ │ ← Dropdown
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ✅ Stereo Mix available: Stereo Mix (Realtek(R) Audio)      │ ← Status (green)
│                                                              │
│ OR                                                           │
│                                                              │
│ ⚠️ Stereo Mix not available: No loopback device found       │ ← Status (orange)
│ System audio capture will fall back to microphone           │
│ (captures both voices).                                     │
└─────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Updates automatically when user changes audio source dropdown
- Only shows for "system" or "both" (hidden for "microphone")
- Green ✅ if available
- Orange ⚠️ if not available with fallback explanation

**Code Changes:**
```python
# settings/ui.py line ~545
# Added after audio_source dropdown:
self._stereo_mix_status = QLabel()
self._stereo_mix_status.setWordWrap(True)
layout.addWidget(self._stereo_mix_status)
self._update_stereo_mix_status()

self.audio_source.currentIndexChanged.connect(self._update_stereo_mix_status)

# New method line ~651
def _update_stereo_mix_status(self):
    """Update Stereo Mix status based on current audio source."""
    available, info = check_stereo_mix_available()
    if available:
        self._stereo_mix_status.setText(f"✅ Stereo Mix available: {info}")
        self._stereo_mix_status.setStyleSheet("color: #059669; ...")
    else:
        self._stereo_mix_status.setText(f"⚠️ Stereo Mix not available: {info}")
        self._stereo_mix_status.setStyleSheet("color: #b45309; ...")
```

---

## Configuration Settings

### New Config Key
```json
{
    "suppress_stereo_mix_warning": false
}
```

**Purpose:** Persist user's "Don't show again" preference

**Location:** `~/.glassnote/config.json`

**Behavior:**
- Default: `false` (show warnings)
- Set to `true` when user checks "Don't show this warning again"
- Can be manually reset by editing config or via Settings UI (future enhancement)

---

## User Experience Flows

### Flow 1: First-time user with Stereo Mix disabled

```
1. User installs GlassNote
2. Sets audio_source = "system" in Settings
3. Clicks "Start Session"
   ↓
   [Warning Dialog Appears]
   
   ⚠️ Stereo Mix Not Enabled
   
   You've selected System Audio but Stereo Mix is not available.
   - Will fall back to Microphone
   - Captures BOTH voices
   
   [Instructions for enabling Stereo Mix shown]
   
   [ Open Settings ]  [ Continue Anyway ]  [ Cancel ]
   
4a. User clicks "Open Settings"
   → Settings UI opens
   → User changes to "Microphone"
   → Returns to session setup
   → Clicks "Start Session" again
   → Warning doesn't appear (mic mode doesn't need Stereo Mix)
   → Session starts ✅

4b. User clicks "Continue Anyway"
   → Session starts with mic fallback
   → Warning shown next time (unless "Don't show again" checked)

4c. User clicks "Cancel"
   → Back to session setup
   → User can fix Stereo Mix first
```

### Flow 2: User enables Stereo Mix

```
1. User sees warning dialog
2. Follows instructions to enable Stereo Mix in Windows
3. Restarts GlassNote
4. Clicks "Start Session"
   ↓
   [No warning - check passes]
   ↓
   Session starts immediately ✅
   
5. Opens Settings to verify
   → Sees: ✅ Stereo Mix available: Stereo Mix (Realtek(R) Audio)
```

### Flow 3: User on laptop without Stereo Mix support

```
1. User clicks "Start Session" with audio_source="system"
   ↓
   [Warning appears: "No loopback device found"]
   
2. User checks "Don't show this warning again"
3. Clicks "Continue Anyway"
   → Preference saved to config
   → Session starts with mic fallback
   
4. Next session: No warning shown (suppressed)
5. Settings still shows: ⚠️ Stereo Mix not available (always shown)
```

---

## Testing Checklist

### Unit Tests

- [ ] **stereo_mix_checker.py**
  ```bash
  cd GUI/audio
  python stereo_mix_checker.py
  ```
  - Verify detection works on your machine
  - Check instructions are readable

- [ ] **stereo_mix_warning_dialog.py**
  ```bash
  cd GUI/session
  python stereo_mix_warning_dialog.py
  ```
  - Verify dialog appears correctly
  - Test all three buttons
  - Check "Don't show again" returns correct flag

### Integration Tests

- [ ] **Session Setup - Stereo Mix Enabled**
  1. Enable Stereo Mix in Windows
  2. Set `audio_source = "system"`
  3. Click "Start Session"
  4. Expected: No warning, session starts immediately

- [ ] **Session Setup - Stereo Mix Disabled**
  1. Disable Stereo Mix in Windows
  2. Set `audio_source = "system"`
  3. Click "Start Session"
  4. Expected: Warning dialog appears
  5. Click "Cancel" → Should return to session setup
  6. Click "Start Session" again
  7. Click "Continue Anyway" → Session should start
  8. Check logs: Should show `[recorder] No loopback device found — falling back to mic`

- [ ] **Session Setup - Open Settings Flow**
  1. Trigger warning dialog
  2. Click "Open Settings"
  3. Expected: Settings window opens
  4. Change audio_source to "Microphone"
  5. Close Settings
  6. Click "Start Session" (no warning should appear)

- [ ] **Session Setup - Don't Show Again**
  1. Trigger warning dialog
  2. Check "Don't show this warning again"
  3. Click "Continue Anyway"
  4. Verify config: `suppress_stereo_mix_warning: true`
  5. End session, start new one
  6. Expected: No warning appears

- [ ] **Settings UI - Status Indicator**
  1. Open Settings → Audio
  2. With Stereo Mix enabled:
     - Select "system" → Should show ✅ green status
     - Select "microphone" → Status should hide
     - Select "both" → Should show ✅ green status
  3. Disable Stereo Mix in Windows
  4. Refresh Settings or restart app
  5. Select "system" → Should show ⚠️ orange warning
  6. Select "both" → Should show ⚠️ orange warning

### Edge Cases

- [ ] **Microphone-only mode never shows warning**
  - Set `audio_source = "microphone"`
  - Start session → No warning (Stereo Mix not needed)

- [ ] **Windows-only check**
  - On non-Windows systems: check returns (False, "Windows only")
  - Warning should still be informative

- [ ] **sounddevice not installed**
  - Simulate by catching ImportError
  - Should gracefully fail with message

- [ ] **Multiple audio devices**
  - Test on system with multiple Stereo Mix devices
  - Should detect first available

---

## Configuration

### Reset Warning Suppression

If user wants to see the warning again:

**Option 1: Edit config manually**
```bash
# Open config file
notepad %USERPROFILE%\.glassnote\config.json

# Find and change:
"suppress_stereo_mix_warning": true
# to:
"suppress_stereo_mix_warning": false

# Save and restart GlassNote
```

**Option 2: Add UI button (future enhancement)**
```python
# In Settings UI, add:
reset_warnings_btn = QPushButton("Reset All Warnings")
reset_warnings_btn.clicked.connect(lambda: (
    cfg.update({"suppress_stereo_mix_warning": False}),
    config.save_config(cfg)
))
```

---

## Known Limitations

1. **Windows-only Detection**
   - macOS / Linux don't have WASAPI loopback
   - Check always returns False on non-Windows
   - Warning message should guide users to use "microphone" mode

2. **Runtime Changes Not Detected**
   - If user enables Stereo Mix while app is running, status won't update
   - Solution: Add "Refresh" button in Settings or restart app

3. **Virtual Audio Devices**
   - Detects "voicemeeter" and other virtual devices
   - May show false positive if virtual device isn't properly configured

4. **Laptop Limitation**
   - Many laptop audio drivers don't support Stereo Mix
   - Users must use "microphone" mode or install virtual audio cable

---

## Future Enhancements

### 1. Auto-Refresh Status in Settings
```python
# Add refresh timer to Settings UI
self._stereo_timer = QTimer()
self._stereo_timer.timeout.connect(self._update_stereo_mix_status)
self._stereo_timer.start(5000)  # Check every 5 seconds
```

### 2. Quick Enable Button
```python
# In warning dialog, add:
btn_enable = QPushButton("Open Windows Sound Settings")
btn_enable.clicked.connect(lambda: os.system("control mmsys.cpl,,1"))
# Opens directly to Recording tab
```

### 3. Virtual Audio Cable Recommendation
```python
# In instructions, add:
if not available and platform.system() == "Windows":
    instructions += """
    
**Alternative: Virtual Audio Cable**

If your audio driver doesn't support Stereo Mix:
1. Install VB-Audio Virtual Cable (free)
2. Set it as default playback device
3. Select VB-Cable in GlassNote settings
"""
```

### 4. Reset Warnings in Settings
Add button to Settings → Advanced:
```python
btn_reset_warnings = QPushButton("Reset All Warning Dialogs")
btn_reset_warnings.clicked.connect(self._reset_warnings)

def _reset_warnings(self):
    cfg = config.load_config()
    cfg["suppress_stereo_mix_warning"] = False
    config.save_config(cfg)
    QMessageBox.information(self, "Reset", "Warning dialogs will show again.")
```

---

## Troubleshooting

### Issue: Warning appears even though Stereo Mix is enabled

**Cause:** Detection keywords don't match device name

**Solution:**
1. Check device name in Windows Sound Settings → Recording tab
2. Add device name keyword to [recorder.py:212-216](GUI/audio/recorder.py#L212-L216)
```python
keywords = [
    "stereo mix", "what u hear", "loopback",
    "wave out",   "monitor",     "mix",
    "wasapi",     "virtual",     "voicemeeter",
    "your device name here",  # ← Add here
]
```

### Issue: Dialog doesn't appear even though Stereo Mix is disabled

**Check:**
1. Config has `suppress_stereo_mix_warning: true` → Reset to `false`
2. Audio source is "microphone" → Change to "system" or "both"
3. Check logs: `[session] Stereo Mix check skipped`

### Issue: Status indicator doesn't update in Settings

**Cause:** Settings UI not refreshing after change

**Solution:**
1. Close and reopen Settings
2. OR implement auto-refresh (see Future Enhancements #1)

---

## Summary

This implementation provides:
- ✅ **Proactive detection** before session starts
- ✅ **Clear warnings** with actionable steps
- ✅ **User choice** (change settings, continue, or cancel)
- ✅ **Persistent preference** (don't show again)
- ✅ **Real-time status** in Settings UI
- ✅ **Graceful fallback** (mic mode if Stereo Mix unavailable)

**Result:** Users are always aware of their audio source configuration and won't be surprised by unexpected behavior during interviews.
