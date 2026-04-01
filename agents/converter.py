"""
agents/converter.py — Agent 2: Document Converter

WHAT THIS AGENT DOES:
    Takes the JSON semantic map from Agent 1 and rewrites the document in
    plain, modern language. It never touches the original document — it works
    entirely from the structured map. This is the transformation step.

BEDROCK PARALLEL:
    This mirrors the Oracle Converter agent in your professional pipeline.
    That agent takes the structured understanding of the COBOL program and
    converts it to Oracle SQL/PL/SQL. Same principle: convert from the map,
    not from the original source. If the Analyzer did its job well, the
    Converter never needs to look back.

WHY WORK FROM THE MAP (NOT THE ORIGINAL DOCUMENT):
    This is the most important design decision in the pipeline.
    If the Converter read the original document directly, it would just be
    a fancy summarizer. By forcing it to work from the semantic map:
    1. Errors in the Analyzer are caught at the human review gate — before
       they silently corrupt the conversion
    2. The Converter's job becomes purely about language and structure,
       not comprehension — it's a specialist, not a generalist
    3. We get a clean audit trail: map → document, fully traceable

PLAIN LANGUAGE STANDARD:
    Federal plain language guidelines (plainlanguage.gov) require:
    - Active voice over passive voice
    - "You must" instead of "It shall be the responsibility of..."
    - Short sentences (aim for under 20 words)
    - Common words over bureaucratic vocabulary
    - Headers and lists to break up dense paragraphs
    This agent is prompted to follow those standards.
"""

import anthropic
from models.pipeline_state import PipelineState
import json


# ── System Prompt ──────────────────────────────────────────────────────────────
#
# The Converter's job description is different from the Analyzer's.
# Where the Analyzer had to be precise and structured (JSON output),
# the Converter needs to be a skilled writer — clear, direct, complete.
# We give it the plain language standard as its target.

SYSTEM_PROMPT = """You are a plain language editor specializing in modernizing government policy and procedure documents.

You will receive a JSON semantic map extracted from a legacy document. Your job is to rewrite the document
as a clean, modern policy document that any employee can understand and act on.

WRITING STANDARDS — follow these strictly:
- Use active voice: "You must submit..." not "It shall be submitted..."
- Use plain words: "use" not "utilize", "send" not "transmit", "before" not "prior to"
- Use direct address: write to "you" (the reader) where appropriate
- Keep sentences short — aim for under 20 words each
- Use headers to organize sections clearly
- Use numbered lists for procedures and steps
- Use bullet points for rules and requirements
- Define jargon the first time it appears, then use it consistently
- State deadlines and timeframes as concrete numbers: "within 10 business days" not "in a timely manner"

COMPLETENESS RULES — these are non-negotiable:
- Every rule from the semantic map must appear in the rewrite — nothing can be dropped
- Every procedure and every step must appear — in the correct order
- Every defined term must be defined in the rewrite
- Every role and their responsibilities must be included
- Every deadline and timeframe must be preserved exactly

FORMATTING:
- Start with a brief "What this policy covers" section (2-3 sentences)
- Use ## for main section headers
- Use ### for subsection headers
- Use numbered lists (1. 2. 3.) for sequential steps
- Use bullet points (- ) for non-sequential rules or responsibilities
- End with a "Quick Reference" section summarizing the key deadlines and contacts

OUTPUT:
Write the complete modernized document in Markdown format. Start directly with the document title as a # header.
Do not add any preamble or explanation — just the document itself.
"""


def run(state: PipelineState, client: anthropic.Anthropic) -> PipelineState:
    """
    Agent 2: Converter

    Reads state.semantic_map, sends it to Claude with the plain language
    prompt, and stores the rewritten document in state.modernized_document.

    Args:
        state:  Pipeline state. We read semantic_map and write modernized_document.
        client: Shared Anthropic client from main.py.

    Returns:
        Updated PipelineState with modernized_document populated.
    """

    print("\n" + "=" * 60)
    print("  AGENT 2 — CONVERTER")
    print("=" * 60)

    if not state.semantic_map:
        raise ValueError("Converter requires a semantic map from Agent 1. Run the Analyzer first.")

    # Pull key stats from the map so we can show them in the console
    rule_count = len(state.semantic_map.get("rules", []))
    proc_count = len(state.semantic_map.get("procedures", []))
    term_count = len(state.semantic_map.get("key_terms", []))

    print(f"  Input: semantic map with {rule_count} rules, {proc_count} procedures, {term_count} terms")

    state.stage = "converting"

    # ── Build the user message ─────────────────────────────────────────────────
    #
    # We serialize the full semantic map to a JSON string and pass it as the
    # user message. The model sees the complete structured data from Agent 1.
    #
    # We also include explicit instructions reinforcing that NOTHING can be
    # dropped — this is the most common failure mode in conversion agents.

    user_message = f"""Rewrite this document using the semantic map below.

Every rule, procedure, step, term, role, and deadline in the map must appear in your rewrite.
Do not summarize or condense — produce a complete, standalone policy document.

SEMANTIC MAP:
{json.dumps(state.semantic_map, indent=2)}
"""

    print("\n  Calling Claude... ", end="", flush=True)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    modernized_document = message.content[0].text
    print("done.")

    # ── Sanity check ───────────────────────────────────────────────────────────
    #
    # Basic completeness check: make sure the output is substantial.
    # A real validation happens in Agent 5 (Verifier) — this is just a
    # quick guard against an obviously truncated response.

    word_count = len(modernized_document.split())
    if word_count < 200:
        warning = f"Converter output seems short ({word_count} words) — may be incomplete"
        state.errors.append(warning)
        print(f"\n  ⚠ Warning: {warning}")

    state.modernized_document = modernized_document
    state.stage = "converted"

    # ── Results summary ────────────────────────────────────────────────────────
    print(f"\n  Results:")
    print(f"    Output length : {word_count:,} words")
    print(f"    Characters    : {len(modernized_document):,}")

    # Show a preview of the first two lines (the title)
    preview_lines = [l for l in modernized_document.split("\n") if l.strip()][:2]
    for line in preview_lines:
        print(f"    Preview       : {line[:80]}")

    usage = message.usage
    print(f"\n  Token usage: {usage.input_tokens} in / {usage.output_tokens} out")

    return state
