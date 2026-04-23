"""
llm/prompts.py

System prompts for each operating mode.

Smart Answering integration
---------------------------
When smart_answering=True the audio pipeline dispatches immediately on
STT end-of-turn signal.  In that case app_controller calls
build_interview_prompt_lean() instead of build_interview_prompt() to
reduce TTFT by 100–400 ms:

  Full interview prompt  (with session context): ~400–1200 input tokens
  Lean interview prompt  (no session context)  :  ~80 input tokens
  Estimated TTFT saving with claude-haiku-4-5  : ~100–400 ms

Decision lives in app_controller._dispatch_llm() — not here.
This module only provides the strings.

Caching
-------
@functools.lru_cache on all build_* functions — repeated calls within
a session return the pre-built string in ~50 ns.
"""

import functools

BASE_SOLVE = """
You are solving a coding interview problem from a screenshot.

Return:
1. Problem type in one short phrase.
2. A brief approach explanation in 2-3 sentences.
3. Clean, optimized code in the detected language.
4. Time and space complexity.
5. Key edge cases or follow-ups.

Be correct, concise, and interview-ready. Use Markdown and code blocks only where needed. Do not add unrelated discussion.
"""

BASE_ANALYZE = """
You are analyzing a technical interview problem from a screenshot.

Return:
- Short problem restatement.
- Optimal approach with brief reasoning.
- Complete code solution.
- Time and space complexity.
- Key edge cases.

Be crisp, precise, and interview-ready. Use Markdown with a clear structure. Do not include filler text.
"""

BASE_INTERVIEW = """
You are coaching a candidate answering a live interview question.

From the transcript, return:
1. A natural spoken answer in 2-4 sentences.
2. 3-5 bullet talking points with relevant technical terms.
3. One short 30-second wrap-up.

Keep the tone confident, conversational, and easy to speak aloud. Do not sound scripted or overly verbose.
"""

BASE_INTERVIEW_LEAN = """
You are a concise interview coach.

Given a spoken interview question, return:
1. A direct 2-3 sentence answer.
2. 3 key bullet points.
3. One confident wrap-up sentence.

Be brief, natural, and easy to speak aloud. Do not add extra explanation.
"""

@functools.lru_cache(maxsize=32)
def build_solve_prompt(session_system: str) -> str:
    return f"{session_system}\n\n---\n\n{BASE_SOLVE}"

@functools.lru_cache(maxsize=32)
def build_analyze_prompt(session_system: str) -> str:
    return f"{session_system}\n\n---\n\n{BASE_ANALYZE}"

@functools.lru_cache(maxsize=32)
def build_interview_prompt(session_system: str) -> str:
    return f"{session_system}\n\n---\n\n{BASE_INTERVIEW}"

@functools.lru_cache(maxsize=1)
def build_interview_prompt_lean() -> str:
    return BASE_INTERVIEW_LEAN

def clear_prompt_cache() -> None:
    build_solve_prompt.cache_clear()
    build_analyze_prompt.cache_clear()
    build_interview_prompt.cache_clear()