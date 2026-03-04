from __future__ import annotations

import fnmatch
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN_FILE = REPO_ROOT / "AgentPlan.md"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
SNAPSHOT_FILES = [
    "AgentPlan.md",
    "README.md",
    "apps/web/auth.ts",
    "apps/web/prisma/schema.prisma",
    "apps/web/tests/e2e/frontend.spec.ts",
    "apps/web/tests/e2e/member-profile-flow.spec.ts",
]
FORBIDDEN_PATH_PATTERNS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "**/node_modules/**",
    "**/.git/**",
]
DEFAULT_OUTPUT_FILES = [
    "ai-web-studio/outputs/implementation-report.md",
    "ai-web-studio/outputs/release-plan.md",
]


def get_ollama_config() -> tuple[str, str]:
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip()
    if not model:
        model = DEFAULT_OLLAMA_MODEL
    if not base_url:
        base_url = DEFAULT_OLLAMA_BASE_URL
    return model, base_url


def build_local_llm() -> LLM:
    model, base_url = get_ollama_config()
    model_name = model if model.startswith("ollama/") else f"ollama/{model}"
    return LLM(
        model=model_name,
        base_url=base_url,
        temperature=0.1,
    )


def _read_excerpt(path: Path, max_chars: int = 3000) -> str:
    if not path.exists():
        return "(missing)"
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n...[truncated]..."


def build_project_snapshot(repo_root: Path = REPO_ROOT) -> str:
    chunks: list[str] = []
    for relative_path in SNAPSHOT_FILES:
        file_path = repo_root / relative_path
        excerpt = _read_excerpt(file_path)
        chunks.append(
            "\n".join(
                [
                    f"## {relative_path}",
                    "```",
                    excerpt,
                    "```",
                ]
            )
        )
    return "\n\n".join(chunks)


def _is_forbidden_path(path: Path, repo_root: Path) -> bool:
    relative_path = path.relative_to(repo_root).as_posix()
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in FORBIDDEN_PATH_PATTERNS)


