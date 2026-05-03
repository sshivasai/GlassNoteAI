# OpenAI STT - WebSocket vs REST API

**TL;DR:** YES, we use **WebSockets** for OpenAI STT via the **Realtime API**

---

## 🔄 Two Different OpenAI Speech-to-Text APIs

### 1️⃣ **REST API** (Batch Transcription) ❌ NOT USED

**Endpoint:** `POST https://api.openai.com/v1/audio/transcriptions`

**How it works:**
```python
# Upload complete audio file
audio_file = open("speech.mp3", "rb")
transcription = client.audio.transcriptions.create(
    model="gpt-4o-transcribe",
    file=audio_file  # ← Upload entire file
)
print(transcription.text)  # ← Get complete transcript
```

**Characteristics:**
- 📤 Upload **complete audio file** (up to 25 MB)
- ⏳ Wait for **entire transcription**
- 📝 Receive **final transcript** (no streaming)
- 💰 Charged per minute of audio

**Use case:** Pre-recorded audio files (podcasts, recordings, etc.)

**Why we DON'T use this:**
- ❌ Not real-time (need entire audio first)
- ❌ No streaming partials
- ❌ No live VAD (Voice Activity Detection)
- ❌ Not suitable for interview mode

---

### 2️⃣ **WebSocket API** (Realtime Transcription) ✅ USED IN OUR CODE

**Endpoint:** `wss://api.openai.com/v1/realtime?intent=transcription`

**How it works:**
```python
# Connect WebSocket
ws = websocket.connect("wss://api.openai.com/v1/realtime?intent=transcription")

# Send audio chunks continuously
ws.send(audio_chunk_1)
ws.send(audio_chunk_2)
ws.send(audio_chunk_3)
# ...

# Receive transcription deltas as they arrive
# No waiting for complete audio!
```

**Characteristics:**
- 🎤 Stream **audio chunks** in real-time (PCM16 @ 24 kHz)
- ⚡ Receive **partial transcripts** as user speaks
- 🎯 Server-side **VAD** (detects speech start/stop)
- 🔄 **Streaming events** (deltas, segments, completed)
- 💰 Charged per token generated

**Use case:** Live transcription (interview mode, voice calls, etc.)

**Why we USE this:**
- ✅ Real-time streaming
- ✅ Partial transcripts appear as user speaks
- ✅ Server VAD detects end-of-turn automatically
- ✅ Perfect for interview mode

---

## 🔍 Our Implementation

**Location:** [stt_openai_realtime.py](GUI/audio/stt_openai_realtime.py)

```python
# Lines 69-70
TARGET_SR    = 24_000  # OpenAI requires 24 kHz PCM16
REALTIME_URL = "wss://api.openai.com/v1/realtime?intent=transcription"
              # ^^^ WebSocket URL, not HTTPS!

class OpenAIRealtimeSTT:
    def __init__(self, api_key, ...):
        self._api_key = api_key
        # ...
    
    def start(self, native_sr: int):
        # Start WebSocket connection thread
        self._thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self._thread.start()
    
    def _run(self):
        """Main WebSocket connection loop."""
        url = REALTIME_URL  # WebSocket URL
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        # Connect WebSocket
        with ws_sync.connect(url, additional_headers=headers) as ws:
            print("[openai] Realtime STT connected ✓")
            
            # Send session config (VAD, model, etc.)
            ws.send(json.dumps({
                "type": "transcription_session.update",
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": "en"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "silence_duration_ms": 500
                }
            }))
            
            # Start sender thread (feeds audio)
            threading.Thread(
                target=self._send_loop,
                args=(ws,),
                daemon=True
            ).start()
            
            # Start receiver thread (receives transcripts)
            threading.Thread(
                target=self._receive_loop,
                args=(ws,),
                daemon=True
            ).start()
            
            # Keep WebSocket alive
            while self._running:
                time.sleep(0.1)
    
    def feed(self, pcm_int16: np.ndarray, native_sr: int):
        """Called from audio callback - queues audio for sending."""
        # Resample to 24 kHz
        resampled = resample_numpy(pcm_int16, native_sr, 24_000)
        self._audio_q.put(resampled)
    
    def _send_loop(self, ws):
        """Continuously send audio chunks to WebSocket."""
        while self._running:
            try:
                audio_chunk = self._audio_q.get(timeout=0.01)
                # Encode to base64 (WebSocket JSON format)
                audio_b64 = base64.b64encode(audio_chunk.tobytes()).decode()
                
                # Send to OpenAI
                ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }))
            except queue.Empty:
                continue
    
    def _receive_loop(self, ws):
        """Receive transcription events from WebSocket."""
        while self._running:
            try:
                message = ws.recv()
                event = json.loads(message)
                
                # Handle different event types
                if event["type"] == "conversation.item.input_audio_transcription.delta":
                    # Partial transcript delta
                    delta_text = event["delta"]
                    self._accumulated += delta_text
                    self._on_partial(self._accumulated)
                
                elif event["type"] == "input_audio_buffer.speech_stopped":
                    # Server VAD detected end of speech
                    if self._on_speech_stopped:
                        self._on_speech_stopped()
                
                elif event["type"] == "conversation.item.input_audio_transcription.completed":
                    # Final transcript for this turn
                    final_text = event["transcript"]
                    if self._on_smart_dispatch:
                        self._on_smart_dispatch(final_text)
            except Exception as e:
                print(f"[openai] Receive error: {e}")
                break
```

