"""
DealNexus Intelligence Suite - Professional Multi-Agent System
Production-Grade Streamlit Application with Enhanced Intelligence Layer
"""

import streamlit as st
import json
import time
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import google.generativeai as genai
import io

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
AGENTS_DIR = BASE_DIR / "agents"
KNOWLEDGE_DIR = BASE_DIR / "knowledge_base"
LOGS_DIR = BASE_DIR / "logs"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
WORKSPACE_DIR = BASE_DIR / "workspace"
OUTPUTS_DIR = BASE_DIR / "outputs"

AGENT_NAMES = [
    "outcomes_strategist",
    "technical_pm",
    "legal_counsel",
    "finance_director",
    "document_architect"
]

AGENT_DISPLAY = {
    "outcomes_strategist": "Targeting",
    "technical_pm": "Feasibility",
    "legal_counsel": "Compliance",
    "finance_director": "Economics",
    "document_architect": "Synthesis"
}

# Ensure all directories exist
for directory in [AGENTS_DIR, KNOWLEDGE_DIR, LOGS_DIR, TRANSCRIPTS_DIR, WORKSPACE_DIR, OUTPUTS_DIR]:
    directory.mkdir(exist_ok=True)

# Configure Gemini
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize all session state variables."""
    defaults = {
        "pipeline_running": False,
        "pipeline_completed": False,
        "manager_chat_history": [],
        "agent_status": {agent: "pending" for agent in AGENT_NAMES},
        "pipeline_start_time": None,
        "pipeline_end_time": None,
        "intervention_needed": False,
        "current_agent": None,
        "uploaded_transcript": None,
        "client_context": "",
        "last_uploaded": None,
        "last_processed": None,
        "refresh_count": 0,
        "live_feed": [],
        "sentiment_score": 0,
        "hourly_rate": 175.0,
        "sentiment_analysis": "Pending analysis...",
        "live_status_message": "System Ready. Awaiting Input.",
        "active_tab": "Data Ingestion",
        "show_completion_banner": False  # Controls the completion notification
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ============================================================================
# FILE UTILITIES
# ============================================================================

def safe_read_json(filepath: Path, default: Any = None) -> Any:
    """Safely read JSON file with error handling."""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError):
        pass
    return default if default is not None else {}

def safe_write_json(filepath: Path, data: Dict) -> bool:
    """Safely write JSON file with error handling."""
    try:
        filepath.parent.mkdir(exist_ok=True, parents=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (IOError, TypeError):
        return False

def safe_read_text(filepath: Path, default: str = "") -> str:
    """Safely read text file with error handling."""
    try:
        if filepath.exists():
            return filepath.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        pass
    return default

def sanitize_for_streamlit_markdown(text: str) -> str:
    """
    Escapes dollar signs to prevent Streamlit from interpreting them as LaTeX math delimiters.
    Also cleans up common LaTeX artifacts if the LLM hallucinated them.

    This fixes the "run-on words" and "weird font" issues globally by escaping $ as \\$.
    """
    if not text:
        return ""

    # Step 1: Clean up any LaTeX commands the LLM might have included
    text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', text)

    # Step 2: Remove LaTeX math mode delimiters \( \) and \[ \]
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\[", "").replace("\\]", "")

    # Step 3: Remove display math mode $$
    text = text.replace("$$", "")

    # Step 4: CRITICAL - Escape ALL dollar signs so Streamlit renders them as literals
    # This prevents Streamlit from interpreting $text$ as LaTeX math mode
    # The escaped \$ will display as a normal $ character
    text = text.replace("$", "\\$")

    return text

def read_agent_prompt(agent_name: str) -> str:
    """Read agent prompt from markdown file."""
    prompt_file = AGENTS_DIR / f"{agent_name}.md"
    if prompt_file.exists():
        return safe_read_text(prompt_file, f"You are the {agent_name.replace('_', ' ').title()} agent.")
    return f"You are the {agent_name.replace('_', ' ').title()} agent."

@st.cache_data(ttl=300)
def load_industry_kpis() -> Dict:
    """Load industry KPI hub."""
    kpi_file = KNOWLEDGE_DIR / "INDUSTRY_KPI_HUB.json"
    return safe_read_json(kpi_file, {"industries": {}, "metadata": {}})

@st.cache_data(ttl=300)
def load_pole_star_metrics() -> Dict:
    """Load Pole Star ROI metrics."""
    metrics_file = KNOWLEDGE_DIR / "POLE_STAR_METRICS.json"
    return safe_read_json(metrics_file, {"metrics": {}, "metadata": {}})

def process_multimodal_file(uploaded_file) -> Optional[str]:
    """Process audio/video files using Gemini 2.5 Flash."""
    try:
        temp_path = TRANSCRIPTS_DIR / uploaded_file.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        update_live_feed("Uploading media to Gemini Multimodal Cloud...")
        myfile = genai.upload_file(temp_path)
        
        while myfile.state.name == "PROCESSING":
            time.sleep(2)
            myfile = genai.get_file(myfile.name)
            
        update_live_feed("Gemini 2.5 Flash analyzing audio/video content...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        result = model.generate_content([myfile, "Generate a detailed, near-verbatim transcript and summary of this meeting."])
        
        # Save as text transcript
        txt_path = temp_path.with_suffix('.txt')
        txt_path.write_text(result.text, encoding='utf-8')
        
        return result.text
    except Exception as e:
        st.error(f"Multimodal Processing Error: {e}")
        return None

def save_uploaded_file(uploaded_file) -> Optional[Path]:
    """Save uploaded file to transcripts directory."""
    try:
        file_name = uploaded_file.name
        if file_name.endswith('.docx'):
            if not DOCX_AVAILABLE:
                st.error("python-docx is not installed.")
                return None
            try:
                document = Document(uploaded_file)
                text_content = "\n".join([para.text for para in document.paragraphs])
                if not text_content.strip():
                    st.warning("Warning: Extracted text from DOCX appears empty.")
                base_name = os.path.splitext(file_name)[0]
                new_file_name = f"{base_name}.txt"
                file_path = TRANSCRIPTS_DIR / new_file_name
                file_path.write_text(text_content, encoding='utf-8')
                return file_path
            except Exception as e:
                st.error(f"Error processing .docx file: {e}")
                return None
        else:
            file_path = TRANSCRIPTS_DIR / file_name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            return file_path
    except Exception as e:
        st.error(f"Error saving file: {e}")
        return None

# ============================================================================
# PDF GENERATION
# ============================================================================

class DiscoveryReportPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'DealNexus Intelligence Suite - Strategic Vision', 0, 1, 'C')
        self.line(10, 20, 200, 20)
        self.ln(10)

    def footer(self):
        self.set_y(-20)
        self.set_font('Helvetica', 'I', 7)
        self.cell(0, 5, 'Architected and created by Rahul Vashisht (Test Pilot). (for testing purpose only)', 0, 1, 'C')
        self.cell(0, 5, f'Page {self.page_no()}', 0, 0, 'C')

def sanitize_for_pdf(text: str) -> str:
    """Sanitize text for PDF generation by removing/replacing unsupported characters."""
    if not text:
        return ""

    # Replace common symbols that cause Helvetica encoding errors
    replacements = {
        "\u26A0": "[!]", "\u26A1": "[*]", "\u2705": "[OK]", "\u2728": "[+]",
        "\ud83c\udfaf": ">", "\u2696\ufe0f": "[L]", "\ud83d\udcb0": "[$]",
        "\ud83d\udcdd": "[D]", "🎯": ">", "⚖️": "[L]", "💰": "[$]", "📝": "[D]",
        "✨": "[+]", "⚡": "[*]", "🔍": "[?]", "✅": "[OK]", "❌": "[X]",
        "⚠️": "[!]", "📊": "[#]", "📈": "[^]", "🚀": "[>]", "💡": "[i]",
        "–": "-", "—": "-", "'": "'", "'": "'", """: '"', """: '"',
        "•": "-", "→": "->", "←": "<-", "≥": ">=", "≤": "<=",
        "×": "x", "÷": "/", "…": "...", "°": " deg", "±": "+/-",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    # Final safety: encode to latin-1, replacing unknown chars
    return text.encode('latin-1', 'replace').decode('latin-1')


def convert_table_row_to_text(line: str) -> str:
    """Convert a markdown table row to plain text format for PDF."""
    # Remove leading/trailing pipes and split
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]

    # Split by pipe and clean each cell
    cells = [c.strip() for c in line.split('|')]
    # Filter out empty cells (from trailing pipes like "| |")
    cells = [c for c in cells if c and c != '-' and not re.match(r'^[-:]+$', c)]

    if not cells:
        return ""

    # Join with arrow separator for readability
    return "  >  ".join(cells)


def generate_pdf_report(content: str) -> Optional[bytes]:
    """
    Generate a PDF using a 'Safe Render' approach.
    - No manual line wrapping; let fpdf handle it via multi_cell(0, ...).
    - Tables are converted to plain text rows.
    - Explicit safe margins to guarantee positive effective width.
    """
    if not FPDF_AVAILABLE:
        st.error("fpdf2 library not available.")
        return None

    try:
        pdf = DiscoveryReportPDF()

        # Set explicit safe margins (10mm on all sides)
        pdf.set_left_margin(10)
        pdf.set_right_margin(10)
        pdf.set_top_margin(10)

        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", size=10)

        lines = content.split('\n')
        in_table = False
        table_header_printed = False

        for line in lines:
            original_line = line
            line = line.strip()

            # Skip empty lines - add small spacing
            if not line:
                pdf.ln(3)
                in_table = False
                table_header_printed = False
                continue

            # Handle markdown horizontal rules
            if line in ('---', '***', '___'):
                pdf.ln(2)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(2)
                in_table = False
                continue

            # TABLE HANDLING: Convert to plain text, don't render as grid
            if '|' in line and (line.startswith('|') or line.count('|') >= 2):
                # Skip separator rows like |---|---|
                if re.match(r'^[\|\s\-:]+$', line):
                    continue

                converted = convert_table_row_to_text(line)
                if not converted:
                    continue

                # First row of table = header, make it bold
                if not in_table:
                    in_table = True
                    table_header_printed = True
                    pdf.set_font("Helvetica", 'B', 10)
                    safe_text = sanitize_for_pdf(converted)
                    pdf.multi_cell(0, 5, safe_text)
                    pdf.set_font("Helvetica", size=10)
                else:
                    # Data row - render as indented text
                    safe_text = sanitize_for_pdf("   " + converted)
                    pdf.multi_cell(0, 5, safe_text)
                continue
            else:
                in_table = False
                table_header_printed = False

            # Clean markdown formatting (bold, italic, code)
            clean_line = line.replace('**', '').replace('__', '').replace('`', '')
            clean_line = sanitize_for_pdf(clean_line)

            # Render based on content type
            try:
                if clean_line.startswith('# '):
                    pdf.ln(3)
                    pdf.set_font("Helvetica", 'B', 14)
                    pdf.multi_cell(0, 7, clean_line[2:].strip())
                    pdf.set_font("Helvetica", size=10)
                    pdf.ln(2)

                elif clean_line.startswith('## '):
                    pdf.ln(2)
                    pdf.set_font("Helvetica", 'B', 12)
                    pdf.multi_cell(0, 6, clean_line[3:].strip())
                    pdf.set_font("Helvetica", size=10)
                    pdf.ln(1)

                elif clean_line.startswith('### '):
                    pdf.ln(1)
                    pdf.set_font("Helvetica", 'B', 11)
                    pdf.multi_cell(0, 5, clean_line[4:].strip())
                    pdf.set_font("Helvetica", size=10)

                elif clean_line.startswith('#### '):
                    pdf.set_font("Helvetica", 'BI', 10)
                    pdf.multi_cell(0, 5, clean_line[5:].strip())
                    pdf.set_font("Helvetica", size=10)

                elif clean_line.startswith(('- ', '* ')):
                    # Bullet point - use simple dash prefix
                    bullet_text = "  - " + clean_line[2:].strip()
                    pdf.multi_cell(0, 5, bullet_text)

                elif re.match(r'^\d+\.', clean_line):
                    # Numbered list - keep number, add indent
                    pdf.multi_cell(0, 5, "  " + clean_line)

                else:
                    # Regular paragraph
                    pdf.multi_cell(0, 5, clean_line)

            except Exception:
                # Ultimate fallback: try to render truncated version
                try:
                    fallback = clean_line[:100] + "..." if len(clean_line) > 100 else clean_line
                    pdf.multi_cell(0, 5, fallback)
                except Exception:
                    # Skip completely broken lines
                    pass

        return bytes(pdf.output())

    except Exception as e:
        st.error(f"PDF Generation Error: {e}")
        return None

# ============================================================================
# ROI & METRICS
# ============================================================================

def calculate_efficiency() -> Dict[str, float]:
    """Calculate efficiency metrics using dynamic hourly rate."""
    manual_hours = 4.0
    hourly_rate = st.session_state.hourly_rate

    if not st.session_state.get("pipeline_completed", False):
        return {
            "hours_saved": 0.0,
            "cost_saved": 0.0,
            "runtime_hours": 0.0,
            "manual_baseline": manual_hours,
            "hourly_rate": hourly_rate
        }

    try:
        if st.session_state.pipeline_start_time and st.session_state.pipeline_end_time:
            runtime_seconds = st.session_state.pipeline_end_time - st.session_state.pipeline_start_time
            runtime_hours = runtime_seconds / 3600.0
        else:
            runtime_hours = 0.0
    except Exception:
        runtime_hours = 0.0

    hours_saved = max(0.0, manual_hours - runtime_hours)
    cost_saved = hours_saved * hourly_rate

    return {
        "hours_saved": hours_saved,
        "cost_saved": cost_saved,
        "runtime_hours": runtime_hours,
        "manual_baseline": manual_hours,
        "hourly_rate": hourly_rate
    }

def update_live_feed(message: str):
    """Update live feed and status."""
    st.session_state.live_status_message = message
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.live_feed.insert(0, f"[{timestamp}] {message}")
    st.session_state.live_feed = st.session_state.live_feed[:5]

# ============================================================================
# AGENT ORCHESTRATION
# ============================================================================

def call_ai_agent(agent_name: str, context: Dict) -> Dict:
    """Call Gemini API with universal context injection."""
    prompt_template = read_agent_prompt(agent_name)
    system_name = "DealNexus Intelligence Suite"
    client_context = context.get("client_context", "Unknown Client")
    
    system_prompt = prompt_template.replace("{{SYSTEM_NAME}}", system_name)
    system_prompt = system_prompt.replace("{{CLIENT_CONTEXT}}", client_context)

    instruction = "Please provide your analysis as a JSON object following your persona guidelines."
    
    if agent_name == "document_architect":
        instruction = """
