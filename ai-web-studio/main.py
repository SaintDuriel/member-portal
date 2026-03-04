from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv

from crew import get_ollama_config, run_memberportal_crew


DEFAULT_GOAL = (
    "Unify the MemberPortal implementation by producing a concrete execution plan for "
    "auth, member/admin UX, and production-grade validation."
)
DEFAULT_OUTPUT_FILES = [
    "ai-web-studio/outputs/implementation-report.md",
    "ai-web-studio/outputs/release-plan.md",
]


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
    parser.add_argument(
        "--task",
        default=None,
        help="Task ID from ai-web-studio/tasks/task-manifest.yaml (example: T08).",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Maximum implement+validate attempts per run (default: 5).",
    )
    parser.add_argument(
        "--qa-test-mode",
        default="tests-only",
        choices=["tests-only"],
        help="Validation test contribution mode (currently only: tests-only).",
    )
    parser.add_argument(
        "--attempt-report-dir",
        default="ai-web-studio/outputs/runs",
        help="Directory where per-attempt artifacts are written.",
    )
    return parser.parse_args()


def verify_ollama_server(base_url: str) -> bool:
    health_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urlopen(health_url, timeout=5) as response:
            return response.status == 200
    except URLError:
        return False


def suppress_crewai_event_pairing_warnings() -> None:
    try:
        from crewai.events import event_context

        event_context._default_config.mismatch_behavior = (
            event_context.MismatchBehavior.SILENT
        )
        event_context._default_config.empty_pop_behavior = (
            event_context.MismatchBehavior.SILENT
        )
    except Exception:
        # Non-fatal: if CrewAI internals change, proceed without suppression.
        pass


def load_task_from_manifest(repo_root: Path, task_id: str) -> dict[str, Any]:
    manifest_path = repo_root / "ai-web-studio" / "tasks" / "task-manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Task manifest not found: {manifest_path}")

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for --task support. Run `pip install -r ai-web-studio/requirements.txt`."
        ) from exc

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    tasks = manifest.get("tasks", [])
    selected = next(
        (item for item in tasks if str(item.get("id", "")).strip().upper() == task_id.strip().upper()),
        None,
    )
    if not selected:
        available = ", ".join(str(item.get("id", "")).strip() for item in tasks)
        raise ValueError(f"Task '{task_id}' not found in manifest. Available: {available}")

    task_file_rel = str(selected.get("file", "")).strip()
    if not task_file_rel:
        raise ValueError(f"Task '{task_id}' is missing 'file' in manifest.")

    task_file = repo_root / task_file_rel
    if not task_file.exists():
        raise FileNotFoundError(f"Task file missing: {task_file}")

    required_outputs = [str(item).strip() for item in selected.get("required_outputs", []) if str(item).strip()]
    task_content = task_file.read_text(encoding="utf-8")

    return {
        "id": str(selected.get("id", task_id)).strip().upper(),
        "file": task_file_rel,
        "required_outputs": required_outputs,
        "content": task_content,
    }


def build_task_context(task_data: dict[str, Any]) -> str:
    required_outputs = task_data.get("required_outputs", [])
    output_lines = "\n".join(f"- {item}" for item in required_outputs) or "- (none specified)"
    return (
        "Loaded task pack context:\n"
        f"Task ID: {task_data['id']}\n"
        f"Task file: {task_data['file']}\n"
        "Required output files:\n"
        f"{output_lines}\n\n"
        "Task specification:\n"
        f"{task_data['content']}"
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    suppress_crewai_event_pairing_warnings()

    dotenv_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path if dotenv_path.exists() else None)

    args = parse_args()
    repo_root = Path(args.repo_root)
    task_data: dict[str, Any] | None = None
    task_context: str | None = None
    required_outputs: list[str] | None = None
    selected_goal = args.goal

    if args.task:
        try:
            task_data = load_task_from_manifest(repo_root, args.task)
        except Exception as exc:
            print(f"Failed to load task '{args.task}': {exc}")
            return 1

        task_context = build_task_context(task_data)
        required_outputs = task_data.get("required_outputs", [])
        if args.goal == DEFAULT_GOAL:
            selected_goal = (
                f"Execute task {task_data['id']} from the task pack, complete all checklist items, "
                "and satisfy all done criteria."
            )

        print(f"Loaded task {task_data['id']} from {task_data['file']}")
        print(f"Task required outputs: {json.dumps(required_outputs)}")

    if args.apply and args.goal == DEFAULT_GOAL and not args.task:
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
    print(f"Max attempts: {args.max_attempts}")
    print(f"QA test mode: {args.qa_test_mode}")
    print(f"Attempt report dir: {args.attempt_report_dir}")
    try:
        result = run_memberportal_crew(
            goal=selected_goal,
            repo_root=repo_root,
            plan_file=Path(args.plan_file),
            apply_changes=args.apply,
            task_context=task_context,
            required_outputs=required_outputs,
            max_attempts=args.max_attempts,
            qa_test_mode=args.qa_test_mode,
            attempt_report_dir=args.attempt_report_dir,
        )
    except Exception as exc:
        print(f"Crew run failed: {exc}")
        return 1

    print("\n=== CrewAI Result ===\n")
    print(result.raw if hasattr(result, "raw") else result)
    output_files = required_outputs if required_outputs else DEFAULT_OUTPUT_FILES
    print("Saved output files:")
    for output_file in output_files:
        print(f"- {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
