"""
main.py — Pipeline Orchestrator

WHAT THIS DOES:
    Acts as the conductor for all five agents. It initializes state,
    calls each agent in sequence, runs human review gates between stages,
    handles errors, and saves checkpoints to disk.

BEDROCK PARALLEL:
    This file is the local equivalent of your AWS Step Functions state machine.

    Step Functions concept          →  What we do here
    ─────────────────────────────────────────────────────────────────
    State machine definition        →  run_pipeline() function
    State (task)                    →  agent_name.run(state, client) call
    Execution input/output          →  PipelineState object passed by reference
    Human approval task             →  human_review_gate() function
    Error handler / Catch           →  try/except blocks around each agent
    Wait state                      →  input() blocking on human review
    S3 artifact storage             →  JSON checkpoints written to output/
    CloudWatch metrics              →  token usage printed per agent

HOW TO RUN:
    1. Copy .env.example to .env and add your Anthropic API key
    2. pip install -r requirements.txt
    3. python main.py
       — or —
       python main.py path/to/your/document.txt
"""

import os
import sys
import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from models.pipeline_state import PipelineState
from agents import analyzer
from agents import converter
from agents import test_generator

# Agents 4-5 will be imported here as we build them:
# from agents import deployer
# from agents import verifier


def human_review_gate(state: PipelineState, gate_name: str) -> bool:
    """
    Pause the pipeline and require explicit human approval to continue.

    BEDROCK PARALLEL:
        In Step Functions, a Human Approval task sends an SNS notification,
        then the state machine pauses until it receives an API callback
        (approve or reject). This is the local equivalent — it just blocks
        on stdin instead.

        The design principle is identical: no agent proceeds without a human
        seeing what the previous agent produced and consciously approving it.
        This is what makes AI pipelines safe for production use.

    Args:
        state:     Current pipeline state (printed as a summary for the reviewer)
        gate_name: Label shown in the console so you know which gate this is

    Returns:
        True  → approved, pipeline continues
        False → rejected, pipeline halts
    """
    print("\n" + "=" * 60)
    print(f"  ⏸  HUMAN REVIEW GATE — {gate_name}")
    print("=" * 60)
    print()
    print(state.summary())

    while True:
        response = input("\n  Approve and continue? (yes / no): ").strip().lower()
        if response in ("yes", "y"):
            print("  ✓ Approved. Continuing pipeline.\n")
            return True
        elif response in ("no", "n"):
            print("  ✗ Rejected. Pipeline halted.")
            return False
        else:
            print("  Please type 'yes' or 'no'.")


def save_checkpoint(state: PipelineState, label: str) -> None:
    """
    Write the full pipeline state to disk as a JSON checkpoint.

    BEDROCK PARALLEL:
        Step Functions automatically persists execution history in S3.
        This does the same thing locally — if a run fails, you can inspect
        the checkpoint to see exactly what each agent produced.
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    checkpoint_path = output_dir / f"{state.pipeline_id}_{label}.json"
    checkpoint_path.write_text(state.to_json(), encoding="utf-8")
    print(f"  💾 Checkpoint saved: {checkpoint_path}")


def run_pipeline(document_path: str) -> PipelineState:
    """
    Main pipeline orchestrator.

    Initializes state, calls each agent in sequence, and manages
    human review gates and error handling between stages.

    Args:
        document_path: Path to the legacy document to modernize.

    Returns:
        The final PipelineState after all agents have run (or after
        a halt at a human review gate).
    """

    # ── Setup ──────────────────────────────────────────────────────────────────
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
        )

    # One shared client — initialized once, passed to every agent.
    # In Bedrock, each Lambda creates its own Bedrock client at cold start.
    client = anthropic.Anthropic(api_key=api_key)

    # Load source document
    doc_path = Path(document_path)
    if not doc_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    state = PipelineState()
    state.source_document_path = str(doc_path)
    state.source_document_text = doc_path.read_text(encoding="utf-8")

    print("\n" + "=" * 60)
    print("  DOCUMENT MODERNIZATION PIPELINE")
    print("=" * 60)
    print(f"  Pipeline ID : {state.pipeline_id}")
    print(f"  Source      : {state.source_document_path}")
    print(f"  Length      : {len(state.source_document_text):,} characters")

    # ── AGENT 1 — ANALYZER ────────────────────────────────────────────────────
    #
    # Reads the raw document, extracts its rules/procedures/terms into JSON.
    # No transformation yet — just deep understanding.

    try:
        state = analyzer.run(state, client)
    except Exception as e:
        error_msg = f"Analyzer failed: {e}"
        state.errors.append(error_msg)
        print(f"\n  ✗ {error_msg}")
        print("  Pipeline halted due to Agent 1 error.")
        save_checkpoint(state, "FAILED_at_analyzer")
        return state

    save_checkpoint(state, "after_agent1_analyzer")

    # Human review gate — look at the semantic map before any conversion starts.
    # This is your chance to catch misunderstandings before they propagate.
    if not human_review_gate(state, "AFTER ANALYSIS — Review semantic map"):
        save_checkpoint(state, "HALTED_at_gate1")
        return state

    # ── AGENT 2 — CONVERTER ───────────────────────────────────────────────────
    #
    # Takes the semantic map and rewrites the document in plain modern language.
    # Works entirely from the map — never reads the original document.

    try:
        state = converter.run(state, client)
    except Exception as e:
        error_msg = f"Converter failed: {e}"
        state.errors.append(error_msg)
        print(f"\n  ✗ {error_msg}")
        print("  Pipeline halted due to Agent 2 error.")
        save_checkpoint(state, "FAILED_at_converter")
        return state

    save_checkpoint(state, "after_agent2_converter")

    # Human review gate — read the modernized document before generating
    # test questions. Does it sound right? Did anything get lost or distorted?
    if not human_review_gate(state, "AFTER CONVERSION — Review modernized document"):
        save_checkpoint(state, "HALTED_at_gate2")
        return state

    # ── AGENT 3 — TEST GENERATOR ──────────────────────────────────────────────
    #
    # Uses both the semantic map and the modernized document to generate
    # verification questions. Risk flags warn you if anything may be missing.

    try:
        state = test_generator.run(state, client)
    except Exception as e:
        error_msg = f"Test Generator failed: {e}"
        state.errors.append(error_msg)
        print(f"\n  ✗ {error_msg}")
        print("  Pipeline halted due to Agent 3 error.")
        save_checkpoint(state, "FAILED_at_test_generator")
        return state

    save_checkpoint(state, "after_agent3_test_generator")

    # Human review gate — review the questions and any risk flags before deploying.
    # If Agent 3 flagged questions it couldn't answer from the rewrite, something
    # was dropped in conversion and you should reject here and rerun.
    if not human_review_gate(state, "AFTER TEST GENERATION — Review questions & risk flags"):
        save_checkpoint(state, "HALTED_at_gate3")
        return state

    # ── AGENT 4 — DEPLOYER ────────────────────────────────────────────────────
    print("\n  [Agent 4 — Deployer: coming soon]")

    # ── AGENT 5 — VERIFIER ────────────────────────────────────────────────────
    print("  [Agent 5 — Verifier: coming soon]")

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE (Session 3 scope)")
    print("=" * 60)
    print(state.summary())

    return state


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Accept an optional document path as a command-line argument.
    # Default to the sample document so you can run it immediately.
    document = sys.argv[1] if len(sys.argv) > 1 else "input/sample_policy.txt"
    run_pipeline(document)
