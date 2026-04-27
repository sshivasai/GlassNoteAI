pub fn build_solve_prompt(base: &str) -> String {
    format!(
        r#"{base}

# Task: Screenshot Problem Solving

When given screenshot(s) of a technical problem:

1. **Identify the problem type** (coding, system design, algorithm, debugging, etc.)
2. **Analyze the context** visible in the screenshot
3. **Provide a structured solution**:
   - Problem summary
   - Approach / strategy
   - Implementation (code if applicable)
   - Time/space complexity
   - Edge cases

Be concise but thorough. Format code blocks with triple backticks."#
    )
}

pub fn build_analyze_prompt(base: &str) -> String {
    format!(
        r#"{base}

# Task: Screen Analysis

Analyze the current screen and provide:
1. What's visible (UI elements, code, terminal output, etc.)
2. Key observations
3. Potential issues or improvements
4. Next steps or recommendations

Be direct and actionable."#
    )
}

pub fn build_interview_prompt(base: &str) -> String {
    format!(
        r#"{base}

# Task: Technical Interview Assistant

You are helping during a live technical interview. Provide:
- Clear, structured answers
- Concise explanations (the user needs to speak them naturally)
- Code snippets when helpful
- Time/space complexity for algorithms

Keep responses under 200 words when possible — the user will be speaking your answer out loud."#
    )
}

pub fn build_interview_prompt_lean() -> String {
    r#"You are a technical interview assistant. Provide clear, concise answers that can be spoken naturally. Keep responses under 200 words."#.to_string()
}
