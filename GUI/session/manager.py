"""
session/manager.py — Session state management with crash recovery.

Changes in this revision
------------------------
1. SessionContext now serializes to / deserializes from JSON so session
   state (company, resume, history Q&A pairs) survives app crashes.

2. SessionManager.start() saves state to ~/.glassnote/session_state.json.
   Every add_to_history() call also persists the updated history.

3. SessionManager.resume_if_exists() checks for a saved session file on
   startup and offers crash recovery.

4. SessionManager.end() deletes the session file.

5. QAPair.screenshots are NOT persisted (base64 images are too large).
   Only question_summary and answer text are saved.
"""

import os
import sys
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import config

# Session state persisted here for crash recovery
_SESSION_FILE = Path.home() / ".glassnote" / "session_state.json"


@dataclass
class QAPair:
    """A single question-answer pair from the interview session."""
    question_summary: str       # Short label (first 60 chars of transcript/screenshot hint)
    answer: str                 # Full markdown answer
    screenshots: list = field(default_factory=list)  # Base64 screenshots used (NOT persisted)


@dataclass
class SessionContext:
    """
    Holds all state for an active interview session.

    Attributes:
        resume_text (str): Parsed text from user's uploaded resume.
        job_description (str): The job description for context.
        company (str): Target company name.
        extra_prompt (str): User-specified extra instructions for this session.
        provider (str): LLM provider ('anthropic' or 'openai').
        model (str): LLM model ID (e.g. 'claude-opus-4-5').
        max_tokens (int): Max output tokens per LLM call.
        language (str): Response language (e.g. 'English', 'Hindi').
        simple_language (bool): If True, use simplified vocabulary.
        history (list[QAPair]): Conversation history for this session.
        active (bool): Whether this session is currently active.
        started_at (float): Unix timestamp when session started.
        patterns_explained (list[str]): Patterns explained in this session (avoid repeating).
    """
    resume_text: str = ""
    job_description: str = ""
    company: str = ""
    extra_prompt: str = ""
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 2048
    language: str = "English"
    simple_language: bool = False
    history: list[QAPair] = field(default_factory=list)
    active: bool = False
    started_at: float = 0.0
    id: str = ""   # Backend-assigned session UUID (obtained via /api/sessions/start)
    patterns_explained: list[str] = field(default_factory=list)  # Track explained patterns

    def build_system_prompt(self) -> str:
        """
        Build the full system prompt for the LLM based on session context.

        Combines base interview instructions with optional context from
        the user's resume, target company, job description, and custom
        instructions.

        # TTFT-OPT: cache system prompt to avoid rebuild on every dispatch
        The prompt is expensive to build (string concatenation of resume +
        JD + company). Cache the result and only rebuild when the inputs
        (resume_text, job_description, company, extra_prompt, language,
        simple_language) actually change.

        Returns:
            str: The complete system prompt string.
        """
        # ── Cache key: tuple of all inputs that affect the prompt ─────────────
        cache_key = (
            self.resume_text,
            self.job_description,
            self.company,
            self.extra_prompt,
            self.language,
            self.simple_language,
            tuple(self.patterns_explained),  # Include patterns for freshness
        )
        # Return cached value if inputs haven't changed
        if (hasattr(self, "_cached_system_prompt")
                and hasattr(self, "_cached_system_prompt_key")
                and self._cached_system_prompt_key == cache_key
                and self._cached_system_prompt is not None):
            return self._cached_system_prompt

        # ── Core persona ──────────────────────────────────────────────────────
        parts = [
            "You are GlassNote, an expert technical assistant operating in real time.",
            "Your answers must be accurate, concise, and immediately usable by a candidate mid-meeting.",
            "Always use Markdown for structure. Always use fenced code blocks (with language tag) for code.",
            "For every algorithm or data-structure problem, include Time and Space complexity.",
            "Never add filler phrases ('Great question!', 'Certainly!', 'Of course!'). Get straight to the answer.",
        ]

        # ── Candidate preferences ─────────────────────────────────────────────
        if self.simple_language:
            parts.append(
                "Use plain, simple language. Prefer everyday words over technical jargon "
                "unless the jargon is essential to the answer."
            )

        if self.language != "English":
            parts.append(f"Respond entirely in {self.language}.")

        # ── Session context ───────────────────────────────────────────────────
        if self.resume_text:
            parts.append(
                "## Candidate Background\n"
                "Use the resume below to personalise examples and frame answers "
                "around the candidate's actual experience.\n\n"
                f"{self.resume_text.strip()}"
            )

        if self.company:
            parts.append(
                f"## Target Company\n"
                f"The candidate is meeting with **{self.company}**. "
                f"Where relevant, tailor examples, system-design scale, and culture fit "
                f"to what is known about {self.company}."
            )

        if self.job_description:
            parts.append(
                "## Job Description\n"
                "Align answers with the skills and responsibilities listed below.\n\n"
                f"{self.job_description.strip()}"
            )

        if self.extra_prompt:
            parts.append(
                "## Candidate-Specified Instructions\n"
                "Follow the instructions below for this session. "
                "They may override style preferences but must not override accuracy or safety.\n\n"
                f"{self.extra_prompt.strip()}"
            )

        # ── Pattern tracking context ──────────────────────────────────────────
        if self.patterns_explained:
            parts.append(
                "## Patterns Already Explained\n"
                f"You've already explained these patterns in depth earlier this session: "
                f"{', '.join(self.patterns_explained)}. "
                f"If you use them again, just name them briefly — don't re-explain unless asked."
            )

        result = "\n\n".join(parts)

        # Store in cache
        self._cached_system_prompt     = result
        self._cached_system_prompt_key = cache_key
        return result

    def add_to_history(self, summary: str, answer: str, screenshots: list = None):
        """
        Add a Q&A pair to the session history and persist to disk.

        Args:
            summary (str): Short description of the question (truncated to 80 chars).
            answer (str): The full LLM-generated answer.
            screenshots (list, optional): Base64 screenshot strings (not persisted).
        """
        self.history.append(QAPair(
            question_summary=summary[:80],
            answer=answer,
            screenshots=screenshots or []
        ))
        # Auto-persist after each Q&A so crash recovery has latest state
        _persist_session(self)

    def mark_pattern_explained(self, pattern_name: str):
        """
        Mark a pattern as explained in this session to avoid repetition.

        Args:
            pattern_name (str): Name of the pattern (e.g., "Two-Pointer", "Dynamic Programming").
        """
        if pattern_name and pattern_name not in self.patterns_explained:
            self.patterns_explained.append(pattern_name)
            # Invalidate cached system prompt since patterns changed
            self._cached_system_prompt = None
            self._cached_system_prompt_key = None

    def extract_patterns_from_answer(self, answer: str):
        """
        Simple heuristic to extract pattern names from an LLM answer.
        Looks for common pattern names in the "Pattern Recognition" or "Primary Pattern" sections.

        Args:
            answer (str): The LLM-generated answer text.
        """
        # Common pattern names to look for
        pattern_keywords = [
            "Two-Pointer", "Two Pointer", "Sliding Window", "Fast & Slow Pointers",
            "Dynamic Programming", "DFS", "BFS", "Backtracking", "Topological Sort",
            "Binary Search", "Greedy", "Divide & Conquer", "Divide and Conquer",
            "Hash Table", "Prefix Sum", "Monotonic Stack", "Monotonic Queue",
            "Trie", "Union-Find", "Bit Manipulation", "Knapsack", "LCS", "LIS"
        ]

        for pattern in pattern_keywords:
            # Look for pattern name in context like "Primary Pattern: Two-Pointer"
            if pattern.lower() in answer.lower():
                self.mark_pattern_explained(pattern)
                break  # Only mark the first/primary pattern per answer

    def get_history_context(self) -> list[dict]:
        """
        Returns last 3 Q&A pairs as LLM message history for context.

        Returns:
            list[dict]: List of role/content dicts for LLM message history.
        """
        messages = []
        for pair in self.history[-3:]:
            messages.append({
                "role": "user",
                "content": f"[Previous question: {pair.question_summary}]"
            })
            messages.append({
                "role": "assistant",
                "content": pair.answer
            })
        return messages

    def to_dict(self) -> dict:
        """
        Serialize session to a JSON-safe dict.
        
        Screenshots are excluded from serialization (too large for disk).
        
        Returns:
            dict: JSON-serializable session state.
        """
        return {
            "resume_text":     self.resume_text,
            "job_description": self.job_description,
            "company":         self.company,
            "extra_prompt":    self.extra_prompt,
            "provider":        self.provider,
            "model":           self.model,
            "max_tokens":      self.max_tokens,
            "language":        self.language,
            "simple_language": self.simple_language,
            "active":          self.active,
            "started_at":      self.started_at,
            "id":              self.id,
            "history": [
                {
                    "question_summary": qa.question_summary,
                    "answer":           qa.answer,
                    # screenshots intentionally excluded — too large
                }
                for qa in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        """
        Deserialize session from a dict (loaded from JSON).

        Args:
            data (dict): Session state dict from disk.

        Returns:
            SessionContext: Restored session instance.
        """
        history = [
            QAPair(
                question_summary=qa.get("question_summary", ""),
                answer=qa.get("answer", ""),
                screenshots=[],
            )
            for qa in data.get("history", [])
        ]
        return cls(
            resume_text=data.get("resume_text", ""),
            job_description=data.get("job_description", ""),
            company=data.get("company", ""),
            extra_prompt=data.get("extra_prompt", ""),
            provider=data.get("provider", "anthropic"),
            model=data.get("model", "claude-haiku-4-5-20251001"),
            max_tokens=data.get("max_tokens", 2048),
            language=data.get("language", "English"),
            simple_language=data.get("simple_language", False),
            history=history,
            active=data.get("active", False),
            started_at=data.get("started_at", 0.0),
            id=data.get("id", ""),
        )


# ── Persistence helpers ───────────────────────────────────────────────────────

def _persist_session(session: SessionContext) -> None:
    """
    Write session state to disk for crash recovery.

    Args:
        session (SessionContext): The session to persist.
    """
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SESSION_FILE, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
    except Exception as e:
        print(f"[session] Persist failed (non-fatal): {e}")


def _delete_session_file() -> None:
    """Remove the persisted session file (called on clean session end)."""
    try:
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()
    except Exception as e:
        print(f"[session] Delete session file failed: {e}")


def _load_persisted_session() -> Optional[SessionContext]:
    """
    Load a previously persisted session from disk.

    Returns:
        SessionContext or None: The restored session, or None if no file exists
            or the file is corrupted/expired.
    """
    try:
        if not _SESSION_FILE.exists():
            return None
        with open(_SESSION_FILE, "r") as f:
            data = json.load(f)

        # Reject sessions older than 6 hours (stale crash recovery)
        started = data.get("started_at", 0.0)
        if started > 0 and (time.time() - started) > 6 * 3600:
            print("[session] Persisted session too old (>6h) — discarding")
            _delete_session_file()
            return None

        session = SessionContext.from_dict(data)
        session.active = True
        print(
            f"[session] ✓ Recovered session — "
            f"company={session.company!r}  "
            f"history={len(session.history)} Q&As"
        )
        return session

    except Exception as e:
        print(f"[session] Recovery failed: {e}")
        _delete_session_file()
        return None


# ── Session Manager ───────────────────────────────────────────────────────────

class SessionManager:
    """
    Manages the lifecycle of interview sessions.

    Singleton — use the module-level `manager` instance.
    """

    def __init__(self):
        self.session: Optional[SessionContext] = None

    def register_with_backend(
        self,
        company: str,
        model: str,
        proxy_url: str,
        proxy_token: str,
    ) -> tuple[bool, str, dict]:
        """
        Synchronously call /api/sessions/start on the backend.

        Called from the setup UI BEFORE emitting session_started, so any
        402 quota errors are surfaced to the user before the session opens.

        Returns:
            (success: bool, session_id: str, error_detail: dict)
            On success: (True, "<uuid>", {})
            On 402:     (False, "", {"error_code": "quota_exceeded", ...})
            On error:   (False, "", {"message": "<reason>"})
        """
        import httpx
        try:
            r = httpx.post(
                f"{proxy_url}/api/sessions/start",
                headers={"Authorization": f"Bearer {proxy_token}"},
                json={"company": company, "model": model},
                timeout=httpx.Timeout(8.0, connect=5.0),
            )
            if r.status_code == 200:
                data = r.json()
                session_id = data.get("session_id", "")
                print(f"[session] ✓ Backend session registered — id={session_id[:8]}")
                return True, session_id, {}
            elif r.status_code == 402:
                # Structured 402 body (BACKEND-3)
                try:
                    detail = r.json().get("detail", {})
                    if isinstance(detail, str):
                        detail = {"error_code": "quota_exceeded", "message": detail}
                except Exception:
                    detail = {"error_code": "quota_exceeded", "message": r.text[:200]}
                print(f"[session] ⚠ Backend session start failed (402) — quota exceeded")
                return False, "", detail
            else:
                msg = f"Backend session start failed ({r.status_code})"
                print(f"[session] ⚠ {msg}")
                return False, "", {"message": msg}
        except Exception as e:
            print(f"[session] ⚠ Backend session register error: {e}")
            return False, "", {"message": str(e), "network_error": True}

    def start(
        self,
        resume_text: str = "",
        job_description: str = "",
        company: str = "",
        extra_prompt: str = "",
        language: str = "English",
        simple_language: bool = False,
        session_id: str = "",
    ) -> SessionContext:
        """
        Start a new interview session with a pre-validated backend session ID.

        The caller (setup_ui._do_verified_start) is responsible for calling
        register_with_backend() first and passing the returned session_id here.
        This ensures 402 errors are surfaced before the session opens.

        Args:
            resume_text (str): Parsed resume text.
            job_description (str): Job description for context.
            company (str): Target company name.
            extra_prompt (str): Custom session instructions.
            language (str): Response language.
            simple_language (bool): Use simplified vocabulary.
            session_id (str): Backend-assigned session UUID (pre-validated).

        Returns:
            SessionContext: The newly created session.
        """
        cfg = config.load_config()
        provider = cfg.get("selected_provider", "anthropic")
        if provider == "anthropic":
            model = cfg.get("anthropic_model", "claude-haiku-4-5-20251001")
        elif provider == "cerebras":
            model = cfg.get("cerebras_model", "gpt-oss-120b")
        elif provider == "openrouter":
            model = cfg.get("openrouter_model", "openrouter/free")
        else:
            model = cfg.get("openai_model", "gpt-4o")

        self.session = SessionContext(
            resume_text=resume_text,
            job_description=job_description,
            company=company,
            extra_prompt=extra_prompt,
            language=language,
            simple_language=simple_language,
            provider=provider,
            model=model,
            max_tokens=cfg.get("max_tokens", 2048),
            active=True,
            started_at=time.time(),
            id=session_id or str(uuid.uuid4()),
        )
        _persist_session(self.session)
        return self.session

    def end(self):
        """End the current session and clean up persisted state."""
        self.session = None
        _delete_session_file()

    def is_active(self) -> bool:
        """Check if a session is currently active."""
        return self.session is not None and self.session.active

    def get(self) -> Optional[SessionContext]:
        """Get the current session context, or None."""
        return self.session

    def has_recoverable_session(self) -> bool:
        """
        Check if there's a crash-recoverable session on disk.

        Returns:
            bool: True if a valid session file exists.
        """
        return _SESSION_FILE.exists()

    def recover_session(self) -> Optional[SessionContext]:
        """
        Attempt to recover a session from the last crash.

        Returns:
            SessionContext or None: The recovered session, or None if recovery fails.
        """
        session = _load_persisted_session()
        if session:
            self.session = session
        return session

    def discard_recovery(self) -> None:
        """Discard the recoverable session file without restoring it."""
        _delete_session_file()


# Singleton
manager = SessionManager()