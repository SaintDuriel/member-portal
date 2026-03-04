from __future__ import annotations

import fnmatch
import os
import re
import subprocess
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


def _task_context_block(task_context: str | None) -> str:
    return f"{task_context.strip()}\n\n" if task_context and task_context.strip() else ""


def _output_targets_block(repo_root: Path, output_targets: list[Path]) -> str:
    return "Output files for this run:\n" + "\n".join(
        f"- {path.relative_to(repo_root).as_posix()}" for path in output_targets
    )


def _build_agents(llm: LLM, code_tools: list) -> tuple[Agent, Agent, Agent, Agent]:
    architect = Agent(
        role="Product Delivery Architect",
        goal="Turn the current MemberPortal codebase and plan into a realistic execution strategy.",
        backstory="You reconcile roadmap intent with the real state of the code.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    engineer = Agent(
        role="Full-Stack Implementation Lead",
        goal="Translate strategy into an implementation sequence with concrete code-level steps.",
        backstory="You focus on executable changes for Next.js, Prisma, Auth.js, and Playwright workflows.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    implementer = Agent(
        role="Repository Implementation Engineer",
        goal="Apply safe code changes to the repository based on the approved implementation plan.",
        backstory="You execute targeted edits, keep changes minimal, and avoid touching secrets or unrelated files.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
        tools=code_tools,
    )

    qa = Agent(
        role="Quality and Release Lead",
        goal="Define validation gates so changes ship with low regression risk.",
        backstory="You produce release decisions grounded in actual test/build execution evidence.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    return architect, engineer, implementer, qa


def _build_implementation_phase_crew(
    goal: str,
    repo_root: Path,
    plan_file: Path,
    run_id: str,
    apply_changes: bool,
    task_context: str | None,
    architecture_output: Path,
    engineering_output: Path,
    implementation_output: Path,
) -> Crew:
    snapshot = build_project_snapshot(repo_root)
    llm = build_local_llm()
    code_tools = build_code_tools(repo_root=repo_root, allow_write=apply_changes)
    architect, engineer, implementer, _ = _build_agents(llm, code_tools)
    task_context_block = _task_context_block(task_context)
    output_targets_block = _output_targets_block(
        repo_root, [architecture_output, engineering_output, implementation_output]
    )
    plan_status = "found" if plan_file.exists() else f"missing ({plan_file.as_posix()})"

    architecture_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            "Project objective:\n"
            f"{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            f"Planning source status: {plan_status}\n\n"
            "Produce the architect result only and keep it implementation-focused.\n"
            "Output:\n"
            "1) Current-state summary.\n"
            "2) Top implementation gaps.\n"
            "3) Prioritized execution phases with dependencies.\n\n"
            f"Snapshot:\n{snapshot}"
        ),
        expected_output="Architect report with gap analysis and execution phases.",
        agent=architect,
        output_file=str(architecture_output),
    )

    implementation_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            "Use the architect report to build a concrete execution backlog.\n"
            "Output:\n"
            "1) Backlog by platform area.\n"
            "2) Acceptance criteria per item.\n"
            "3) First 5 execution tasks.\n"
            "4) Explicit file targets."
        ),
        expected_output="Engineering implementation plan with explicit file targets.",
        agent=engineer,
        context=[architecture_task],
        output_file=str(engineering_output),
    )

    code_edit_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            f"{task_context_block}"
            f"{output_targets_block}\n\n"
            "Apply repository edits from the engineering plan.\n"
            f"Apply mode: {'ENABLED' if apply_changes else 'DISABLED (planning-only)'}.\n"
            "Rules:\n"
            "1) Read files before editing.\n"
            "2) Keep edits scoped to this task.\n"
            "3) Never modify secrets or .env files.\n"
            "4) Provide changed-file list and rationale.\n"
            "5) If apply mode is disabled, output a concrete patch plan only.\n"
            f"Write this report to: {implementation_output.relative_to(repo_root).as_posix()}"
        ),
        expected_output="Implementation report with concrete changes or patch plan.",
        agent=implementer,
        context=[architecture_task, implementation_task],
        output_file=str(implementation_output),
    )

    return Crew(
        name=f"memberportal-impl-{run_id}",
        agents=[architect, engineer, implementer],
        tasks=[architecture_task, implementation_task, code_edit_task],
        process=Process.sequential,
        verbose=False,
        cache=False,
        memory=False,
        tracing=False,
    )


