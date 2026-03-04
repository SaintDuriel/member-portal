from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv

from crew import get_ollama_config, run_memberportal_crew


DEFAULT_GOAL = (
    "Unify the MemberPortal implementation by producing a concrete execution plan for "
    "auth, member/admin UX, and production-grade validation."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CrewAI orchestration for the MemberPortal project."
    )
    parser.add_argument(
        "--goal",
        default=DEFAULT_GOAL,
        help="Project-level objective given to the crew.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Absolute path to the MemberPortal repository root.",
    )
    parser.add_argument(
        "--plan-file",
        default=str(Path(__file__).resolve().parents[1] / "AgentPlan.md"),
        help="Path to the planning document (AgentPlan.md).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model to use (example: qwen2.5-coder:7b).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Ollama base URL (default: http://127.0.0.1:11434).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Allow the implementation agent to write code edits.",
    )
    return parser.parse_args()


def verify_ollama_server(base_url: str) -> bool:
    health_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urlopen(health_url, timeout=5) as response:
            return response.status == 200
    except URLError:
        return False


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    dotenv_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path if dotenv_path.exists() else None)

    args = parse_args()
    if args.apply and args.goal == DEFAULT_GOAL:
        print("When using --apply, provide an explicit --goal describing the exact feature to implement.")
        return 1

    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
    if args.base_url:
        os.environ["OLLAMA_BASE_URL"] = args.base_url

    model, base_url = get_ollama_config()
    if not verify_ollama_server(base_url):
        print(
            f"Ollama is not reachable at {base_url}. Start it with `ollama serve` and try again."
        )
        return 1

    print(f"Using local model: {model} @ {base_url}")
    if args.apply:
        print("Code edit mode: ENABLED")
    else:
        print("Code edit mode: DISABLED (planning only)")
    result = run_memberportal_crew(
        goal=args.goal,
        repo_root=Path(args.repo_root),
        plan_file=Path(args.plan_file),
        apply_changes=args.apply,
    )

    print("\n=== CrewAI Result ===\n")
    print(result.raw if hasattr(result, "raw") else result)
    print("Saved implementation report to ai-web-studio/outputs/implementation-report.md")
    print("\nSaved release checklist to ai-web-studio/outputs/release-plan.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
