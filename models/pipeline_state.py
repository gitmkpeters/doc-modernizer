"""
pipeline_state.py — Shared execution context for the document modernization pipeline.

BEDROCK PARALLEL:
    In AWS Step Functions, each state (Lambda function) receives a JSON input
    object and returns a JSON output object. The state machine passes this context
    forward automatically.

    Here, PipelineState is that JSON context — a single object that every agent
    reads from and writes to. By passing it through each agent instead of using
    global variables, we make the data flow explicit and debuggable, exactly like
    Step Functions does.

WHY A DATACLASS:
    Python dataclasses give us a clean container with typed fields and a free
    __repr__ for debugging, without the boilerplate of a regular class.
    In a Bedrock Lambda, each field here would be a key in the Step Functions
    execution input/output JSON.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PipelineState:
    """
    The single source of truth for a pipeline run.

    One instance is created at the start of main.py and passed through every
    agent. Each agent fills in its section and returns the updated state.
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    source_document_path: str = ""
    source_document_text: str = ""

    # ── Agent 1 — Analyzer output ─────────────────────────────────────────────
    # A structured JSON object describing the document's rules, procedures,
    # key terms, and tone. This is the "semantic map" — the foundation
    # every downstream agent works from.
    semantic_map: Optional[dict] = None

    # ── Agent 2 — Converter output ────────────────────────────────────────────
    # The rewritten document in plain modern language.
    modernized_document: Optional[str] = None

    # ── Agent 3 — Test Generator output ──────────────────────────────────────
    # A list of comprehension questions that verify the rewrite preserved intent.
    verification_questions: Optional[list] = None

    # ── Agent 4 — Deployer output ─────────────────────────────────────────────
    # The file path where the modernized document was written.
    output_file_path: Optional[str] = None

    # ── Agent 5 — Verifier output ─────────────────────────────────────────────
    # A dict containing confidence_score, findings, and sign_off status.
    verification_report: Optional[dict] = None

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    # Unique ID for this run — used to name output files so runs don't overwrite.
    # In Bedrock, this would be the Step Functions execution ARN.
    pipeline_id: str = field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    stage: str = "initialized"
    errors: list = field(default_factory=list)

    def summary(self) -> str:
        """
        Returns a human-readable status string.
        Used at human review gates so you can see what's been completed.
        """
        lines = [
            f"Pipeline ID : {self.pipeline_id}",
            f"Stage       : {self.stage}",
            f"Source      : {self.source_document_path}",
            f"Analyzer    : {'✓ complete' if self.semantic_map else '○ pending'}",
            f"Converter   : {'✓ complete' if self.modernized_document else '○ pending'}",
            f"Test Gen    : {'✓ complete' if self.verification_questions else '○ pending'}",
            f"Deployer    : {'✓ ' + self.output_file_path if self.output_file_path else '○ pending'}",
            f"Verifier    : {'✓ complete' if self.verification_report else '○ pending'}",
        ]
        if self.errors:
            lines.append(f"Errors      : {len(self.errors)}")
            for e in self.errors:
                lines.append(f"              ✗ {e}")
        return "\n".join(lines)

    def to_json(self) -> str:
        """
        Serialize state to JSON.
        Useful for saving checkpoints to disk between stages — in Bedrock,
        Step Functions does this automatically in S3.
        """
        return json.dumps(
            {
                "pipeline_id": self.pipeline_id,
                "stage": self.stage,
                "source_document_path": self.source_document_path,
                "semantic_map": self.semantic_map,
                "modernized_document": self.modernized_document,
                "verification_questions": self.verification_questions,
                "output_file_path": self.output_file_path,
                "verification_report": self.verification_report,
                "errors": self.errors,
            },
            indent=2,
        )