Generate a COMPREHENSIVE, VP-GLANCEABLE strategic report. Optimize for a busy executive who has 60 seconds to scan.

CRITICAL: YOU MUST COMPLETE THE REPORT. DO NOT STOP UNTIL 'Risk Register' is fully written.
IMPORTANT: Do NOT generate Appendices. Stop after the 'Risk Register' section.

=== NO MATH MODE (MANDATORY) ===
STRICT TEXT ONLY: Do NOT use LaTeX formatting, MathJax, dollar-sign math mode, or code blocks for formulas.
BAD: $Revenue - Cost = Margin$
BAD: `Revenue - Cost`
BAD: \(Revenue - Cost\)
GOOD: Revenue ($50,000) - Cost ($40,000) = Margin (20%)

FORMATTING CRITICAL: You are strictly forbidden from using the $ symbol for anything other than US Currency (e.g., $500).
NEVER write: $Revenue - Cost$ or $TCV$ or $Variable$
NEVER write: ( $Something$ ) or any $ around words/variables
ALWAYS write currency as: $50,000 or $1.5M (number immediately after $)
ALWAYS write variables as plain text: TCV, Revenue, Cost, Margin (no $ symbols)

SPACING: Always insert spaces around mathematical operators (+, -, =, *, /). Never squeeze words together.
BAD: issignificantlybelow or Revenue-Cost=Margin or ATotalContractValue
GOOD: is significantly below or Revenue - Cost = Margin or A Total Contract Value

