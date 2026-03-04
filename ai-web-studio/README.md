# AI Web Studio (CrewAI)

This folder contains a CrewAI orchestration flow for coordinating the MemberPortal build.

## Setup

1. Install Ollama and pull the local model:

```bash
winget install -e --id Ollama.Ollama
ollama pull qwen2.5-coder:7b
```

If `ollama` is not found right after install on Windows, open a new terminal and retry.

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r ai-web-studio/requirements.txt
```

`requirements.txt` includes `crewai[litellm]` so Ollama models work with CrewAI.
It is pinned to a stable version to avoid the yanked `1.10.0` runtime warnings.

3. Configure local model settings in `ai-web-studio/.env`:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

## Run

```bash
python ai-web-studio/main.py
```

Planning-only mode (default):
- Agents produce architecture + implementation + QA outputs.
- No repository files are modified.

Task-pack mode (loads a predefined task file and required output filenames):

```bash
python ai-web-studio/main.py --task T08
```

Task IDs are defined in `ai-web-studio/tasks/task-manifest.yaml`.

Apply mode:

```bash
python ai-web-studio/main.py --goal "Implement feature X" --apply
```

In `--apply` mode, the implementation agent can edit repository files with guardrails:
- Only repo-relative paths
- `.env` and secret-like files are blocked
- `.next` build artifacts are ignored/blocked
- `.git` and `node_modules` paths are blocked
- `--goal` should be explicit and scoped (required in practice for safe edits)
- If local tool-calling is unreliable, runtime can apply model-produced `diff` or structured `yaml` edits.

Optional (advanced):
- `CREW_ENABLE_TOOL_WRITES=1` to allow direct file-write tools in the implementer agent.
  - Default is disabled; structured runtime apply is generally more reliable with local Ollama models.

Optional flags:

```bash
python ai-web-studio/main.py --goal "Your objective" --plan-file "C:/path/to/AgentPlan.md" --model qwen2.5-coder:7b
python ai-web-studio/main.py --task T08 --apply --model qwen2.5-coder:7b
python ai-web-studio/main.py --task T08 --apply --max-attempts 5 --qa-test-mode tests-only --attempt-report-dir ai-web-studio/outputs/runs
```

Output:
- Console summary from the crew run
- Legacy outputs (latest attempt snapshot):
  - `ai-web-studio/outputs/implementation-report.md`
  - `ai-web-studio/outputs/release-plan.md`
- Per-attempt outputs:
  - `ai-web-studio/outputs/runs/run-<id>/attempt-01/*`
  - ...
  - `ai-web-studio/outputs/runs/run-<id>/attempt-0N/*`

Each output file is stamped with run metadata (`run_utc`, `goal`, `apply_changes`) at the top.

## Runtime Layout

Core modules:
- `ai-web-studio/crew_defs.py`: agent definitions, goals, and prompt/task builders.
- `ai-web-studio/runtime_tools.py`: path guards, command safety, parsing, apply helpers, and tool definitions.
- `ai-web-studio/orchestrator.py`: multi-attempt run loop and phase orchestration.
- `ai-web-studio/crew.py`: compatibility shim exports.

## Multi-Attempt Behavior

- Each run can retry implementation + validation up to `--max-attempts` (default: 5).
- All agents rerun each attempt.
- Edits accumulate between attempts.
- Validation context includes current attempt outputs plus prior attempt outputs/failures.
- Execution stops early when all validated commands pass.

## Validation Contracts

Validation reports are expected to include YAML blocks:

```yaml
validation_commands:
  - pnpm test
  - pnpm --filter web test:e2e
  - pnpm build
```

```yaml
playwright_candidate_tests:
  - path: apps/web/tests/e2e/example.qa.generated.ts
    purpose: Validate a flow
    content: |
      import { test, expect } from "@playwright/test";
      test("example", async ({ page }) => {
        await page.goto("/");
        await expect(page.getByRole("heading", { name: "Guild Sites" })).toBeVisible();
      });
```

When `--apply` is enabled:
- Missing contract blocks are treated as an attempt failure.
- Runtime enforces command allowlist/safety checks before execution.

## Candidate Test Workflow

- Validation can generate Playwright candidate tests under `apps/web/tests/e2e/*.qa.generated.ts`.
- Candidate tests are executable during validation runs.
- Candidate tests are syntax-checked before final write using `pnpm -C apps/web exec playwright test --list <candidate>`.
- Invalid candidate tests are rejected and logged in validation output.
- Promotion to permanent tests is manual (rename/move candidate files and keep only approved coverage).