---

## 📊 Comparison: WebSocket (Used) vs REST (Not Used)

| Feature | REST API (`/v1/audio/transcriptions`) | WebSocket API (`/v1/realtime`) | Used? |
|---------|---------------------------------------|--------------------------------|-------|
| **Connection** | HTTP POST per file | Persistent WebSocket | ✅ WebSocket |
| **Audio input** | Complete file (25 MB max) | Streaming chunks | ✅ Streaming |
| **Latency** | High (wait for upload + processing) | Low (~100-300ms) | ✅ Low |
| **Partial results** | ❌ No | ✅ Yes (deltas) | ✅ Yes |
| **Server VAD** | ❌ No | ✅ Yes | ✅ Yes |
| **End-of-turn** | ❌ Manual | ✅ Automatic | ✅ Automatic |
| **Use case** | Pre-recorded files | Live transcription | ✅ Live |
| **Models** | whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe | gpt-4o-transcribe, gpt-4o-mini-transcribe | ✅ Both |
| **Pricing** | Per audio minute | Per token | ✅ Token-based |
| **KeepAlive** | N/A (one-shot) | Automatic (WebSocket) | ✅ Built-in |

---

## 🎯 Event Flow (Our Implementation)

```
User starts interview mode
    ↓
WebSocket connects to wss://api.openai.com/v1/realtime
    ↓
Send session config:
  • model: gpt-4o-mini-transcribe
  • input_audio_format: pcm16
  • turn_detection: server_vad (500ms silence)
  • language: en
    ↓
[WebSocket stays open, ready for audio]
    ↓
Interviewer speaks
    ↓
Audio callback fires every 21ms (1024 frames @ 48 kHz)
    ↓
feed() queues PCM chunks
    ↓
Sender thread:
  • Resample 48kHz → 24kHz
  • Encode to base64
  • Send via WebSocket:
    {"type": "input_audio_buffer.append", "audio": "..."}
    ↓
OpenAI server:
  • Receives audio stream
  • Runs server-side VAD
  • Transcribes in real-time
    ↓
Server sends events:
  1. "input_audio_buffer.speech_started"
     → User started speaking
  
  2. "conversation.item.input_audio_transcription.delta"
     → Partial transcript: "Hello"
  
  3. "conversation.item.input_audio_transcription.delta"
     → Partial transcript: "Hello, how"
  
  4. "conversation.item.input_audio_transcription.delta"
     → Partial transcript: "Hello, how are"
  
  5. "input_audio_buffer.speech_stopped"
     → Server VAD detected silence
     → Calls on_speech_stopped()
     → Pipeline locks silence clock
  
  6. "conversation.item.input_audio_transcription.completed"
     → Final transcript: "Hello, how are you?"
     → Calls on_smart_dispatch()
     → Dispatches to LLM
    ↓
LLM generates response
    ↓
User hears answer
    ↓
[WebSocket still open, ready for next question]
```

---

## 🆚 Deepgram vs OpenAI WebSocket Comparison

Both use WebSockets, but with different protocols:

### **Deepgram WebSocket**
```python
# URL
wss://api.deepgram.com/v1/listen?model=nova-3&...

# Audio format
PCM16 @ 16 kHz (binary)

# KeepAlive
{"type": "KeepAlive"}  # Every 8s for nova
ws.ping()              # Every 30s for flux

# Events
- Results (partial transcripts)
- Metadata
- SpeechStarted
- UtteranceEnd
- EndOfTurn (flux only)
```