def _resolve_repo_path(repo_root: Path, relative_path: str) -> Path:
    normalized = Path(relative_path.strip().replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("Only repository-relative paths are allowed.")
    candidate = (repo_root / normalized).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("Path escapes repository root.") from exc
    if _is_forbidden_path(candidate, repo_root):
        raise ValueError("Access to this path is not allowed.")
    return candidate


def _resolve_output_path(repo_root: Path, output_path: str) -> Path:
    normalized = Path(output_path.strip().replace("\\", "/"))
    candidate = normalized.resolve() if normalized.is_absolute() else (repo_root / normalized).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Output path escapes repository root: {output_path}") from exc
    return candidate


def resolve_output_targets(repo_root: Path, required_outputs: list[str] | None) -> tuple[Path, Path, list[Path]]:
    output_paths: list[Path] = []
    for configured_path in (required_outputs or []):
        if configured_path.strip():
            output_paths.append(_resolve_output_path(repo_root, configured_path))

    if not output_paths:
        output_paths = [_resolve_output_path(repo_root, item) for item in DEFAULT_OUTPUT_FILES]

    if len(output_paths) == 1:
        output_paths.append(_resolve_output_path(repo_root, DEFAULT_OUTPUT_FILES[1]))

    return output_paths[0], output_paths[1], output_paths


def build_code_tools(repo_root: Path, allow_write: bool):
    @tool("list_project_files")
    def list_project_files(directory: str = ".", glob_pattern: str = "**/*", limit: int = 200) -> str:
        """List repository files for planning or edits. Returns one path per line."""
        base_dir = _resolve_repo_path(repo_root, directory)
        if not base_dir.exists():
            return f"Directory not found: {directory}"
        if not base_dir.is_dir():
            return f"Not a directory: {directory}"

        results: list[str] = []
        for path in base_dir.rglob("*"):
            if path.is_dir():
                continue
            if _is_forbidden_path(path, repo_root):
                continue
            relative = path.relative_to(repo_root).as_posix()
            if fnmatch.fnmatch(relative, glob_pattern):
                results.append(relative)
            if len(results) >= limit:
                break
        return "\n".join(results) if results else "(no files found)"

    @tool("read_project_file")
    def read_project_file(path: str, start_line: int = 1, max_lines: int = 200) -> str:
        """Read a repository file by relative path with line bounds."""
        file_path = _resolve_repo_path(repo_root, path)
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"Not a file: {path}"

        lines = file_path.read_text(encoding="utf-8").splitlines()
        start_index = max(0, start_line - 1)
        end_index = min(len(lines), start_index + max(1, max_lines))
        excerpt = lines[start_index:end_index]
        numbered = [f"{start_index + idx + 1}:{line}" for idx, line in enumerate(excerpt)]
        return "\n".join(numbered) if numbered else "(empty)"

    tools = [list_project_files, read_project_file]

    if allow_write:
        @tool("write_project_file")
        def write_project_file(path: str, content: str) -> str:
            """Write full file content to a repository-relative path."""
            file_path = _resolve_repo_path(repo_root, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Wrote {path} ({len(content)} chars)"

        @tool("replace_in_project_file")
        def replace_in_project_file(path: str, search_text: str, replace_text: str, count: int = 1) -> str:
            """Replace text in a repository file. Use count=-1 to replace all."""
            file_path = _resolve_repo_path(repo_root, path)
            if not file_path.exists():
                return f"File not found: {path}"

            original = file_path.read_text(encoding="utf-8")
            if search_text not in original:
                return "Search text not found."

            actual_count = -1 if count < 0 else max(1, count)
            updated = original.replace(search_text, replace_text, actual_count)
            file_path.write_text(updated, encoding="utf-8")

            replacements = original.count(search_text) if actual_count == -1 else min(original.count(search_text), actual_count)
            return f"Updated {path}; replacements={replacements}"

        tools.extend([write_project_file, replace_in_project_file])

    return tools


def build_memberportal_crew(
    goal: str,
    repo_root: Path = REPO_ROOT,
    plan_file: Path = DEFAULT_PLAN_FILE,
    apply_changes: bool = False,
    task_context: str | None = None,
    required_outputs: list[str] | None = None,
) -> Crew:
    dotenv_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path if dotenv_path.exists() else None)
    snapshot = build_project_snapshot(repo_root)
    llm = build_local_llm()
    code_tools = build_code_tools(repo_root=repo_root, allow_write=apply_changes)
    run_id = uuid4().hex[:8]
    implementation_output, validation_output, output_targets = resolve_output_targets(
        repo_root, required_outputs
    )
    task_context_block = (
        f"{task_context.strip()}\n\n" if task_context and task_context.strip() else ""
    )
    output_targets_block = "Output files for this run:\n" + "\n".join(
        f"- {path.relative_to(repo_root).as_posix()}" for path in output_targets
    )
    plan_status = (
        "found" if plan_file.exists() else f"missing ({plan_file.as_posix()})"
    )

    architect = Agent(
        role="Product Delivery Architect",
        goal="Turn the current MemberPortal codebase and plan into a realistic execution strategy.",
        backstory=(
            "You are a senior architect who reconciles roadmap intent with the real state of the code."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    engineer = Agent(
        role="Full-Stack Implementation Lead",
        goal="Translate strategy into an implementation sequence with concrete code-level steps.",
        backstory=(
            "You focus on executable changes for Next.js, Prisma, Auth.js, and Playwright workflows."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    qa = Agent(
        role="Quality and Release Lead",
        goal="Define validation gates so changes ship with low regression risk.",
        backstory=(
            "You build practical verification plans including E2E, auth checks, and release readiness."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    implementer = Agent(
        role="Repository Implementation Engineer",
        goal="Apply safe code changes to the repository based on the approved implementation plan.",
        backstory=(
            "You execute targeted edits, keep changes minimal, and avoid touching secrets or unrelated files."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
        tools=code_tools,
    )

    architecture_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            "Project objective:\n"
            f"{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            f"Planning source status: {plan_status}\n\n"
            "Use the code snapshot to identify what already exists and what is missing.\n"
            "Output:\n"
            "1) Current-state summary.\n"
            "2) Top implementation gaps.\n"
            "3) Prioritized execution phases with dependencies.\n\n"
            f"Snapshot:\n{snapshot}"
        ),
        expected_output=(
            "A markdown brief with current-state findings, key gaps, and a phased implementation strategy."
        ),
        agent=architect,
    )

    implementation_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            "Build a practical build plan from the architect output.\n"
            "Include concrete file targets, commands, and sequencing.\n"
            "Output:\n"
            "1) Backlog grouped by platform area (auth, member portal, admin, tests, infra).\n"
            "2) Acceptance criteria per backlog item.\n"
            "3) First 5 execution tasks the team should perform next.\n"
            "4) Quote the exact project objective in one line at the top."
        ),
        expected_output=(
            "A technical backlog with file-level implementation notes and acceptance criteria."
        ),
        agent=engineer,
        context=[architecture_task],
    )

    code_edit_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            "Use the implementation backlog to perform repository edits.\n"
            f"Apply mode: {'ENABLED' if apply_changes else 'DISABLED (planning-only)'}.\n"
            "Rules:\n"
            "1) Read files before editing.\n"
            "2) Keep edits focused to the requested goal.\n"
            "3) Do not modify any .env files or secrets.\n"
            "4) Return a concise list of changed files and why.\n"
            "If apply mode is disabled, produce a concrete patch plan with file-level edits but do not write files.\n"
            "Always include the Run ID and project objective in the report.\n"
            f"Write this report to: {implementation_output.relative_to(repo_root).as_posix()}"
        ),
        expected_output=(
            "A markdown implementation report with changed files (or planned file edits in dry-run mode)."
        ),
        agent=implementer,
        context=[implementation_task],
        output_file=str(implementation_output),
    )

    qa_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            "Create a release validation plan from the implementation backlog.\n"
            "Output:\n"
            "1) Automated checks to run in CI.\n"
            "2) Manual smoke tests.\n"
            "3) Go/No-Go criteria for deployment.\n"
            "4) Risks and mitigations.\n"
            "5) Explicitly reference at least three items from the implementation report.\n"
            f"Write this report to: {validation_output.relative_to(repo_root).as_posix()}"
        ),
        expected_output=(
            "A test and release checklist tailored to this MemberPortal codebase."
        ),
        agent=qa,
        context=[implementation_task, code_edit_task],
        output_file=str(validation_output),
    )

    return Crew(
        name=f"memberportal-{run_id}",
        agents=[architect, engineer, implementer, qa],
        tasks=[architecture_task, implementation_task, code_edit_task, qa_task],
        process=Process.sequential,
        verbose=False,
        cache=False,
        memory=False,
        tracing=False,
    )


def run_memberportal_crew(
    goal: str,
    repo_root: Path = REPO_ROOT,
    plan_file: Path = DEFAULT_PLAN_FILE,
    apply_changes: bool = False,
    task_context: str | None = None,
    required_outputs: list[str] | None = None,
):
    _, _, output_targets = resolve_output_targets(repo_root, required_outputs)
    for target in output_targets:
        target.parent.mkdir(parents=True, exist_ok=True)

    crew = build_memberportal_crew(
        goal=goal,
        repo_root=repo_root,
        plan_file=plan_file,
        apply_changes=apply_changes,
        task_context=task_context,
        required_outputs=required_outputs,
    )
    result = crew.kickoff()

    run_stamp = datetime.now(timezone.utc).isoformat()
    header = (
        f"<!-- run_utc: {run_stamp} | apply_changes: {apply_changes} -->\n"
        f"<!-- goal: {goal} -->\n\n"
    )
    for target in output_targets:
        if target.exists():
            content = target.read_text(encoding="utf-8")
            target.write_text(header + content, encoding="utf-8")

    return result
