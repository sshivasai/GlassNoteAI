"""
utils/export.py — Export session history to various formats.

Supports:
  - JSON (structured data with timestamps)
  - Markdown (human-readable with formatting)
  - PDF (requires reportlab - optional)
  - Plain text (simple backup)

Usage:
    from utils.export import export_session

    export_session(
        session,
        format="markdown",
        output_path="~/Downloads/interview_2026-04-26.md"
    )
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


def export_session_json(session, output_path: str) -> bool:
    """
    Export session to JSON format.

    Args:
        session: SessionContext object
        output_path: Path to save JSON file

    Returns:
        bool: True if export succeeded
    """
    try:
        data = {
            "exported_at": datetime.now().isoformat(),
            "company": session.company,
            "started_at": datetime.fromtimestamp(session.started_at).isoformat() if session.started_at else None,
            "model": session.model,
            "provider": session.provider,
            "language": session.language,
            "history": [
                {
                    "question": qa.question_summary,
                    "answer": qa.answer,
                    "screenshot_count": len(qa.screenshots),
                }
                for qa in session.history
            ],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported session to JSON: {output_path}")
        return True

    except Exception as e:
        logger.error(f"JSON export failed: {e}", exc_info=True)
        return False


def export_session_markdown(session, output_path: str) -> bool:
    """
    Export session to Markdown format.

    Args:
        session: SessionContext object
        output_path: Path to save Markdown file

    Returns:
        bool: True if export succeeded
    """
    try:
        lines = []

        # Header
        lines.append(f"# Interview Session — {session.company or 'Untitled'}\n")
        lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if session.started_at:
            started = datetime.fromtimestamp(session.started_at).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"**Session Started:** {started}\n")

        lines.append(f"**Model:** {session.provider} / {session.model}")
        lines.append(f"**Language:** {session.language}\n")
        lines.append("---\n")

        # Q&A History
        if not session.history:
            lines.append("*No questions answered in this session.*\n")
        else:
            for idx, qa in enumerate(session.history, 1):
                lines.append(f"## Question {idx}: {qa.question_summary}\n")

                if qa.screenshots:
                    lines.append(f"*({len(qa.screenshots)} screenshot{'s' if len(qa.screenshots) > 1 else ''} attached)*\n")

                lines.append("### Answer\n")
                lines.append(f"{qa.answer}\n")
                lines.append("---\n")

        # Footer
        lines.append(f"\n*Exported from GlassNote on {datetime.now().strftime('%Y-%m-%d')}*\n")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(f"Exported session to Markdown: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Markdown export failed: {e}", exc_info=True)
        return False


def export_session_text(session, output_path: str) -> bool:
    """
    Export session to plain text format.

    Args:
        session: SessionContext object
        output_path: Path to save text file

    Returns:
        bool: True if export succeeded
    """
    try:
        lines = []

        # Header
        lines.append(f"INTERVIEW SESSION — {session.company or 'UNTITLED'}")
        lines.append("=" * 70)
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if session.started_at:
            started = datetime.fromtimestamp(session.started_at).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"Session Started: {started}")

        lines.append(f"Model: {session.provider} / {session.model}")
        lines.append(f"Language: {session.language}")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # Q&A History
        if not session.history:
            lines.append("No questions answered in this session.")
        else:
            for idx, qa in enumerate(session.history, 1):
                lines.append(f"QUESTION {idx}: {qa.question_summary}")
                lines.append("-" * 70)

                if qa.screenshots:
                    lines.append(f"[{len(qa.screenshots)} screenshot{'s' if len(qa.screenshots) > 1 else ''} attached]")
                    lines.append("")

                lines.append("ANSWER:")
                lines.append(qa.answer)
                lines.append("")
                lines.append("=" * 70)
                lines.append("")

        # Footer
        lines.append(f"Exported from GlassNote on {datetime.now().strftime('%Y-%m-%d')}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        logger.info(f"Exported session to text: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Text export failed: {e}", exc_info=True)
        return False


def export_session_pdf(session, output_path: str) -> bool:
    """
    Export session to PDF format (requires reportlab).

    Args:
        session: SessionContext object
        output_path: Path to save PDF file

    Returns:
        bool: True if export succeeded
    """
    try:
        # Try to import reportlab
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT
        except ImportError:
            logger.error("reportlab not installed. Run: pip install reportlab")
            return False

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=12,
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=6,
        )

        # Title
        story.append(Paragraph(f"Interview Session — {session.company or 'Untitled'}", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Metadata
        meta_text = f"""
        <b>Exported:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
        <b>Model:</b> {session.provider} / {session.model}<br/>
        <b>Language:</b> {session.language}
        """
        story.append(Paragraph(meta_text, styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        # Q&A History
        if not session.history:
            story.append(Paragraph("<i>No questions answered in this session.</i>", styles['Normal']))
        else:
            for idx, qa in enumerate(session.history, 1):
                # Question
                story.append(Paragraph(f"<b>Question {idx}:</b> {qa.question_summary}", heading_style))

                if qa.screenshots:
                    story.append(Paragraph(
                        f"<i>({len(qa.screenshots)} screenshot{'s' if len(qa.screenshots) > 1 else ''} attached)</i>",
                        styles['Normal']
                    ))

                # Answer
                story.append(Paragraph("<b>Answer:</b>", styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))

                # Split answer into paragraphs
                for para in qa.answer.split('\n\n'):
                    if para.strip():
                        # Escape HTML entities
                        para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        story.append(Paragraph(para, styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))

                story.append(Spacer(1, 0.2 * inch))

        # Footer
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(
            f"<i>Exported from GlassNote on {datetime.now().strftime('%Y-%m-%d')}</i>",
            styles['Normal']
        ))

        doc.build(story)
        logger.info(f"Exported session to PDF: {output_path}")
        return True

    except Exception as e:
        logger.error(f"PDF export failed: {e}", exc_info=True)
        return False


def export_session(
    session,
    format: str = "markdown",
    output_path: Optional[str] = None,
    auto_name: bool = True,
) -> Optional[str]:
    """
    Export session to file.

    Args:
        session: SessionContext object
        format: Export format (json, markdown, text, pdf)
        output_path: Optional output path. If None, auto-generates.
        auto_name: If True, auto-generate filename with timestamp

    Returns:
        Optional[str]: Path to exported file, or None on failure
    """
    # Validate format
    valid_formats = {"json", "markdown", "md", "text", "txt", "pdf"}
    format_lower = format.lower()

    if format_lower not in valid_formats:
        logger.error(f"Invalid format: {format}. Valid: {valid_formats}")
        return None

    # Normalize format
    if format_lower == "md":
        format_lower = "markdown"
    elif format_lower == "txt":
        format_lower = "text"

    # Auto-generate output path
    if output_path is None or auto_name:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)

        company_slug = session.company.replace(" ", "_").lower() if session.company else "untitled"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        extensions = {
            "json": "json",
            "markdown": "md",
            "text": "txt",
            "pdf": "pdf",
        }

        ext = extensions.get(format_lower, "txt")
        filename = f"interview_{company_slug}_{timestamp}.{ext}"
        output_path = str(downloads / filename)

    # Ensure parent directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Export based on format
    exporters = {
        "json": export_session_json,
        "markdown": export_session_markdown,
        "text": export_session_text,
        "pdf": export_session_pdf,
    }

    exporter = exporters.get(format_lower)
    if exporter is None:
        logger.error(f"No exporter for format: {format}")
        return None

    success = exporter(session, output_path)

    if success:
        return output_path
    else:
        return None
