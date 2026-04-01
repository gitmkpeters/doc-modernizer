"""
agents/deployer.py — Agent 4: Deployer

WHAT THIS AGENT DOES:
    Writes the modernized document to a clean, timestamped output file.
    This is the "deployment" step — taking the converted artifact and
    delivering it to its final destination.

BEDROCK PARALLEL:
    In your professional pipeline, the Deployment Agent writes the converted
    Oracle SQL/PL/SQL to a target schema or file store — S3, a Git repo,
    or a database. Same principle here: the output of conversion gets
    delivered to a defined location in a defined format.

WHY A DEDICATED AGENT FOR THIS:
    It might seem like overkill to have a whole agent just write a file.
    But separating deployment from conversion is a critical design principle:

    1. The Deployer can be swapped out without touching the Converter.
       Today we write a .md file. Tomorrow we could write to a CMS,
       a SharePoint site, or an API endpoint — the Converter doesn't change.

    2. It creates an explicit checkpoint. Nothing gets written to the
       output until ALL previous agents have run AND a human has approved
       at every gate. The file existing on disk means the pipeline succeeded
       up to this point.

    3. In Bedrock, this agent would handle the IAM permissions, S3 bucket
       policies, and write confirmations that other agents don't need to
       know about.

NO CLAUDE API CALL:
    This is the only agent that doesn't call Claude. Its job is purely
    operational — format the output and write it to disk. Using AI here
    would be waste. Good agent design means each agent uses the right tool
    for its job, not AI for everything.
"""

from pathlib import Path
from datetime import datetime
from models.pipeline_state import PipelineState


def run(state: PipelineState) -> PipelineState:
    """
    Agent 4: Deployer

    Writes the modernized document to output/ as a timestamped .md file,
    with a metadata header prepended so the file is self-documenting.

    Note: No Anthropic client needed — this agent does no AI inference.

    Args:
        state: Pipeline state. We read modernized_document and write
               output_file_path.

    Returns:
        Updated PipelineState with output_file_path populated.
    """

    print("\n" + "=" * 60)
    print("  AGENT 4 — DEPLOYER")
    print("=" * 60)

    if not state.modernized_document:
        raise ValueError("Deployer requires the modernized document from Agent 2.")

    state.stage = "deploying"

    # ── Build output path ──────────────────────────────────────────────────────
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_filename = f"{state.pipeline_id}_modernized_document.md"
    output_path = output_dir / output_filename

    # ── Prepend metadata header ────────────────────────────────────────────────
    #
    # We add a provenance block at the top of the file so anyone reading it
    # knows exactly where it came from and how it was produced.
    # In Bedrock, this metadata would be stored as S3 object tags.

    source_filename = Path(state.source_document_path).name
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question_count = len(state.verification_questions) if state.verification_questions else 0

    metadata_header = f"""<!--
  MODERNIZED DOCUMENT
  ───────────────────────────────────────────────────────
  Source file    : {source_filename}
  Pipeline ID    : {state.pipeline_id}
  Generated      : {generated_at}
  Verification   : {question_count} test questions generated
  Pipeline       : Analyzer → Converter → Test Generator → Deployer → Verifier
  ───────────────────────────────────────────────────────
  This document was produced by an automated modernization pipeline.
  It has passed human review gates after analysis and conversion.
  Final verification report is saved separately in output/.
-->

"""

    final_content = metadata_header + state.modernized_document

    # ── Write file ─────────────────────────────────────────────────────────────
    output_path.write_text(final_content, encoding="utf-8")

    state.output_file_path = str(output_path)
    state.stage = "deployed"

    word_count = len(state.modernized_document.split())
    print(f"\n  Results:")
    print(f"    Output file   : {output_path}")
    print(f"    Size          : {len(final_content):,} characters / {word_count:,} words")
    print(f"    ✓ Document written successfully")

    return state