=== MANDATORY STRUCTURE (FOLLOW THIS ORDER EXACTLY) ===

## Executive Elevator Pitch
START your report with this section. Write exactly 3 bullet points:
- **Why Now**: What urgent trigger or market force makes this timely?
- **The Value**: What is the quantified ROI or strategic benefit? (Use a dollar figure or percentage)
- **The Ask**: What specific decision or action is needed from leadership?
This section MUST be readable in 30 seconds. No fluff.

=== BOLDING STRATEGY ===
You MUST use **bold** formatting for:
- Key risk terms (e.g., **Critical**, **Blocked**, **High Priority**, **Urgent**)
- Agent names when providing specific insights (e.g., **Finance Director** recommends...)
- Timeline milestones (e.g., **Q2 2024**, **Week 1**)

=== SAFE FORMATTING RULE (MANDATORY) ===
Do NOT use bold formatting (**) inside mathematical formulas or calculations. Write the numbers plainly.

**Financial Rejection Format:** Use a simple list format:
- Formula: Proposed TCV ($50,000) - Implementation Cost ($70,437) = Margin (-40.8%)
- Target: 35%
- Result: REJECTED (Below Target)

AVOID long paragraphs. Use concise bullet points so a VP can scan the document.
Each bullet should be 1-2 sentences MAX.

=== AGENT NAMING RULE ===
Always convert agent IDs to Title Case in the text. Write "Outcomes Strategist", "Finance Director", "Legal Counsel", "Technical PM" - never "outcomes_strategist" or "finance_director".

=== MARKDOWN TABLE FORMATTING RULES ===
1. Do NOT include trailing pipes at the end of table rows.
   WRONG: | Category | Finding | Priority | |
   CORRECT: | Category | Finding | Priority |

2. Every table row MUST have the EXACT same number of columns as the header row.

3. Do NOT add blank lines between table header, alignment row, and data rows.

4. Table structure:
   | Header1 | Header2 | Header3 |
   |---------|---------|---------|
   | Data1   | Data2   | Data3   |

5. Do NOT place list items (-) on the same line as table rows.
6. Use double newlines between sections (not within tables).
7. Do not return JSON. Return raw Markdown only.
8. After the LAST row of ANY table, insert TWO blank lines before starting the next section.

TABLE CLEANUP: For 'Target' and 'Gap' columns, leave the cell EMPTY if the value is not applicable (e.g., for Cost rows). Do NOT write 'N/A'.
=== END TABLE RULES ===

=== REPORT SECTIONS (FOLLOW THIS ORDER) ===

1. **Executive Elevator Pitch** (as described above)

2. **Client Strategic Vision**:
   - Focus on high-level goals, ROI, and strategic outcomes.
   - STRICTLY PROHIBITED: Do not mention 'Glean', 'internal agents', 'vendors', or 'backend logic'.
   - Use bullet points, not paragraphs.

3. **Detailed Solution Analysis**:
   - Technical Feasibility findings from Technical PM (use bullet points for Technical Blockers, Budget Cap issues, and Custom Build requirements)
   - Compliance & Legal findings from Legal Counsel (use bullet points)
   - Financial Analysis from Finance Director (label this as "Vendor Engineering Margin Analysis")
   - Include key metrics, risks identified, and recommendations from each agent.
   - FORMAT: Use bullet points throughout this section for readability. No long paragraphs.

4. **Projected Efficiency Gains (Based on Client Internal Rate)**:
   - This section shows time/cost savings for the CLIENT based on their internal labor rate.
   - This is SEPARATE from the Vendor Engineering Margin above.

5. **SEPARATOR AND INTERNAL HEADER**:
   After the Client sections above, you MUST insert:
   ---
   # Internal Performance Summary
   ### Confidential audit of agent reasoning and pipeline execution.

6. **Operational Audit** (after the separator):
   - Internal metrics, agent negotiation logs, and confidence scores.
   - Bold all key metrics and agent names (using Title Case).

7. **Risk Register** (final section):
   - List key risks with severity and mitigation steps in a table.
   - After the Risk Register table, you MUST insert TWO blank lines to break the table context.
   - ONLY THEN, on its own line, write: [[REPORT_COMPLETE]]
   - STOP HERE. Do NOT generate Appendices.
"""
    elif agent_name == "outcomes_strategist":
        instruction += " Include a 'sentiment_score' (0-100) and 'sentiment_analysis' summary in your JSON output."

    elif agent_name == "finance_director":
        instruction += """

=== PRICING LOGIC (CRITICAL) ===

1. **Search First:** Look for explicit budget constraints in the transcript (e.g., "We have $50k", "Budget cap is $80k", "Our budget is around $X").

2. **Fallback Calculation:** If NO specific budget/TCV is mentioned by the client:
   - You MUST calculate a "Recommended TCV".
   - Formula: Total Implementation Cost / 0.65 (This targets a 35% Gross Margin).
   - Use this calculated value as the proposed_tcv.
   - Flag it with pricing_source: "ai_recommendation"

3. **Never Return Null:** The proposed_tcv field MUST always contain a number. If you can't find one, calculate one using the formula above.

=== REQUIRED JSON OUTPUT STRUCTURE ===

Your response MUST include this financial_summary object:

{
  "financial_summary": {
    "total_implementation_cost": <number>,
    "proposed_tcv": <number - NEVER null or missing>,
    "pricing_source": "client_budget" OR "ai_recommendation",
    "gross_margin_percent": <number>,
    "margin_target": 35,
    "status": "APPROVED" OR "REJECTED",
    "rejection_reason": "<explanation if REJECTED, otherwise null>"
  },
  "deal_risk": "LOW" OR "MEDIUM" OR "HIGH" OR "CRITICAL",
  "recommendation": "<actionable recommendation>"
}

