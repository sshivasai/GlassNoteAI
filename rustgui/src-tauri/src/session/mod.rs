use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionData {
    pub company: String,
    pub job_description: String,
    pub resume_text: String,
    pub extra_instructions: String,
    pub language: String,
}

#[derive(Debug, Clone)]
pub struct Session {
    pub id: String,
    pub company: String,
    pub job_description: String,
    pub resume_text: String,
    pub extra_instructions: String,
    pub language: String,
    pub started_at: DateTime<Utc>,
}

impl Session {
    pub fn new(data: SessionData) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            company: data.company,
            job_description: data.job_description,
            resume_text: data.resume_text,
            extra_instructions: data.extra_instructions,
            language: data.language,
            started_at: Utc::now(),
        }
    }

    pub fn build_system_prompt(&self) -> String {
        format!(
            r#"You are an AI assistant helping during a technical interview.

# Context
Company: {}
Job Description: {}

# Candidate Background
{}

# Instructions
{}

# Output Language
{}"#,
            self.company,
            self.job_description,
            self.resume_text,
            self.extra_instructions,
            self.language
        )
    }

    pub fn build_analyze_prompt(&self) -> String {
        let base = self.build_system_prompt();
        crate::llm::build_analyze_prompt(&base)
    }

    pub fn build_interview_prompt(&self) -> String {
        let base = self.build_system_prompt();
        crate::llm::build_interview_prompt(&base)
    }
}
