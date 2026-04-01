"""
agents/analyzer.py — Agent 1: Document Analyzer

WHAT THIS AGENT DOES:
    Reads the raw legacy document and uses Claude to extract its complete
    logical structure into a JSON "semantic map." This map becomes the
    single source of truth that every downstream agent works from.

BEDROCK PARALLEL:
    This mirrors the COBOL Analyzer agent in your professional pipeline.
    Just as that agent reads COBOL and extracts data structures, program flow,
    and business logic before any conversion happens — this agent reads a
    policy document and extracts its rules, procedures, and intent first.

    The critical design principle: NEVER convert what you haven't fully understood.
    Separating analysis from conversion is what makes multi-agent pipelines
    reliable. If you collapse both into one step, errors compound silently.

WHY JSON OUTPUT:
    Forcing Claude to return structured JSON rather than free prose means:
    1. We can validate the output programmatically (did we get the fields we need?)
    2. Every downstream agent gets a consistent, typed input — not a blob of text
    3. In Bedrock, this JSON would be stored as an S3 artifact between Lambda stages

MODEL CHOICE:
    claude-sonnet-4-6 — good balance of analytical depth and speed for this task.
    The Analyzer needs to genuinely understand the document, not just summarize it,
    so we don't want to cut corners with a lighter model here.
"""

import json
import anthropic
from models.pipeline_state import PipelineState


# ── System Prompt ──────────────────────────────────────────────────────────────
#
# The system prompt is the "job description" for this agent.
# It tells Claude exactly what role it's playing, what format to return,
# and critically — it instructs Claude to return ONLY valid JSON.
#
# In Bedrock, this prompt would be stored in AWS Parameter Store or Secrets Manager
# and injected into the Lambda at runtime, so prompts can be updated without
# redeploying code.

SYSTEM_PROMPT = """You are a document analysis expert specializing in legacy government policy and procedure documents.

Your job is to analyze a document and extract its complete logical structure into a JSON semantic map.
This map will be handed to a downstream agent that will rewrite the document in plain modern language.
Your analysis must be thorough enough that the rewriter never needs to look at the original document.

CRITICAL INSTRUCTION: Return ONLY valid JSON. No explanation before it, no markdown code fences around it,
no commentary after it. Just the raw JSON object starting with { and ending with }.

The JSON must follow this exact schema — include every field even if some are empty arrays:

{
  "document_type": "string — e.g. 'policy', 'standard operating procedure', 'directive', 'handbook section'",
  "title": "string — the document title, inferred if not explicit",
  "summary": "string — 2-3 sentences describing the document's purpose and who it governs",
  "audience": "string — who this document is written for",
  "effective_scope": "string — what activities, systems, or people this document covers",

  "rules": [
    {
      "id": "R001",
      "text": "string — the rule stated clearly and completely",
      "mandatory": true,
      "conditions": "string or null — any if/when/unless conditions that apply"
    }
  ],

  "procedures": [
    {
      "id": "P001",
      "title": "string — name of this procedure",
      "trigger": "string — what event or condition initiates this procedure",
      "steps": [
        "string — each step as a complete, actionable sentence"
      ],
      "responsible_party": "string or null — who performs this procedure"
    }
  ],

  "key_terms": [
    {
      "term": "string",
      "definition": "string — definition as used in this document"
    }
  ],

  "dependencies": [
    "string — any referenced documents, systems, regulations, or external standards"
  ],

  "roles_mentioned": [
    "string — every role, title, or organizational unit referenced in the document"
  ],

  "tone_and_style": {
    "formality": "formal | semi-formal | informal",
    "era_indicators": [
      "string — specific phrases or conventions that date the document"
    ],
    "clarity_problems": [
      "string — specific passages or patterns that are unclear, passive, bureaucratic, or ambiguous"
    ]
  },

  "structural_notes": "string — observations about the document's organization, numbering scheme, or formatting"
}
"""


def run(state: PipelineState, client: anthropic.Anthropic) -> PipelineState:
    """
    Agent 1: Analyzer

    Reads state.source_document_text, sends it to Claude with the analysis
    prompt, parses the JSON response, and stores the result in state.semantic_map.

    Args:
        state:  The current pipeline state object. We read source_document_text
                and write semantic_map.
        client: The Anthropic client, initialized once in main.py and shared
                across all agents. (In Bedrock, each Lambda creates its own
                Bedrock client — shared client is a local optimization.)

    Returns:
        The updated PipelineState with semantic_map populated.

    Raises:
        json.JSONDecodeError: If Claude returns malformed JSON.
        anthropic.APIError:   If the API call fails.
    """

    print("\n" + "=" * 60)
    print("  AGENT 1 — ANALYZER")
    print("=" * 60)
    print(f"  Source: {state.source_document_path}")
    print(f"  Length: {len(state.source_document_text):,} characters")

    state.stage = "analyzing"

    # ── API Call ───────────────────────────────────────────────────────────────
    #
    # We use the Messages API with a system prompt (the agent's role) and a
    # user message (the document to analyze).
    #
    # max_tokens=8192: Generous limit so the JSON semantic map is never
    # truncated mid-response. The first run used 4,014 of a 4,096 limit —
    # dangerously close. Always give structured-output agents room to breathe.

    print("\n  Calling Claude... ", end="", flush=True)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze this document and return the JSON semantic map.\n\n"
                    "DOCUMENT:\n"
                    "─────────────────────────────────────────────────────\n"
                    f"{state.source_document_text}\n"
                    "─────────────────────────────────────────────────────"
                ),
            }
        ],
    )

    raw_response = message.content[0].text
    print("done.")

    # ── Parse and Validate ─────────────────────────────────────────────────────
    #
    # Claude was instructed to return only JSON, but we validate it explicitly.
    # In production Bedrock pipelines, this validation step would trigger a
    # Step Functions error handler that routes to a retry or human escalation state.
    #
    # We also do a light structural check — if key fields are missing, we warn
    # rather than crash, because partial data is better than no data.

    try:
        semantic_map = json.loads(raw_response)
    except json.JSONDecodeError:
        # Claude sometimes wraps JSON in markdown fences despite instructions.
        # Try stripping those before giving up.
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        semantic_map = json.loads(cleaned)  # If this also fails, let it raise

    # Light structural validation
    expected_fields = ["rules", "procedures", "key_terms", "tone_and_style"]
    missing = [f for f in expected_fields if f not in semantic_map]
    if missing:
        warning = f"Semantic map missing expected fields: {missing}"
        state.errors.append(warning)
        print(f"\n  ⚠ Warning: {warning}")

    state.semantic_map = semantic_map
    state.stage = "analyzed"

    # ── Results Summary ────────────────────────────────────────────────────────
    print(f"\n  Results:")
    print(f"    Document type : {semantic_map.get('document_type', 'unknown')}")
    print(f"    Title         : {semantic_map.get('title', 'unknown')}")
    print(f"    Rules found   : {len(semantic_map.get('rules', []))}")
    print(f"    Procedures    : {len(semantic_map.get('procedures', []))}")
    print(f"    Key terms     : {len(semantic_map.get('key_terms', []))}")
    print(f"    Roles         : {len(semantic_map.get('roles_mentioned', []))}")

    clarity_issues = semantic_map.get("tone_and_style", {}).get("clarity_problems", [])
    if clarity_issues:
        print(f"    Clarity issues: {len(clarity_issues)} identified")

    # Token usage — useful for cost tracking (mirrors CloudWatch metrics in Bedrock)
    usage = message.usage
    print(f"\n  Token usage: {usage.input_tokens} in / {usage.output_tokens} out")

    return state