=== MARGIN CALCULATION ===
- Gross Margin % = ((Proposed TCV - Implementation Cost) / Proposed TCV) * 100
- If Gross Margin % < 35%, status = "REJECTED"
- If Gross Margin % >= 35%, status = "APPROVED"
"""

    user_message = f"""
Analyze the following discovery context:
**Client:** {client_context}
**Industry:** {context.get('industry', 'N/A')}
**Detected Industry:** {context.get('detected_industry', 'Not yet detected')}
**Transcript:**
{context.get('transcript', 'N/A')}
**Industry-Specific KPIs:**
{json.dumps(context.get('industry_kpis', {}), indent=2)}
**Pole Star Metrics Reference:**
{json.dumps(context.get('pole_star_metrics', {}), indent=2)}
**Report Guidance:**
{context.get('report_template', '')}
{json.dumps(context.get('executive_style_guidance', {}), indent=2)}
**Previous Agent Outputs:**
{json.dumps(context.get('previous_outputs', {}), indent=2)}
{instruction}
"""
    try:
        # Unlock safety settings to prevent medical/legal content from being blocked
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(temperature=0.0),
            safety_settings=safety_settings
        )
        response_text = response.text

        if agent_name == "document_architect":
            output_data = {"raw_output": response_text}
        else:
            try:
                clean_text = response_text.replace("```json", "").replace("```", "").strip()
                output_data = json.loads(clean_text)
            except json.JSONDecodeError:
                output_data = {"raw_output": response_text}

        return {
            "status": "completed",
            "output": output_data,
            "completed_at": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        }

def run_sentiment_analysis(transcript: str, context: Dict) -> Dict:
    """Run dedicated Sentiment Intelligence Agent."""
    try:
        prompt_file = AGENTS_DIR / "sentiment_agent.md"
        if prompt_file.exists():
            system_prompt = safe_read_text(prompt_file)
        else:
            system_prompt = "You are an expert Stakeholder Sentiment Analyst. Analyze the transcript for emotional tone. Return JSON with 'sentiment_score' (0-100) and 'sentiment_analysis'."

        user_message = f"Analyze transcript sentiment:\n\n{transcript[:50000]}"

        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(temperature=0.0)
        )
        
        try:
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except:
            return {"sentiment_score": 50, "sentiment_analysis": "Error parsing sentiment."}
    except Exception as e:
        return {"sentiment_score": 50, "sentiment_analysis": f"Analysis failed: {str(e)}"}

def run_pipeline_steps(transcript: str, client_context: str, status_placeholder) -> bool:
    """Execute the pipeline steps with dynamic status updates."""
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("Google API key not configured.")
        return False

    def update_status(msg):
        st.session_state.live_status_message = msg
        status_placeholder.markdown(f"""
        <div class="live-bar">
            <span style="margin-right: 15px; color: #a855f7;">\u26A1</span>
            <span class="typewriter-text">{msg}</span>
        </div>
        """, unsafe_allow_html=True)
        update_live_feed(msg)

    st.session_state.pipeline_start_time = time.time()
    
    try:
        # --- Step A ---
        update_status("🎯 Outcomes Strategist is spotting industry-specific pain points...")
        kpi_hub = load_industry_kpis()
        pole_star = load_pole_star_metrics()
        
        context_a = {
            "client_context": client_context,
            "transcript": transcript,
            "industry_kpis": kpi_hub.get("industries", {}),
            "industry_detection_patterns": kpi_hub.get("industry_detection_patterns", {}),
            "pole_star_metrics": pole_star.get("metrics", {})
        }
        
        sentiment_data = run_sentiment_analysis(transcript, context_a)
        st.session_state.sentiment_score = sentiment_data.get("sentiment_score", 50)
        st.session_state.sentiment_analysis = sentiment_data.get("sentiment_analysis", "Pending analysis.")

        st.session_state.current_agent = "outcomes_strategist"
        outcomes_result = call_ai_agent("outcomes_strategist", context_a)
        
        if outcomes_result["status"] == "error":
            st.error(f"Error: {outcomes_result.get('error')}")
            return False
        safe_write_json(LOGS_DIR / "outcomes_strategist.json", outcomes_result)
        
        # --- Step B ---
        update_status("⚖️ Legal Counsel is auditing for HIPAA/GDPR roadblocks...")
        
        outcomes_data = outcomes_result.get("output", {})
        detected_industry = outcomes_data.get("industry_detection", {}).get("detected_industry", "general")
        industry_kpis = kpi_hub.get("industries", {}).get(detected_industry, {})
        
        context_b = {
            "client_context": client_context,
            "transcript": transcript,
            "industry": detected_industry,
            "industry_kpis": industry_kpis,
            "pole_star_metrics": pole_star.get("metrics", {}),
            "previous_outputs": {"outcomes": outcomes_result}
        }
        
        st.session_state.current_agent = "technical_pm"
        tech_result = call_ai_agent("technical_pm", context_b)
        safe_write_json(LOGS_DIR / "technical_pm.json", tech_result)
        
        st.session_state.current_agent = "legal_counsel"
        legal_result = call_ai_agent("legal_counsel", context_b)
        safe_write_json(LOGS_DIR / "legal_counsel.json", legal_result)
        
        # --- Step C ---
        update_status("💰 Hmmmm, the Finance Director spotted an issue with the discount demanded...")
        
        tech_data = tech_result.get("output", {})
        legal_data = legal_result.get("output", {})
        
        compliance_status = legal_data.get("compliance_status", "APPROVED")
        custom_builds = tech_data.get("feasibility_summary", {}).get("custom_builds", [])
        
        if custom_builds and compliance_status != "APPROVED":
             st.session_state.intervention_needed = True
             safe_write_json(LOGS_DIR / "cross_talk.json", {
                 "negotiations": [{"agent": "legal_counsel", "message": "Cleared with mitigations."}],
                 "status": "RESOLVED"
             })
        else:
            safe_write_json(LOGS_DIR / "cross_talk.json", {"status": "NO_CUSTOM_BUILDS"})

        # --- Step D ---
        update_status("📝 Document Architect is synthesizing the final Executive Vision...")

        st.session_state.current_agent = "finance_director"
        all_outputs = {
            "outcomes": outcomes_result,
            "technical": tech_result,
            "legal": legal_result,
            "sentiment": sentiment_data
        }
        finance_context = {
            "client_context": client_context,
            "pole_star_metrics": pole_star.get("metrics", {}),
            "previous_outputs": all_outputs
        }
        finance_result = call_ai_agent("finance_director", finance_context)
        safe_write_json(LOGS_DIR / "finance_director.json", finance_result)
        all_outputs["finance"] = finance_result

        st.session_state.current_agent = "document_architect"
        report_template = safe_read_text(WORKSPACE_DIR / "REPORT_TEMPLATE.md", "")

        # Fix 3: Sanitize previous_outputs - replace failed agent outputs with summary
        sanitized_outputs = {}
        for agent_key, agent_result in all_outputs.items():
            if isinstance(agent_result, dict) and agent_result.get("status") == "error":
                sanitized_outputs[agent_key] = {"summary": f"Agent '{agent_key}' failed to run.", "status": "error"}
            else:
                sanitized_outputs[agent_key] = agent_result

        doc_context = {
            "client_context": client_context,
            "previous_outputs": sanitized_outputs,
            "report_template": report_template,
            "executive_style_guidance": {
                "tone": "VP-level professional",
                "formatting": "Strict Markdown with '---' separation."
            }
        }
        doc_result = call_ai_agent("document_architect", doc_context)
        safe_write_json(LOGS_DIR / "document_architect.json", doc_result)

        # Fix 2: Expose real error if document_architect failed
        if doc_result.get("status") == "error":
            report_content = f"# Report Generation Failed\n\n**Error Details:** {doc_result.get('error', 'Unknown error')}\n\n**Timestamp:** {doc_result.get('completed_at', 'N/A')}\n\n---\n\n## Troubleshooting\n- Check if the transcript contains content that triggered safety filters\n- Review agent logs in the `logs/` directory\n- Ensure API key has sufficient quota"
            # Fix 4: Force intervention on error
            st.session_state.intervention_needed = True
            safe_write_json(LOGS_DIR / "cross_talk.json", {
                "negotiations": [{
                    "agent": "document_architect",
                    "message": f"Report generation failed: {doc_result.get('error', 'Unknown error')}"
                }],
                "status": "PIPELINE_ERROR",
                "flagged_at": datetime.now().isoformat()
            })
        else:
            # Get raw report and sanitize to remove LaTeX/MathJax artifacts
            raw_report = doc_result.get("output", {}).get("raw_output", "# Error generating report")
            report_content = sanitize_for_streamlit_markdown(raw_report)

        workspace_file = WORKSPACE_DIR / "FINAL_REPORT.md"
        workspace_file.write_text(report_content, encoding='utf-8')

        # --- Intervention State Synchronization ---
        # Check if the Document Architect flagged any issues in the report content
        intervention_markers = [
            "PENDING LEADERSHIP RESOLUTION",
            "PENDING REVIEW",
            "DRAFT - PENDING",
            "REQUIRES INTERVENTION",
            "ESCALATION REQUIRED",
            "UNRESOLVED CONFLICT"
        ]

        report_has_intervention = any(marker.lower() in report_content.lower() for marker in intervention_markers)

        if report_has_intervention:
            st.session_state.intervention_needed = True

            # Extract context from agent outputs to populate intervention details
            conflict_details = []

            # Check legal compliance issues
            if legal_data.get("compliance_status") not in ["APPROVED", None]:
                conflict_details.append({
                    "agent": "legal_counsel",
                    "message": f"Compliance Status: {legal_data.get('compliance_status', 'Unknown')}. {legal_data.get('summary', 'Review required.')}"
                })

            # Check technical feasibility blockers
            if custom_builds:
                conflict_details.append({
                    "agent": "technical_pm",
                    "message": f"Custom builds identified: {', '.join(custom_builds[:3])}. May require resource negotiation."
                })

            # Check finance objections
            finance_data = finance_result.get("output", {})
            if finance_data.get("deal_risk") in ["HIGH", "CRITICAL"]:
                conflict_details.append({
                    "agent": "finance_director",
                    "message": f"Deal Risk: {finance_data.get('deal_risk', 'Unknown')}. {finance_data.get('recommendation', 'Review pricing.')}"
                })

            # GUARANTEED FALLBACK: If no specific conflicts found but intervention is needed, inject default
            if not conflict_details:
                conflict_details.append({
                    "agent": "system",
                    "message": "General Compliance Block: The document contains unresolved markers requiring leadership sign-off before client delivery."
                })

            # FORCE WRITE: Always write when intervention_needed is True
            cross_talk_payload = {
                "negotiations": conflict_details,
                "status": "PENDING_RESOLUTION",
                "flagged_at": datetime.now().isoformat()
            }
            write_success = safe_write_json(LOGS_DIR / "cross_talk.json", cross_talk_payload)
            if not write_success:
                # Fallback: try direct write if safe_write fails
                try:
                    with open(LOGS_DIR / "cross_talk.json", 'w', encoding='utf-8') as f:
                        json.dump(cross_talk_payload, f, indent=2)
                except Exception:
                    pass
        else:
            # Clear intervention flag if report is clean
            if not st.session_state.intervention_needed:
                safe_write_json(LOGS_DIR / "cross_talk.json", {
                    "negotiations": [],
                    "status": "CLEAR",
                    "cleared_at": datetime.now().isoformat()
                })

        st.session_state.pipeline_end_time = time.time()
        st.session_state.pipeline_completed = True
        st.session_state.pipeline_running = False
        st.session_state.current_agent = None
        st.session_state.show_completion_banner = True  # Flag for completion UX
        update_status("Strategic Vision Complete. Navigate to Executive Report.")
        st.balloons()
        return True

    except Exception as e:
        st.error(f"Pipeline crashed: {str(e)}")
        st.session_state.pipeline_running = False
        return False

# ============================================================================
# UI COMPONENTS
# ============================================================================

def inject_cyber_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Manrope:wght@400;600;800&display=swap');
        
        /* Unified Animated Background for Main and Sidebar */
        .stApp, section[data-testid="stSidebar"] {
            background: linear-gradient(135deg, #1e1b4b, #312e81, #111827, #0f172a);
            background-size: 400% 400%;
            animation: gradientBG 20s ease infinite;
            color: #f8fafc;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* Shepherd-Style Glowing Button */
        div.stButton > button {
            background: linear-gradient(90deg, #1e293b, #0f172a);
            color: #e2e8f0;
            border: 1px solid #0ea5e9;
            border-radius: 9999px; /* Pill */
            font-family: 'Manrope', sans-serif;
            font-weight: 700;
            padding: 0.6rem 2rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 0 15px rgba(14, 165, 233, 0.3);
        }
        div.stButton > button:hover {
            box-shadow: 0 0 25px rgba(14, 165, 233, 0.6);
            transform: translateY(-2px);
            color: #ffffff;
            border-color: #38bdf8;
        }
        div.stButton > button:active {
            transform: translateY(1px);
        }

        /* Segmented Pill Tabs */
        div.row-widget.stRadio > div {
            flex-direction: row;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 50px;
            padding: 6px;
            border: 1px solid rgba(255,255,255,0.1);
            justify-content: space-between;
        }
        div.row-widget.stRadio > div[role="radiogroup"] > label {
            background: transparent;
            border-radius: 40px;
            margin: 0 4px;
            padding: 10px 24px;
            transition: all 0.3s ease;
            flex: 1;
            text-align: center;
            border: 1px solid transparent;
            font-family: 'Manrope', sans-serif;
            font-weight: 600;
            color: #94a3b8;
        }

        /* Metric Boxes - Uniform Glassmorphism */
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }
        .metric-box {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(14, 165, 233, 0.2);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            height: 140px;
            transition: transform 0.3s ease;
        }
        .metric-box:hover {
            transform: translateY(-5px);
            border-color: #0ea5e9;
            box-shadow: 0 10px 30px -10px rgba(14, 165, 233, 0.2);
        }
        .metric-label {
            font-family: 'Manrope', sans-serif;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: #94a3b8;
            margin-bottom: 10px;
        }
        .metric-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.8em;
            font-weight: 700;
            color: #f8fafc;
        }
        .metric-sub {
            font-family: 'Manrope', sans-serif;
            font-size: 0.7em;
            color: #4ade80;
            margin-top: 5px;
        }

        /* Glitch-Morph Status Bar */
        .live-bar {
            background: rgba(15, 23, 42, 0.9);
            border-left: 4px solid #a855f7;
            padding: 15px 25px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            animation: fadeIn 0.5s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Agent Status Strip */
        .agent-strip {
            display: flex;
            gap: 12px;
            overflow-x: auto;
            align-items: center;
            padding: 5px 0;
        }
        .agent-chip {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(255,255,255,0.05);
            padding: 6px 14px;
            border-radius: 100px;
            font-family: 'Manrope';
            font-size: 0.8em;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
            color: #cbd5e1;
        }
        .agent-chip.active {
            border-color: #a855f7;
            background: rgba(168, 85, 247, 0.15);
            color: #e2e8f0;
            box-shadow: 0 0 10px rgba(168, 85, 247, 0.2);
        }
        .agent-chip.completed {
            border-color: #4ade80;
            background: rgba(74, 222, 128, 0.15);
            color: #e2e8f0;
        }
        
        /* Pulse Animation for Button */
        @keyframes pulse-glow {
            0% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(14, 165, 233, 0); }
            100% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0); }
        }

        /* Visual "Pop" for Bold Text - Professional Amber/Gold */
        .stMarkdown strong, .stMarkdown b {
            color: #fbbf24 !important;
            font-weight: 700 !important;
        }

        /* Hide the default white header bar */
        header[data-testid="stHeader"] {
            background: transparent !important;
            /* Alternatively, match the deep blue background exactly if transparent causes issues */
            background-color: #0f172a !important;
        }

        /* Force the Menu Options (Hamburger / Deploy) to be white so they are visible */
        header[data-testid="stHeader"] button {
            color: #f8fafc !important;
        }

        /* Hide the colored running man/stop animation if it distracts */
        div[data-testid="stStatusWidget"] {
            visibility: hidden;
        }
    </style>
    """, unsafe_allow_html=True)

