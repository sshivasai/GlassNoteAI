"""
Stereo Mix Detection Utility

Checks if a WASAPI loopback device (Stereo Mix) is available on Windows.
Used to warn users before starting a session if system audio capture will fail.
"""

import sys
from typing import Optional, Tuple


def check_stereo_mix_available() -> Tuple[bool, str]:
    """
    Check if a WASAPI loopback device is available for system audio capture.

    Returns:
        Tuple[bool, str]: (is_available, device_name or error_message)

    Examples:
        >>> available, info = check_stereo_mix_available()
        >>> if available:
        >>>     print(f"Found: {info}")
        >>> else:
        >>>     print(f"Error: {info}")
    """
    # Only Windows supports WASAPI loopback
    if sys.platform != "win32":
        return (False, "System audio capture is only supported on Windows")

    try:
        import sounddevice as sd
    except ImportError:
        return (False, "sounddevice library not installed")

    try:
        devices = sd.query_devices()
        loopback_keywords = [
            "stereo mix", "what u hear", "loopback",
            "wave out",   "monitor",     "mix",
            "wasapi",     "virtual",     "voicemeeter",
        ]

        for i, dev in enumerate(devices):
            # Must have input channels to be recordable
            if dev["max_input_channels"] > 0:
                device_name = dev["name"].lower()
                if any(kw in device_name for kw in loopback_keywords):
                    return (True, dev["name"])

        return (False, "No loopback device found")

    except Exception as e:
        return (False, f"Detection failed: {str(e)}")


def get_stereo_mix_instructions() -> str:
    """
    Returns user-friendly instructions for enabling Stereo Mix on Windows.

    Returns:
        str: Markdown-formatted instructions
    """
    return """**System Audio Capture Requires 'Stereo Mix'**

To capture system audio (interviewer's voice in online interviews), you need to enable the 'Stereo Mix' recording device in Windows.

**How to enable Stereo Mix:**

1. Right-click the **speaker icon** in the taskbar
2. Select **Sounds** → go to the **Recording** tab
3. Right-click in the empty space → **Show Disabled Devices**
4. Right-click **Stereo Mix** → **Enable**
5. Click **OK** and restart the application

**Note:** If you don't see 'Stereo Mix' at all:
- Your audio driver may not support it (common on laptops)
- Alternative: Use **audio_source = "microphone"** mode
  - This captures both voices through your mic (interviewer via speakers)

**After enabling:**
- Restart GlassNote
- Select **audio_source = "system"** in Settings
- Interview mode will capture system audio only
"""


def should_check_stereo_mix(audio_source: str) -> bool:
    """
    Determines if Stereo Mix check is needed based on audio source setting.

    Args:
        audio_source: "system", "microphone", or "both"

    Returns:
        bool: True if check is required (source uses system audio)
    """
    return audio_source in ("system", "both")


def get_warning_message(audio_source: str) -> str:
    """
    Returns appropriate warning message based on audio source.

    Args:
        audio_source: "system", "microphone", or "both"

    Returns:
        str: Markdown-formatted warning message
    """
    if audio_source == "system":
        return """⚠️ **Stereo Mix Not Enabled**

You've selected **System Audio** as the audio source, but Stereo Mix is not available.

**What this means:**
- Interview mode will fall back to **Microphone**
- Your mic will capture BOTH interviewer (from speakers) and your voice
- This is NOT ideal for system-only capture

**Recommended actions:**
1. Enable Stereo Mix (see instructions below)
2. OR change audio source to **Microphone** in Settings (if you're okay with both voices)
3. OR continue anyway (will use mic as fallback)
"""
    elif audio_source == "both":
        return """⚠️ **Stereo Mix Not Enabled**

You've selected **Both (System + Microphone)** as the audio source, but Stereo Mix is not available.

**What this means:**
- Only your microphone will be used (can't capture separate system audio)
- You won't get separate "INTERVIEWER" and "CANDIDATE" streams
- Dual-stream mode requires Stereo Mix to work properly

**Recommended actions:**
1. Enable Stereo Mix (see instructions below)
2. OR change audio source to **Microphone** in Settings
"""
    else:
        return ""  # Microphone-only mode doesn't need Stereo Mix


# ── Quick standalone test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Checking for Stereo Mix...")
    available, info = check_stereo_mix_available()

    if available:
        print(f"✅ Found: {info}")
    else:
        print(f"❌ Not available: {info}")
        print("\nInstructions:")
        print(get_stereo_mix_instructions())
