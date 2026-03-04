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

Apply mode:

```bash
python ai-web-studio/main.py --goal "Implement feature X" --apply
```

In `--apply` mode, the implementation agent can edit repository files with guardrails:
- Only repo-relative paths
- `.env` and secret-like files are blocked
- `.git` and `node_modules` paths are blocked
- `--goal` should be explicit and scoped (required in practice for safe edits)

Optional flags:

```bash
python ai-web-studio/main.py --goal "Your objective" --plan-file "C:/path/to/AgentPlan.md" --model qwen2.5-coder:7b
```

Output:
- Console summary from the crew run
- `ai-web-studio/outputs/implementation-report.md`
- `ai-web-studio/outputs/release-plan.md`