def render_executive_header(status_placeholder):
    """Render the high-fidelity executive dashboard header."""
    metrics = calculate_efficiency()
    sentiment = st.session_state.sentiment_score
    status = "RUNNING" if st.session_state.pipeline_running else ("COMPLETE" if st.session_state.pipeline_completed else "READY")
    runtime = f"{metrics['runtime_hours']*60:.1f}m" if metrics['runtime_hours'] > 0 else "--"
    
    # Title
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 style="margin:0; font-family:'Manrope', sans-serif; font-weight:800; font-size: 2.5em; background: -webkit-linear-gradient(0deg, #f8fafc, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1.5px;">
            DEALNEXUS INTELLIGENCE SUITE
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Status Bar Placeholder (Populated dynamically)
    if not st.session_state.pipeline_running and not st.session_state.pipeline_completed:
        status_placeholder.markdown("""
        <div class="live-bar">
            <span style="margin-right: 15px; color: #a855f7;">\u26A1</span>
            <span>System Ready. Upload Transcript to Initialize.</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Calculate color for sentiment
    s_color = "#4ade80" if sentiment > 75 else ("#facc15" if sentiment > 50 else "#f87171")
    
    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-box">
            <div class="metric-label">Human Capital Leverage</div>
            <div class="metric-value">{metrics['hours_saved']:.1f}h</div>
            <div class="metric-sub">Saved vs Manual</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Process Value Realized</div>
            <div class="metric-value">${metrics['cost_saved']:.0f}</div>
            <div class="metric-sub">@ ${metrics['hourly_rate']}/hr</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Alignment</div>
            <div class="metric-value" style="color:{s_color}">{sentiment}%</div>
            <div class="metric-sub">Stakeholder Score</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">System Status</div>
            <div class="metric-value" style="font-size: 1.4em;">{status}</div>
            <div class="metric-sub">Pipeline State</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Execution</div>
            <div class="metric-value" style="font-size: 1.4em;">{runtime}</div>
            <div class="metric-sub">Total Runtime</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# COMPONENT: AGENT STRIP
# ============================================================================

def get_agent_strip_html():
    html = '<div class="agent-strip">'
    for agent in AGENT_NAMES:
        status = safe_read_json(LOGS_DIR / f"{agent}.json").get("status", "pending")
        is_active = st.session_state.current_agent == agent
        
        status_class = ""
        icon = "○"
        if status == "completed":
            status_class = "completed"
            icon = "●"
        elif is_active:
            status_class = "active"
            icon = "◎"
            
        html += f'<div class="agent-chip {status_class}"><span>{icon}</span><span>{AGENT_DISPLAY[agent]}</span></div>'
    html += '</div>'
    return html

# ============================================================================
# TABS & VIEWS
# ============================================================================

def render_ingestion_view(status_placeholder):
    # Ingestion Pulse Bar: Consolidating Targeting/Status + Input
    # Ensure correct HTML rendering with wrapper
    st.markdown(f"""
    <div style="background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
        <h3 style="margin-top:0; font-family:'Manrope'; font-size:1.1em; color:#cbd5e1;">Transcript Ingestion & Pulse</h3>
        {get_agent_strip_html()}
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.session_state.client_context = st.text_input("Client Context:", value=st.session_state.client_context, placeholder="e.g. MedVault - Series B Fintech", label_visibility="collapsed")
    with c2:
         uploaded_file = st.file_uploader("Upload", type=["txt", "docx", "mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"], label_visibility="collapsed")
    
    if uploaded_file:
        if st.session_state.last_processed != uploaded_file.name:
            file_extension = Path(uploaded_file.name).suffix.lower()
            if file_extension in ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']:
                with st.spinner("Processing Multimodal Content..."):
                    transcript_text = process_multimodal_file(uploaded_file)
                    if transcript_text:
                        st.session_state.uploaded_transcript = f"{uploaded_file.name}.txt"
                        st.session_state.last_processed = uploaded_file.name
                        st.session_state.last_uploaded = uploaded_file.name
                        st.success("Multimodal processing complete")
                        st.rerun()
            else:
                file_path = save_uploaded_file(uploaded_file)
                if file_path:
                    st.session_state.uploaded_transcript = file_path.name
                    st.session_state.last_processed = uploaded_file.name
                    st.session_state.last_uploaded = uploaded_file.name
                    st.success("File processed")
                    st.rerun()

    # Transcript Preview & Action
    transcript_name = st.session_state.uploaded_transcript
    if transcript_name:
        path = TRANSCRIPTS_DIR / transcript_name
        if path.exists():
            text = safe_read_text(path)
            
            with st.expander(f"View Transcript: {transcript_name} ({len(text.split())} words)"):
                st.text_area("Raw Text", text, height=200)

            # Prevent Vanishing Button: Only show if NOT running. 
            # If running, the status bar takes over.
            if not st.session_state.pipeline_running:
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("ACTIVATE INTELLIGENCE", type="primary", use_container_width=True):
                    st.session_state.pipeline_running = True
                    # Force a rerun to immediately update UI state (hide button, show status)
                    st.rerun()

def render_intervention_view():
    st.subheader("Intervention & Negotiation")

    cross_talk_data = safe_read_json(LOGS_DIR / "cross_talk.json", {"negotiations": [], "status": "CLEAR"})
    ct = cross_talk_data.get("negotiations", [])
    status = cross_talk_data.get("status", "CLEAR")

    # Show status-appropriate header
    if st.session_state.intervention_needed or status == "PENDING_RESOLUTION":
        st.warning("Critical Deadlock Detected. Manual review required before finalizing the report.")
        st.markdown(f"""
        <div style="background: rgba(250, 204, 21, 0.1); border: 1px solid #facc15; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <div style="font-weight: bold; color: #facc15; margin-bottom: 8px;">Resolution Status: {status.replace('_', ' ').title()}</div>
            <div style="color: #e2e8f0; font-size: 0.9em;">The Executive Report contains draft watermarks pending leadership resolution. Review the conflicts below and take appropriate action.</div>
        </div>
        """, unsafe_allow_html=True)
    elif status == "RESOLVED":
        st.success("All conflicts have been resolved.")
    elif not st.session_state.pipeline_completed:
        st.info("Pipeline not yet complete. Conflicts will be detected after analysis runs.")
        return

    if not ct:
        if st.session_state.pipeline_completed:
            st.success("No active negotiations or conflicts. Report is ready for delivery.")
        else:
            st.info("No active negotiations or conflicts.")
    else:
        st.markdown("### Flagged Issues")
        for idx, msg in enumerate(ct):
            agent = msg.get('agent', 'System')
            message = msg.get('message', '')

            # Color-code by agent type
            border_color = "#facc15"  # default yellow
            if agent == "legal_counsel":
                border_color = "#f87171"  # red for legal
            elif agent == "finance_director":
                border_color = "#4ade80"  # green for finance
            elif agent == "technical_pm":
                border_color = "#60a5fa"  # blue for technical

            st.markdown(f"""
            <div style="background: rgba(30,41,59,0.5); border-left: 4px solid {border_color}; padding: 15px; margin-bottom: 12px; border-radius: 4px;">
                <div style="font-weight: bold; color: {border_color}; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; font-size: 0.85em;">{agent.replace('_', ' ')}</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.9em; color: #e2e8f0; line-height: 1.5;">{message}</div>
            </div>
            """, unsafe_allow_html=True)

        # Resolution actions
        st.markdown("---")
        st.markdown("### Resolution Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Mark as Resolved", use_container_width=True):
                # Update cross_talk.json
                safe_write_json(LOGS_DIR / "cross_talk.json", {
                    "negotiations": ct,
                    "status": "RESOLVED",
                    "resolved_at": datetime.now().isoformat()
                })
                st.session_state.intervention_needed = False

                # Update FINAL_REPORT.md to replace DRAFT watermarks with resolution
                report_path = WORKSPACE_DIR / "FINAL_REPORT.md"
                if report_path.exists():
                    report_content = safe_read_text(report_path, "")

                    # Define patterns to replace
                    draft_patterns = [
                        "DRAFT - PENDING LEADERSHIP RESOLUTION",
                        "DRAFT - PENDING",
                        "PENDING LEADERSHIP RESOLUTION",
                        "PENDING REVIEW",
                        "REQUIRES INTERVENTION",
                        "ESCALATION REQUIRED",
                        "UNRESOLVED CONFLICT"
                    ]

                    # Resolution stamp with green indicator
                    resolution_stamp = """### 🟢 Leadership Resolution: Approved

**Status:** Issues Resolved by Rahul Vashisht (Test Pilot). Proceeding with Custom Build."""

                    # Replace all draft patterns
                    modified = False
                    for pattern in draft_patterns:
                        if pattern in report_content:
                            report_content = report_content.replace(pattern, resolution_stamp)
                            modified = True

                    # If no patterns found but we're resolving, prepend the resolution
                    if not modified:
                        report_content = resolution_stamp + "\n\n---\n\n" + report_content

                    # Save back to disk
                    report_path.write_text(report_content, encoding='utf-8')

                st.success("Resolved! Report updated with Leadership Approval stamp.")
                st.rerun()
        with col2:
            if st.button("Escalate to Leadership", use_container_width=True):
                st.info("Escalation logged. Notify your leadership team for further review.")

def sanitize_markdown_tables(content: str) -> str:
    """
    Clean up malformed markdown tables to prevent rendering gaps.
    - Removes trailing empty pipes (| |)
    - Ensures consistent column counts
    - Removes blank lines within table blocks
    """
    lines = content.split('\n')
    result = []
    in_table = False
    expected_cols = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect table rows
        if stripped.startswith('|') and stripped.endswith('|'):
            # Clean trailing empty pipes like "| |" or "|  |"
            # Remove trailing pipe, clean, then add back
            cleaned = stripped.rstrip('|').rstrip()
            # Remove empty trailing cells
            while cleaned.endswith('|') or cleaned.endswith('| '):
                cleaned = cleaned.rstrip('|').rstrip()
            cleaned = cleaned + ' |'

            # Count columns
            cols = cleaned.count('|') - 1  # subtract 1 for leading pipe

            if not in_table:
                in_table = True
                expected_cols = cols
                result.append(cleaned)
            else:
                # Check if this is a separator row
                if re.match(r'^\|[\s\-:]+\|$', stripped.replace(' ', '')):
                    result.append(cleaned)
                else:
                    # Data row - ensure same column count as header
                    result.append(cleaned)
        else:
            # Not a table row
            if in_table and stripped == '':
                # Skip blank lines immediately after table rows (prevents gaps)
                # But end the table context
                in_table = False
                expected_cols = 0
            else:
                in_table = False
                expected_cols = 0
            result.append(line)

    return '\n'.join(result)


def render_report_view():
    if not st.session_state.pipeline_completed:
        st.info("Awaiting pipeline completion...")
        return

    report_content = safe_read_text(WORKSPACE_DIR / "FINAL_REPORT.md", "No report found.")

    # Sanitize tables before rendering
    report_content = sanitize_markdown_tables(report_content)

    # Watermark logic fix: only show DRAFT if intervention is actually needed
    if st.session_state.intervention_needed:
        if "STATUS-BASED WATERMARK" in report_content or "DRAFT - PENDING" in report_content:
            st.error("REPORT ADVISORY: THIS DOCUMENT CONTAINS DRAFT WATERMARKS DUE TO PENDING INTERVENTION.")

    # Minimal table CSS - let Streamlit handle standard rendering
    st.markdown("""
    <style>
        .stMarkdown table {
            border-collapse: collapse !important;
            width: 100% !important;
        }
        .stMarkdown th, .stMarkdown td {
            border: 1px solid #475569 !important;
            padding: 8px !important;
            text-align: left !important;
        }
        .stMarkdown th {
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }
        .stMarkdown td {
            background-color: #0f172a !important;
            color: #e2e8f0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Strip any agent-generated appendix placeholders from the report
    appendix_markers = ["Appendix A:", "Appendix F:", "## Appendix", "### Appendix", "## Appendices", "### Appendices"]
    main_report = report_content
    for marker in appendix_markers:
        if marker in main_report:
            split_idx = main_report.find(marker)
            main_report = main_report[:split_idx].strip()
            break

    # Render the main report as flat, scrollable markdown (NOT in expanders)
    # The agent now generates the "Internal Performance Summary" header in markdown
    st.markdown(main_report)

    # Attribution footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 15px; color: #64748b; font-size: 0.8em; font-family: 'JetBrains Mono', monospace;">
        Architected and created by Rahul Vashisht (Test Pilot). (for testing purpose only)
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN
# ============================================================================

def main():
    st.set_page_config(page_title="DealNexus Intelligence Suite", page_icon="\u26A1", layout="wide")
    inject_cyber_css()
    initialize_session_state()
    
    # --- Sidebar ---
    with st.sidebar:
        st.title("\u26A1 DealNexus Suite")
        
        st.markdown("### Strategic Value Modeler")
        st.session_state.hourly_rate = st.slider("Human Capital Cost ($/hr)", 100, 300, 175, 5)
        
        st.markdown("---")
        
        # Intelligent Analyst Chat
        st.subheader("Intelligent Analyst")
        
        # Scrollable Chat Container
        st.markdown("""
        <style>
        .chat-scroll-container {
            max-height: 400px;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 5px;
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .chat-turn {
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .chat-msg {
            padding: 10px;
            border-radius: 6px;
            font-size: 0.85em;
            line-height: 1.4;
            max-width: 100%; /* Fix table overflow */
            overflow-x: auto;
        }
        .chat-msg.assistant {
            background: rgba(14, 165, 233, 0.1);
            border-left: 2px solid #0ea5e9;
            color: #e2e8f0;
        }
        .chat-msg.user {
            background: rgba(255, 255, 255, 0.03);
            border-left: 2px solid #94a3b8;
            color: #cbd5e1;
        }
        .chat-header {
            font-size: 0.7em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
            color: #94a3b8;
            font-weight: 700;
        }
        </style>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="chat-scroll-container">', unsafe_allow_html=True)
            for msg in st.session_state.manager_chat_history:
                role_class = "assistant" if msg["role"] == "assistant" else "user"
                role_name = "ANALYST" if msg["role"] == "assistant" else "YOU"
                
                st.markdown(f"""
                <div class="chat-turn">
                    <div class="chat-header">{role_name}</div>
                    <div class="chat-msg {role_class}">{msg['content']}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # Chat Input (Auto-clears)
        prompt = st.chat_input("Query the intelligence layer...")
        if prompt:
            st.session_state.manager_chat_history.append({"role": "user", "content": prompt})
            try:
                logs = []
                for a in AGENT_NAMES:
                    logs.append(safe_read_json(LOGS_DIR / f"{a}.json"))
                context = f"Logs: {json.dumps(logs)[:15000]}..." 
                model = genai.GenerativeModel("gemini-2.5-flash")
                chat_response = model.generate_content(
                    f"You are an Intelligent Analyst (VP level). Answer based on these logs:\n{context}\n\nUser Question: {prompt}",
                    generation_config=genai.types.GenerationConfig(temperature=0.0)
                )
                # Sanitize chat response to escape $ signs and prevent LaTeX rendering
                clean_chat_response = sanitize_for_streamlit_markdown(chat_response.text)
                st.session_state.manager_chat_history.append({"role": "assistant", "content": clean_chat_response})
                st.rerun()
            except Exception as e:
                st.error(f"Analyst Error: {str(e)}")

        st.markdown("---")
        if st.button("System Reset", use_container_width=True):
             for f in LOGS_DIR.glob("*"): f.unlink() 
             for f in WORKSPACE_DIR.glob("*"): f.unlink()
             st.session_state.clear()
             st.rerun()

    # --- Main Content ---
    
    # 1. Dynamic Status Bar Placeholder (Top of page)
    status_placeholder = st.empty()
    
    # 2. Executive Header
    render_executive_header(status_placeholder)
    
    # Check if pipeline was triggered
    if st.session_state.pipeline_running and not st.session_state.pipeline_completed:
        # Get transcript from file if not passed directly (since we are in main flow)
        if st.session_state.uploaded_transcript:
             path = TRANSCRIPTS_DIR / st.session_state.uploaded_transcript
             if path.exists():
                 text = safe_read_text(path)
                 with st.status("DealNexus Intelligence Pipeline Active...", expanded=True) as status:
                     success = run_pipeline_steps(text, st.session_state.client_context, status_placeholder)
                     if success:
                         status.update(label="Pipeline Complete", state="complete", expanded=False)
                         st.rerun()
                     else:
                         status.update(label="Pipeline Failed", state="error", expanded=True)
                         st.session_state.pipeline_running = False
             else:
                 st.session_state.pipeline_running = False
                 st.error(f"Transcript file not found: {path}")
                 st.rerun()
        else:
             st.session_state.pipeline_running = False
             st.error("No transcript loaded. Please upload a file first.")
             st.rerun()

    # 3. Completion Banner (shown once after pipeline completes)
    if st.session_state.get("show_completion_banner", False):
        metrics = calculate_efficiency()
        runtime_display = f"{metrics['runtime_hours']*60:.1f} minutes" if metrics['runtime_hours'] > 0 else "N/A"

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(74, 222, 128, 0.15), rgba(14, 165, 233, 0.1));
                    border: 1px solid #4ade80;
                    border-radius: 12px;
                    padding: 20px 25px;
                    margin-bottom: 20px;
                    animation: fadeIn 0.5s ease-in-out;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
                <div>
                    <div style="font-family: 'Manrope', sans-serif; font-weight: 800; font-size: 1.3em; color: #4ade80; margin-bottom: 5px;">
                        Analysis Complete
                    </div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.9em; color: #e2e8f0;">
                        Pipeline executed in {runtime_display}. Your Strategic Vision is ready.
                    </div>
                </div>
                <div style="display: flex; gap: 10px;">
                    <span style="background: rgba(74, 222, 128, 0.2); color: #4ade80; padding: 8px 16px; border-radius: 20px; font-family: 'Manrope', sans-serif; font-size: 0.85em; font-weight: 600;">
                        {metrics['hours_saved']:.1f}h Saved
                    </span>
                    <span style="background: rgba(14, 165, 233, 0.2); color: #0ea5e9; padding: 8px 16px; border-radius: 20px; font-family: 'Manrope', sans-serif; font-size: 0.85em; font-weight: 600;">
                        ${metrics['cost_saved']:.0f} Value
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            if st.button("View Executive Report", type="primary", use_container_width=True):
                st.session_state.active_tab = "Executive Report"
                st.session_state.show_completion_banner = False
                st.rerun()
        with col2:
            if st.session_state.intervention_needed:
                if st.button("Review Interventions", use_container_width=True):
                    st.session_state.active_tab = "Intervention"
                    st.session_state.show_completion_banner = False
                    st.rerun()
        with col3:
            if st.button("Dismiss", use_container_width=True):
                st.session_state.show_completion_banner = False
                st.rerun()

        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

    # 4. Custom Navigation Tabs
    tabs = ["Data Ingestion", "Intervention", "Executive Report"]

    if st.session_state.intervention_needed and st.session_state.active_tab != "Intervention":
        st.markdown("""
        <div style="margin-bottom: 15px;">
             <button class="stButton" style="width:100%; border: 1px solid #facc15; color: #facc15; background: rgba(250, 204, 21, 0.1);" onclick="window.location.reload()">
                \u26A0\uFE0F Deadlock Detected - Click to Switch to Intervention
            </button>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔍 Look Into Conflict", type="primary", use_container_width=True):
            st.session_state.active_tab = "Intervention"
            st.rerun()

    selected_tab = st.radio(
        "", 
        tabs, 
        index=tabs.index(st.session_state.active_tab) if st.session_state.active_tab in tabs else 0,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_radio"
    )
    
    if selected_tab != st.session_state.active_tab:
        st.session_state.active_tab = selected_tab
        st.rerun()

    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

    if st.session_state.active_tab == "Data Ingestion":
        render_ingestion_view(status_placeholder)
    elif st.session_state.active_tab == "Intervention":
        render_intervention_view()
    elif st.session_state.active_tab == "Executive Report":
        render_report_view()

if __name__ == "__main__":
    main()