"""
agents/test_generator.py — Agent 3: Test Generator

WHAT THIS AGENT DOES:
    Reads both the original semantic map (Agent 1 output) and the modernized
    document (Agent 2 output) and generates a set of comprehension and
    verification questions. These questions are designed to confirm that
    the rewrite preserved every rule, deadline, role, and procedure from
    the original.

BEDROCK PARALLEL:
    This mirrors the Test Generator agent in your professional COBOL pipeline.
    That agent generates unit tests that verify the converted Oracle SQL/PL/SQL
    produces the same outputs as the original COBOL program.

    Same principle here: before anything gets "deployed" (written to an output
    file), we generate test cases. If a human can answer every question correctly
    using only the modernized document, the rewrite is complete and accurate.
    If any question can't be answered from the rewrite, Agent 2 dropped something.

WHY TWO INPUTS:
    Most agents in this pipeline only need one input. Agent 3 is different —
    it needs both the semantic map AND the modernized document because:
    1. The semantic map tells it what SHOULD be in the document (ground truth)
    2. The modernized document tells it what IS in the document (the rewrite)
    Generating questions from the map ensures we test for completeness, not
    just readability. A question like "What is the deadline for the annual
    inventory report?" can only be answered correctly if the Converter
    preserved that specific deadline.

QUESTION CATEGORIES:
    - Factual: specific numbers, deadlines, timeframes ("How many days to...?")
    - Role-based: who is responsible for what ("Who must submit...?")
    - Procedural: correct order of steps ("What is the first step when...?")
    - Rules: mandatory vs. conditional requirements ("Under what conditions...?")
    - Definitions: key terms ("What is a Custodian?")
"""

import json
import anthropic
from models.pipeline_state import PipelineState


SYSTEM_PROMPT = """You are a quality assurance specialist reviewing modernized government policy documents.

You will receive two inputs:
1. A JSON semantic map of the original legacy document (the ground truth)
2. The modernized rewrite of that document

Your job is to generate a comprehensive set of verification questions that test whether the
modernized document faithfully preserved all the content from the original.

QUESTION DESIGN RULES:
- Every question must be answerable using ONLY the modernized document (no outside knowledge needed)
- Every question must have a single, unambiguous correct answer
- Questions must cover all critical content: deadlines, roles, rules, procedures, definitions
- Prioritize mandatory rules, procedures, specific deadlines, and defined terms
- Flag any question where you suspect the modernized document may NOT contain the answer
- LIMIT: Generate no more than 20 questions total — choose the most important ones

OUTPUT FORMAT — return ONLY valid JSON, no markdown, no explanation.
Keep correct_answer brief (under 20 words). Keep risk_note brief (under 15 words).

{
  "total_questions": 0,
  "coverage_summary": {
    "rules_tested": 0,
    "procedures_tested": 0,
    "terms_tested": 0,
    "roles_tested": 0
  },
  "questions": [
    {
      "id": "Q001",
      "category": "factual | role | procedural | rule | definition",
      "question": "string",
      "correct_answer": "string — brief, under 20 words",
      "source": "R001 | P001 | term | role",
      "risk_flag": false,
      "risk_note": null
    }
  ]
}
"""


def run(state: PipelineState, client: anthropic.Anthropic) -> PipelineState:
    """
    Agent 3: Test Generator

    Reads state.semantic_map and state.modernized_document, generates
    verification questions, and stores them in state.verification_questions.

    Args:
        state:  Pipeline state. We read semantic_map and modernized_document,
                and write verification_questions.
        client: Shared Anthropic client from main.py.

    Returns:
        Updated PipelineState with verification_questions populated.
    """

    print("\n" + "=" * 60)
    print("  AGENT 3 — TEST GENERATOR")
    print("=" * 60)

    if not state.semantic_map:
        raise ValueError("Test Generator requires the semantic map from Agent 1.")
    if not state.modernized_document:
        raise ValueError("Test Generator requires the modernized document from Agent 2.")

    rule_count = len(state.semantic_map.get("rules", []))
    proc_count = len(state.semantic_map.get("procedures", []))
    term_count = len(state.semantic_map.get("key_terms", []))
    role_count = len(state.semantic_map.get("roles_mentioned", []))

    print(f"  Input: {rule_count} rules, {proc_count} procedures, {term_count} terms, {role_count} roles to cover")

    state.stage = "generating_tests"

    user_message = f"""Generate verification questions for this document rewrite.

SEMANTIC MAP (ground truth from original document):
{json.dumps(state.semantic_map, indent=2)}

MODERNIZED DOCUMENT (the rewrite to be tested):
─────────────────────────────────────────────────────
{state.modernized_document}
─────────────────────────────────────────────────────

Generate enough questions to fully verify the rewrite preserved all rules, procedures,
deadlines, roles, and definitions from the semantic map.
"""

    print("\n  Calling Claude... ", end="", flush=True)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    raw_response = message.content[0].text
    print("done.")

    # ── Parse JSON ─────────────────────────────────────────────────────────────
    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        result = json.loads(cleaned)

    questions = result.get("questions", [])
    state.verification_questions = questions
    state.stage = "tests_generated"

    # ── Results summary ────────────────────────────────────────────────────────
    coverage = result.get("coverage_summary", {})
    risk_flags = [q for q in questions if q.get("risk_flag")]

    print(f"\n  Results:")
    print(f"    Questions generated : {len(questions)}")
    print(f"    Rules tested        : {coverage.get('rules_tested', '?')}")
    print(f"    Procedures tested   : {coverage.get('procedures_tested', '?')}")
    print(f"    Terms tested        : {coverage.get('terms_tested', '?')}")
    print(f"    Roles tested        : {coverage.get('roles_tested', '?')}")

    if risk_flags:
        print(f"\n  ⚠  Risk flags ({len(risk_flags)} questions may not be answerable from the rewrite):")
        for q in risk_flags:
            print(f"     {q['id']}: {q['question'][:70]}...")
            if q.get("risk_note"):
                print(f"          → {q['risk_note']}")
    else:
        print(f"\n  ✓ No risk flags — all questions appear answerable from the modernized document")

    # Show a few sample questions so you can see them at the review gate
    print(f"\n  Sample questions:")
    for q in questions[:3]:
        print(f"    [{q['id']} / {q['category']}] {q['question']}")
        print(f"      Answer: {q['correct_answer'][:80]}")

    usage = message.usage
    print(f"\n  Token usage: {usage.input_tokens} in / {usage.output_tokens} out")

    return state
