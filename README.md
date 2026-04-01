# Document Modernization Pipeline
### A Multi-Agent AI System built with Python + Anthropic Claude

> **Part of the JPR FlipSide learning series** — building real AI systems from scratch so non-technical people can understand exactly how they work.

---

## What This Is

A working five-agent AI pipeline that reads a legacy government policy document and automatically rewrites it in plain, modern language — while verifying that nothing was lost or distorted in the process.

Each agent does one specific job. No agent does more than it should. The output of one becomes the input of the next. That's the core idea behind multi-agent design, and it's the same pattern used in enterprise AI systems running on AWS at scale.

```
Legacy Document
      │
      ▼
┌─────────────┐
│  Agent 1    │  Analyzer      → Reads the document, extracts rules/procedures into a JSON map
└──────┬──────┘
       │
┌──────▼──────┐
│  Agent 2    │  Converter     → Takes the JSON map, rewrites the document in plain language
└──────┬──────┘
       │
┌──────▼──────┐
│  Agent 3    │  Test Generator → Creates comprehension questions to verify the rewrite
└──────┬──────┘
       │
┌──────▼──────┐
│  Agent 4    │  Deployer      → Writes the final modernized document to an output file
└──────┬──────┘
       │
┌──────▼──────┐
│  Agent 5    │  Verifier      → Compares output to original, produces a confidence score
└─────────────┘
      │
      ▼
Modernized Document + Sign-off Report
```

Human review gates pause the pipeline between stages so a person can inspect and approve each agent's work before the next one runs.

---

## Why I Built This

I work in federal IT — 25 years managing a team that runs a legacy financial system. My organization is building a multi-agent AI pipeline on **AWS Bedrock** to modernize COBOL code into Oracle SQL/PL/SQL. The professional architecture uses five agents orchestrated by Step Functions with human approval gates.

I built this personal version to:

1. **Deeply understand** multi-agent design before contributing to the enterprise project
2. **Build real transferable skills** with agent pipelines — hands-on, not theoretical
3. **Document the journey** for my [JPR FlipSide](https://youtube.com/@JPRFlipSide) brand on YouTube and Instagram, where I help non-technical people move from fear to confidence with AI

This project is the local equivalent of the Bedrock architecture — same five-agent pattern, same orchestration logic, same human review gates — built on a Mac Mini using the Anthropic API directly.

---

## The Bedrock Parallel

If you're building on AWS Bedrock and Step Functions, here's how every concept in this project maps to what you're working with professionally:

| This project | AWS Bedrock architecture |
|---|---|
| `main.py` orchestrator | Step Functions state machine |
| `PipelineState` object | Step Functions execution context (JSON passed between states) |
| `agents/*.py` | Lambda functions (one per agent/state) |
| `human_review_gate()` | Step Functions human approval task |
| JSON checkpoints in `output/` | S3 artifact storage between stages |
| Token usage logging | CloudWatch metrics |
| `.env` API key | AWS Secrets Manager / Parameter Store |

Understanding this project means you understand the architecture — not just the code.

---

## Tech Stack

- **Python 3.10+**
- **Anthropic API** (Claude claude-sonnet-4-6 / claude-opus-4-6)
- **M4 Mac Mini** as always-on development server
- **VS Code** with Remote-SSH from a 2013 MacBook

---

## Project Structure

```
doc-modernizer/
├── main.py                    # Pipeline orchestrator (mirrors Step Functions)
├── models/
│   └── pipeline_state.py      # Shared execution context passed between agents
├── agents/
│   ├── analyzer.py            # Agent 1: Extract structure → JSON semantic map
│   ├── converter.py           # Agent 2: JSON map → modernized document  [coming soon]
│   ├── test_generator.py      # Agent 3: Verification questions           [coming soon]
│   ├── deployer.py            # Agent 4: Write output file                [coming soon]
│   └── verifier.py           # Agent 5: Confidence score & sign-off      [coming soon]
├── input/
│   └── sample_policy.txt      # Sample legacy government policy document
├── output/                    # Modernized documents and JSON checkpoints
├── reports/                   # Verification reports
├── requirements.txt
└── .env.example               # API key template
```

---

## Setup

**Prerequisites:** Python 3.10+, an [Anthropic API key](https://console.anthropic.com/settings/keys)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/doc-modernizer.git
cd doc-modernizer

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Open .env and paste your Anthropic API key

# Run the pipeline on the included sample document
python main.py

# Or run on your own document
python main.py path/to/your/document.txt
```

---

## How It Runs

When you run `python main.py`, the pipeline:

1. Loads the document and initializes a `PipelineState` object with a unique run ID
2. Passes the state to **Agent 1 (Analyzer)**, which calls Claude and returns a structured JSON semantic map
3. Saves a checkpoint JSON file to `output/` (so you can inspect exactly what the agent produced)
4. Pauses at a **human review gate** — you read the summary and type `yes` to continue or `no` to halt
5. *(Agents 2–5 coming in subsequent build sessions)*

Sample output from a run:

```
============================================================
  DOCUMENT MODERNIZATION PIPELINE
============================================================
  Pipeline ID : 20260331_142201
  Source      : input/sample_policy.txt
  Length      : 5,847 characters

============================================================
  AGENT 1 — ANALYZER
============================================================
  Calling Claude... done.

  Results:
    Document type : policy
    Title         : Management and Control of Information Technology Assets
    Rules found   : 12
    Procedures    : 4
    Key terms     : 4
    Roles         : 5
    Clarity issues: 8 identified

  Token usage: 1842 in / 987 out
  💾 Checkpoint saved: output/20260331_142201_after_agent1_analyzer.json

============================================================
  ⏸  HUMAN REVIEW GATE — AFTER ANALYSIS
============================================================
  Approve and continue? (yes/no):
```

---

## Build Log

This project is being built incrementally and documented publicly.

| Session | What was built |
|---|---|
| Session 1 | Project architecture, `PipelineState`, Agent 1 (Analyzer), orchestrator shell |
| Session 2 | Agent 2 — Converter *(coming soon)* |
| Session 3 | Agent 3 — Test Generator *(coming soon)* |
| Session 4 | Agents 4 & 5 — Deployer & Verifier *(coming soon)* |

---

## Follow the Journey

I document this kind of build on **JPR FlipSide** — where I help non-technical people understand and use AI tools with confidence.

- YouTube: [@JPRFlipSide](https://youtube.com/@JPRFlipSide)
- Instagram: [@JPRFlipSide](https://instagram.com/JPRFlipSide)

---

## License

MIT — use it, learn from it, build on it.