def _build_validation_phase_crew(
    goal: str,
    repo_root: Path,
    run_id: str,
    qa_context: str,
    validation_output: Path,
) -> Crew:
    llm = build_local_llm()
    code_tools = build_code_tools(repo_root=repo_root, allow_write=False)
    _, _, _, qa = _build_agents(llm, code_tools)

    qa_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Project objective:\n{goal}\n\n"
            "Produce release validation based only on provided implementation artifacts and command logs.\n\n"
            f"{qa_context}\n\n"
            "Output must include:\n"
            "1) Automated checks outcome summary based on executed command logs.\n"
            "2) Manual smoke checks still required.\n"
            "3) Go/No-Go decision with rationale.\n"
            "4) Risks and mitigations.\n"
            "5) Explicit references to architect, engineering, and implementation outputs."
        ),
        expected_output="Validation report grounded in executed command evidence.",
        agent=qa,
        output_file=str(validation_output),
    )

    return Crew(
        name=f"memberportal-qa-{run_id}",
        agents=[qa],
        tasks=[qa_task],
        process=Process.sequential,
        verbose=False,
        cache=False,
        memory=False,
        tracing=False,
    )


def _extract_validation_commands(task_context: str | None) -> list[str]:
    if not task_context:
        return []
    match = re.search(
        r"##\s*Validation Commands\s*```(?:bash)?\s*(.*?)```",
        task_context,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    raw = match.group(1)
    commands: list[str] = []
    for line in raw.splitlines():
        command = line.strip()
        if not command or command.startswith("#"):
            continue
        commands.append(command)
    return commands


def _truncate(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...[truncated]..."


def _run_validation_commands(repo_root: Path, commands: list[str]) -> list[dict[str, str | int]]:
    results: list[dict[str, str | int]] = []
    for command in commands:
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60 * 30,
                check=False,
            )
            results.append(
                {
                    "command": command,
                    "exit_code": completed.returncode,
                    "stdout": _truncate(completed.stdout or ""),
                    "stderr": _truncate(completed.stderr or ""),
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "command": command,
                    "exit_code": 124,
                    "stdout": "",
                    "stderr": "Command timed out.",
                }
            )
    return results


def _format_command_log(results: list[dict[str, str | int]]) -> str:
    lines = [
        "# Executed Validation Command Logs",
        "",
        "| Command | Exit Code |",
        "| --- | --- |",
    ]
    for item in results:
        command = str(item["command"]).replace("|", "\\|")
        lines.append(f"| `{command}` | {item['exit_code']} |")

    for idx, item in enumerate(results, start=1):
        lines.extend(
            [
                "",
                f"## Command {idx}",
                f"`{item['command']}`",
                "",
                "### Stdout",
                "```text",
                str(item["stdout"]),
                "```",
                "",
                "### Stderr",
                "```text",
                str(item["stderr"]),
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def _is_invalid_implementation_output(text: str) -> bool:
    normalized = text.lower()
    refusal_patterns = [
        "i'm sorry, but i can't assist",
        "i cannot assist with that request",
        "i can’t assist with that request",
        '"response": "i\'m sorry',
    ]
    if any(pattern in normalized for pattern in refusal_patterns):
        return True
    content_only = normalized.strip()
    return len(content_only) < 180


def _append_file_header(path: Path, apply_changes: bool, goal: str) -> None:
    run_stamp = datetime.now(timezone.utc).isoformat()
    header = (
        f"<!-- run_utc: {run_stamp} | apply_changes: {apply_changes} -->\n"
        f"<!-- goal: {goal} -->\n\n"
    )
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(header + content, encoding="utf-8")


def run_memberportal_crew(
    goal: str,
    repo_root: Path = REPO_ROOT,
    plan_file: Path = DEFAULT_PLAN_FILE,
    apply_changes: bool = False,
    task_context: str | None = None,
    required_outputs: list[str] | None = None,
):
    dotenv_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path if dotenv_path.exists() else None)

    implementation_output, validation_output, output_targets = resolve_output_targets(
        repo_root, required_outputs
    )
    run_id = uuid4().hex[:8]
    architecture_output = implementation_output.with_name(f"{implementation_output.stem}-architect.md")
    engineering_output = implementation_output.with_name(f"{implementation_output.stem}-engineering.md")
    command_log_output = validation_output.with_name(f"{validation_output.stem}-command-logs.md")

    all_outputs = [architecture_output, engineering_output, implementation_output, validation_output, command_log_output]
    for target in all_outputs:
        target.parent.mkdir(parents=True, exist_ok=True)

    implementation_crew = _build_implementation_phase_crew(
        goal=goal,
        repo_root=repo_root,
        plan_file=plan_file,
        run_id=run_id,
        apply_changes=apply_changes,
        task_context=task_context,
        architecture_output=architecture_output,
        engineering_output=engineering_output,
        implementation_output=implementation_output,
    )
    implementation_crew.kickoff()

    implementation_text = implementation_output.read_text(encoding="utf-8") if implementation_output.exists() else ""
    if _is_invalid_implementation_output(implementation_text):
        _append_file_header(implementation_output, apply_changes, goal)
        raise RuntimeError(
            f"Fail-fast: implementation output is invalid/refusal in {implementation_output.relative_to(repo_root).as_posix()}."
        )

    validation_commands = _extract_validation_commands(task_context)
    if task_context and not validation_commands:
        raise RuntimeError("Fail-fast: task context provided but no 'Validation Commands' block could be parsed.")

    command_results = _run_validation_commands(repo_root, validation_commands)
    command_log_output.write_text(_format_command_log(command_results), encoding="utf-8")

    commands_summary_lines = [
        "Executed validation commands (system-generated):",
        *[f"- `{item['command']}` -> exit {item['exit_code']}" for item in command_results],
    ]
    qa_context = "\n\n".join(
        [
            "Architect output:\n```markdown\n" + _read_excerpt(architecture_output, max_chars=12000) + "\n```",
            "Engineering output:\n```markdown\n" + _read_excerpt(engineering_output, max_chars=12000) + "\n```",
            "Implementation output:\n```markdown\n" + _read_excerpt(implementation_output, max_chars=12000) + "\n```",
            "\n".join(commands_summary_lines),
            "Command log file:\n" + command_log_output.relative_to(repo_root).as_posix(),
        ]
    )

    validation_crew = _build_validation_phase_crew(
        goal=goal,
        repo_root=repo_root,
        run_id=run_id,
        qa_context=qa_context,
        validation_output=validation_output,
    )
    validation_result = validation_crew.kickoff()

    if command_results:
        existing_validation = validation_output.read_text(encoding="utf-8") if validation_output.exists() else ""
        validation_output.write_text(
            existing_validation
            + "\n\n## Executed Command Logs (System Generated)\n\n"
            + _format_command_log(command_results),
            encoding="utf-8",
        )

    failed_commands = [item for item in command_results if int(item["exit_code"]) != 0]
    for target in [*output_targets, architecture_output, engineering_output, command_log_output]:
        if target.exists():
            _append_file_header(target, apply_changes, goal)

    if failed_commands:
        failed_list = ", ".join(f"`{item['command']}` (exit {item['exit_code']})" for item in failed_commands)
        raise RuntimeError(f"Validation commands failed: {failed_list}")

    return validation_result