### **OpenAI Realtime WebSocket**
```python
# URL
wss://api.openai.com/v1/realtime?intent=transcription

# Audio format
PCM16 @ 24 kHz (base64 encoded in JSON)

# KeepAlive
Built-in (no explicit KeepAlive needed)

# Events
- input_audio_buffer.speech_started
- conversation.item.input_audio_transcription.delta
- input_audio_buffer.speech_stopped
- conversation.item.input_audio_transcription.completed
```

**Key Difference:** 
- Deepgram sends raw PCM binary
- OpenAI sends base64-encoded PCM in JSON messages

---

## 💰 Pricing

### **REST API** (`/v1/audio/transcriptions`)
```
whisper-1:              $0.006 / minute
gpt-4o-transcribe:      $2.50 per 1M input tokens + $10 per 1M output tokens
gpt-4o-mini-transcribe: $1.25 per 1M input tokens + $5 per 1M output tokens
```
**Pricing model:** Per minute of audio (whisper) or per token (gpt-4o)

### **WebSocket API** (`/v1/realtime`)
```
gpt-4o-mini-transcribe: $1.25 per 1M input tokens + $5 per 1M output tokens
gpt-4o-transcribe:      $2.50 per 1M input tokens + $10 per 1M output tokens
```
**Pricing model:** Per token generated (streaming or not)

**Our usage:** We use `gpt-4o-mini-transcribe` via WebSocket for lowest cost + best latency.

---

## 🔧 Configuration in Our Code

**Where it's selected:** [settings/ui.py](GUI/settings/ui.py)

```python
# STT Provider dropdown
self.stt_provider = QComboBox()
self.stt_provider.addItems([
    "Deepgram",
    "OpenAI Realtime",  # ← This uses WebSocket
])

# OpenAI model selection (when OpenAI Realtime selected)
self.openai_stt_model = QComboBox()
self.openai_stt_model.addItems([
    "gpt-4o-mini-transcribe",  # Default - fast + cheap
    "gpt-4o-transcribe",       # Higher accuracy
])
```

**Config saved to:** `~/.glassnote/config.json`
```json
{
    "stt_provider": "openai_realtime",
    "openai_stt_model": "gpt-4o-mini-transcribe",
    "openai_api_key": "sk-..."
}
```

**Pipeline instantiation:** [pipeline.py:770-808](GUI/audio/pipeline.py#L770-L808)
```python
elif provider == "openai_realtime":
    from audio.stt_openai_realtime import OpenAIRealtimeSTT
    return OpenAIRealtimeSTT(
        api_key=openai_key,
        on_partial=self._on_partial,
        on_smart_dispatch=self._on_smart_dispatch,
        on_speech_stopped=self._on_stt_vad_stopped,
        model=model,
        language=self._language,
        silence_ms=500
    )
```

---

## 🐛 Known Limitations

### REST API Limitations (why we don't use it)
- ❌ Cannot stream live audio
- ❌ No real-time partial transcripts
- ❌ No server-side VAD
- ❌ Must upload entire file first
- ❌ High latency (seconds)

### WebSocket API Benefits (why we use it)
- ✅ Real-time streaming
- ✅ Partial transcripts as user speaks
- ✅ Server-side VAD (automatic turn detection)
- ✅ Low latency (100-300ms)
- ✅ Persistent connection (no reconnect per question)
- ✅ Perfect for interview mode

---

## 📋 Summary

| Question | Answer |
|----------|--------|
| **Do we use WebSockets for OpenAI STT?** | ✅ YES |
| **Which API?** | **Realtime API** (`/v1/realtime`) |
| **WebSocket URL** | `wss://api.openai.com/v1/realtime?intent=transcription` |
| **Audio format** | PCM16 @ 24 kHz (base64 encoded) |
| **Models supported** | gpt-4o-mini-transcribe, gpt-4o-transcribe |
| **KeepAlive needed?** | No (built-in WebSocket keep-alive) |
| **Server VAD?** | Yes (automatic end-of-turn detection) |
| **Streaming?** | Yes (delta events) |
| **Pricing** | Per token (input + output) |

---

## 🔗 References

### OpenAI Documentation
- **REST API:** https://developers.openai.com/api/docs/guides/speech-to-text
- **Realtime API:** https://developers.openai.com/api/docs/guides/realtime (WebSocket)
- **Models:** https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe

### Our Code
- **Implementation:** [stt_openai_realtime.py](GUI/audio/stt_openai_realtime.py)
- **Pipeline integration:** [pipeline.py:770-808](GUI/audio/pipeline.py#L770-L808)
- **Settings UI:** [settings/ui.py](GUI/settings/ui.py)

---

**Last Updated:** 2026-05-03  
**Status:** ✅ Fully implemented with WebSocket support for both Deepgram and OpenAI
