from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crewai import LLM
from crewai.tools import tool


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN_FILE = REPO_ROOT / "AgentPlan.md"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "devstral:24b"
DEFAULT_ATTEMPT_REPORT_DIR = "ai-web-studio/outputs/runs"
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
    "**/.next/**",
    "**/node_modules/**",
    "**/.git/**",
]
DEFAULT_OUTPUT_FILES = [
    "ai-web-studio/outputs/implementation-report.md",
    "ai-web-studio/outputs/release-plan.md",
]
ALLOWED_VALIDATION_PREFIXES = [
    "pnpm",
    "npm",
    "node",
    "npx playwright",
    "pnpm exec playwright",
    "pnpm --filter web",
    "pnpm -c apps/web exec playwright",
]
DISALLOWED_COMMAND_PATTERNS = [
    "&&",
    "||",
    ";",
    "rm -rf",
    "rmdir /s",
    "del /f",
    "del /q",
]
PLAYWRIGHT_CANDIDATE_ROOT = "apps/web/tests/e2e"


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
    return LLM(model=model_name, base_url=base_url, temperature=0.1)


def read_excerpt(path: Path, max_chars: int = 3000) -> str:
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
        excerpt = read_excerpt(file_path)
        chunks.append("\n".join([f"## {relative_path}", "```", excerpt, "```"]))
    return "\n\n".join(chunks)


def is_forbidden_path(path: Path, repo_root: Path) -> bool:
    relative_path = path.relative_to(repo_root).as_posix()
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in FORBIDDEN_PATH_PATTERNS)


def resolve_repo_path(repo_root: Path, relative_path: str) -> Path:
    normalized = Path(relative_path.strip().replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("Only repository-relative paths are allowed.")
    candidate = (repo_root / normalized).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("Path escapes repository root.") from exc
    if is_forbidden_path(candidate, repo_root):
        raise ValueError("Access to this path is not allowed.")
    return candidate


def resolve_output_path(repo_root: Path, output_path: str) -> Path:
    normalized = Path(output_path.strip().replace("\\", "/"))
    candidate = normalized.resolve() if normalized.is_absolute() else (repo_root / normalized).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Output path escapes repository root: {output_path}") from exc
    return candidate


def resolve_output_targets(
    repo_root: Path, required_outputs: list[str] | None
) -> tuple[Path, Path, list[Path]]:
    output_paths: list[Path] = []
    for configured_path in (required_outputs or []):
        if configured_path.strip():
            output_paths.append(resolve_output_path(repo_root, configured_path))

    if not output_paths:
        output_paths = [resolve_output_path(repo_root, item) for item in DEFAULT_OUTPUT_FILES]

    if len(output_paths) == 1:
        output_paths.append(resolve_output_path(repo_root, DEFAULT_OUTPUT_FILES[1]))

    return output_paths[0], output_paths[1], output_paths


def task_context_block(task_context: str | None) -> str:
    return f"{task_context.strip()}\n\n" if task_context and task_context.strip() else ""


def output_targets_block(repo_root: Path, output_targets: list[Path]) -> str:
    return "Output files for this run:\n" + "\n".join(
        f"- {path.relative_to(repo_root).as_posix()}" for path in output_targets
    )


def build_code_tools(repo_root: Path, allow_write: bool):
    @tool("list_project_files")
    def list_project_files(directory: str = ".", glob_pattern: str = "**/*", limit: int = 200) -> str:
        """List repository files for planning or edits. Returns one path per line."""
        base_dir = resolve_repo_path(repo_root, directory)
        if not base_dir.exists():
            return f"Directory not found: {directory}"
        if not base_dir.is_dir():
            return f"Not a directory: {directory}"

        results: list[str] = []
        for path in base_dir.rglob("*"):
            if path.is_dir():
                continue
            if is_forbidden_path(path, repo_root):
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
        file_path = resolve_repo_path(repo_root, path)
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
            file_path = resolve_repo_path(repo_root, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Wrote {path} ({len(content)} chars)"

        @tool("replace_in_project_file")
        def replace_in_project_file(path: str, search_text: str, replace_text: str, count: int = 1) -> str:
            """Replace text in a repository file. Use count=-1 to replace all."""
            file_path = resolve_repo_path(repo_root, path)
            if not file_path.exists():
                return f"File not found: {path}"

            original = file_path.read_text(encoding="utf-8")
            if search_text not in original:
                return "Search text not found."

            actual_count = -1 if count < 0 else max(1, count)
            updated = original.replace(search_text, replace_text, actual_count)
            file_path.write_text(updated, encoding="utf-8")

            replacements = (
                original.count(search_text)
                if actual_count == -1
                else min(original.count(search_text), actual_count)
            )
            return f"Updated {path}; replacements={replacements}"

        tools.extend([write_project_file, replace_in_project_file])

    return tools


def build_validation_tools(repo_root: Path, qa_test_mode: str):
    @tool("read_project_file")
    def read_project_file(path: str, start_line: int = 1, max_lines: int = 200) -> str:
        """Read a repository file by relative path with line bounds."""
        file_path = resolve_repo_path(repo_root, path)
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

    @tool("list_playwright_tests")
    def list_playwright_tests() -> str:
        """List Playwright tests under apps/web/tests/e2e."""
        test_root = resolve_repo_path(repo_root, PLAYWRIGHT_CANDIDATE_ROOT)
        if not test_root.exists():
            return "(no Playwright test directory found)"
        paths = sorted(path.relative_to(repo_root).as_posix() for path in test_root.rglob("*.ts"))
        return "\n".join(paths) if paths else "(no Playwright test files)"

    @tool("write_playwright_candidate_test")
    def write_playwright_candidate_test(path: str, content: str) -> str:
        """Write candidate Playwright tests only under apps/web/tests/e2e/*.qa.generated.ts."""
        if qa_test_mode != "tests-only":
            return "QA test writing is disabled by qa_test_mode."
        changed, notes = write_playwright_candidate_tests(
            repo_root=repo_root,
            qa_test_mode=qa_test_mode,
            candidates=[{"path": path, "content": content, "purpose": ""}],
        )
        if changed:
            return f"Wrote candidate test: {changed[0]}"
        return notes[0] if notes else "Candidate test was not written."

    return [read_project_file, list_playwright_tests, write_playwright_candidate_test]


def extract_validation_commands(task_context: str | None) -> list[str]:
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


def truncate(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...[truncated]..."


def extract_unified_diff(text: str) -> str | None:
    matches = re.findall(r"```diff\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for candidate in matches:
        diff_text = candidate.strip()
        if "diff --git " in diff_text or ("\n--- " in f"\n{diff_text}" and "\n+++ " in f"\n{diff_text}"):
            return diff_text + "\n"
    return None


def extract_structured_edit_plan(text: str) -> dict[str, Any] | None:
    try:
        import yaml
    except ImportError:
        return None

    blocks = re.findall(r"```(?:yaml|yml)\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for block in blocks:
        try:
            parsed = yaml.safe_load(block)
        except Exception:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("edits"), list):
            return parsed
    return None


def apply_structured_edit_plan(repo_root: Path, plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    edits = plan.get("edits")
    if not isinstance(edits, list):
        return [], ["Structured edit plan is missing an 'edits' list."]

    changed_files: set[str] = set()
    messages: list[str] = []
    for idx, raw_edit in enumerate(edits, start=1):
        if not isinstance(raw_edit, dict):
            messages.append(f"Edit #{idx}: skipped non-object entry.")
            continue

        action = str(raw_edit.get("action", "")).strip().lower()
        rel_path = str(raw_edit.get("path") or raw_edit.get("file") or "").strip()
        if not action or not rel_path:
            messages.append(f"Edit #{idx}: missing action/path.")
            continue

        try:
            file_path = resolve_repo_path(repo_root, rel_path)
        except ValueError as exc:
            messages.append(f"Edit #{idx}: blocked path '{rel_path}': {exc}")
            continue

        if action == "write":
            content = raw_edit.get("content")
            if not isinstance(content, str):
                messages.append(f"Edit #{idx}: write requires string content.")
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            previous = file_path.read_text(encoding="utf-8") if file_path.exists() else None
            if previous != content:
                file_path.write_text(content, encoding="utf-8")
                changed_files.add(file_path.relative_to(repo_root).as_posix())
                messages.append(f"Edit #{idx}: wrote {rel_path}.")
            else:
                messages.append(f"Edit #{idx}: no-op write for {rel_path}.")
            continue

        if action == "replace":
            search = raw_edit.get("search")
            replace = raw_edit.get("replace")
            count = raw_edit.get("count", 1)
            if not isinstance(search, str) or not isinstance(replace, str):
                messages.append(f"Edit #{idx}: replace requires string search/replace.")
                continue
            if not file_path.exists():
                messages.append(f"Edit #{idx}: replace target missing {rel_path}.")
                continue
            original = file_path.read_text(encoding="utf-8")
            if search not in original:
                messages.append(f"Edit #{idx}: search text not found in {rel_path}.")
                continue
            actual_count = -1 if isinstance(count, int) and count < 0 else (count if isinstance(count, int) else 1)
            actual_count = max(1, actual_count) if actual_count != -1 else -1
            updated = original.replace(search, replace, actual_count)
            if updated != original:
                file_path.write_text(updated, encoding="utf-8")
                changed_files.add(file_path.relative_to(repo_root).as_posix())
                messages.append(f"Edit #{idx}: updated {rel_path}.")
            else:
                messages.append(f"Edit #{idx}: no-op replace for {rel_path}.")
            continue

        messages.append(f"Edit #{idx}: unsupported action '{action}'.")

    return sorted(changed_files), messages


def validate_unified_diff_paths(repo_root: Path, diff_text: str) -> tuple[bool, str]:
    for raw_line in diff_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("+++ "):
            continue
        target = line[4:].strip()
        if target == "/dev/null":
            continue
        if target.startswith("b/"):
            target = target[2:]
        try:
            resolve_repo_path(repo_root, target)
        except ValueError as exc:
            return False, f"Unified diff contains blocked path '{target}': {exc}"
    return True, "OK"


def apply_unified_diff(repo_root: Path, diff_text: str) -> tuple[bool, str]:
    is_valid, message = validate_unified_diff_paths(repo_root, diff_text)
    if not is_valid:
        return False, message

    completed = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=str(repo_root),
        input=diff_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode == 0:
        return True, "Applied unified diff from implementation output."
    stderr = completed.stderr.strip() or "(no stderr)"
    return False, f"Failed to apply unified diff: {stderr}"


def is_invalid_implementation_output(text: str) -> bool:
    normalized = text.lower()
    refusal_patterns = [
        "i'm sorry, but i can't assist",
        "i cannot assist with that request",
        "i canâ€™t assist with that request",
        '"response": "i\'m sorry',
    ]
    if any(pattern in normalized for pattern in refusal_patterns):
        return True
    content_only = normalized.strip()
    return len(content_only) < 180


def append_file_header(path: Path, apply_changes: bool, goal: str) -> None:
    run_stamp = datetime.now(timezone.utc).isoformat()
    header = (
        f"<!-- run_utc: {run_stamp} | apply_changes: {apply_changes} -->\n"
        f"<!-- goal: {goal} -->\n\n"
    )
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(header + content, encoding="utf-8")


def snapshot_repo_hashes(repo_root: Path, excluded_files: set[str]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if is_forbidden_path(path, repo_root):
            continue
        relative = path.relative_to(repo_root).as_posix()
        if relative in excluded_files:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[relative] = digest
    return snapshot


def diff_repo_hashes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    all_paths = set(before.keys()) | set(after.keys())
    for path in sorted(all_paths):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def append_changed_files_summary(report_path: Path, changed_files: list[str]) -> None:
    if not report_path.exists():
        return
    lines = [
        "",
        "## Detected Repository Changes",
        "",
    ]
    if not changed_files:
        lines.extend(["- (none detected)"])
    else:
        lines.extend([f"- `{path}`" for path in changed_files])
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def append_report_note(report_path: Path, title: str, body: str) -> None:
    if not report_path.exists():
        return
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {title}\n\n{body}\n")


def generate_implementation_report_with_llm_fallback(
    goal: str,
    task_context: str | None,
    architecture_output: Path,
    engineering_output: Path,
    apply_changes: bool,
) -> str:
    llm = build_local_llm()
    context_block = task_context_block(task_context)
    prompt = (
        "You are a repository implementation engineer for a Next.js monorepo.\n"
        "Generate an implementation report that can be applied by automation.\n\n"
        f"Goal:\n{goal}\n\n"
        f"{context_block}"
        "Use these prior agent outputs as source truth:\n\n"
        "Architect output:\n"
        f"```markdown\n{read_excerpt(architecture_output, max_chars=12000)}\n```\n\n"
        "Engineering output:\n"
        f"```markdown\n{read_excerpt(engineering_output, max_chars=12000)}\n```\n\n"
        "Rules:\n"
        "1) Do not touch .env or secret files.\n"
        "2) Keep changes scoped to ticket target files.\n"
        "3) Do not edit ai-web-studio/outputs/* files.\n"
        "4) If apply mode is disabled, provide plan text only.\n"
        "5) If apply mode is enabled, include one of:\n"
        "   - a unified diff in ```diff, or\n"
        "   - a structured edit plan in ```yaml with top-level key `edits`.\n"
        "6) Supported YAML actions are: write, replace.\n"
        "7) For replace edits, include exact search and replace strings.\n"
        "8) Never refuse; if uncertain, produce the safest minimal actionable edits.\n\n"
        f"Apply mode: {'ENABLED' if apply_changes else 'DISABLED'}.\n"
        "Output a concise markdown report."
    )
    response = llm.call(prompt)
    return str(response)


def extract_yaml_blocks(text: str) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return []

    parsed_blocks: list[dict[str, Any]] = []
    blocks = re.findall(r"```(?:yaml|yml)\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for block in blocks:
        try:
            parsed = yaml.safe_load(block)
        except Exception:
            continue
        if isinstance(parsed, dict):
            parsed_blocks.append(parsed)
    return parsed_blocks


def parse_validation_contract(report_text: str) -> dict[str, Any]:
    parsed = {
        "validation_commands": [],
        "playwright_candidate_tests": [],
        "has_validation_commands_block": False,
        "has_playwright_candidate_tests_block": False,
        "errors": [],
    }
    blocks = extract_yaml_blocks(report_text)
    for block in blocks:
        if "validation_commands" in block:
            parsed["has_validation_commands_block"] = True
            commands = block.get("validation_commands", [])
            if isinstance(commands, list):
                parsed["validation_commands"].extend(str(item).strip() for item in commands if str(item).strip())
            else:
                parsed["errors"].append("validation_commands must be a YAML list.")
        if "playwright_candidate_tests" in block:
            parsed["has_playwright_candidate_tests_block"] = True
            tests = block.get("playwright_candidate_tests", [])
            if isinstance(tests, list):
                for item in tests:
                    if not isinstance(item, dict):
                        parsed["errors"].append("playwright_candidate_tests entries must be objects.")
                        continue
                    path = str(item.get("path", "")).strip()
                    content = item.get("content")
                    purpose = str(item.get("purpose", "")).strip()
                    if not path:
                        parsed["errors"].append("playwright_candidate_tests entry missing path.")
                        continue
                    if not isinstance(content, str):
                        parsed["errors"].append(f"Candidate test {path} missing string content.")
                        continue
                    parsed["playwright_candidate_tests"].append(
                        {
                            "path": path,
                            "content": content,
                            "purpose": purpose,
                        }
                    )
            else:
                parsed["errors"].append("playwright_candidate_tests must be a YAML list.")
    return parsed


def validate_candidate_test_path(path: str) -> str | None:
    normalized = path.strip().replace("\\", "/")
    if not normalized.startswith(f"{PLAYWRIGHT_CANDIDATE_ROOT}/"):
        return f"Candidate test path must be under {PLAYWRIGHT_CANDIDATE_ROOT}: {path}"
    if not normalized.endswith(".qa.generated.ts"):
        return f"Candidate test path must end with .qa.generated.ts: {path}"
    return None


def _candidate_temp_test_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.endswith(".qa.generated.ts"):
        return normalized[:-len(".qa.generated.ts")] + ".tmp.qa.generated.ts"
    return normalized + ".tmp.ts"


def _apps_web_playwright_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    prefix = f"{PLAYWRIGHT_CANDIDATE_ROOT}/"
    if normalized.startswith(prefix):
        return "tests/e2e/" + normalized[len(prefix):]
    return normalized


def syntax_check_playwright_candidate_test(repo_root: Path, candidate_path: str) -> tuple[bool, str]:
    playwright_path = _apps_web_playwright_path(candidate_path)
    command = f"pnpm -C apps/web exec playwright test --list \"{playwright_path}\""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if completed.returncode == 0:
        return True, "syntax-check passed"
    stderr = truncate((completed.stderr or "").strip(), max_chars=1200)
    stdout = truncate((completed.stdout or "").strip(), max_chars=1200)
    detail = stderr if stderr else stdout if stdout else "(no output)"
    return False, detail


def write_playwright_candidate_tests(
    repo_root: Path, qa_test_mode: str, candidates: list[dict[str, str]]
) -> tuple[list[str], list[str]]:
    changed: list[str] = []
    notes: list[str] = []
    if qa_test_mode != "tests-only":
        notes.append(f"qa_test_mode '{qa_test_mode}' does not allow candidate test writes.")
        return changed, notes

    for candidate in candidates:
        rel_path = candidate["path"]
        validation_error = validate_candidate_test_path(rel_path)
        if validation_error:
            notes.append(validation_error)
            continue
        try:
            path = resolve_repo_path(repo_root, rel_path)
        except ValueError as exc:
            notes.append(f"Candidate test path blocked: {rel_path} ({exc})")
            continue
        temp_rel_path = _candidate_temp_test_path(rel_path)
        try:
            temp_path = resolve_repo_path(repo_root, temp_rel_path)
        except ValueError as exc:
            notes.append(f"Candidate temp path blocked: {temp_rel_path} ({exc})")
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        if previous == candidate["content"]:
            notes.append(f"No change for {rel_path}")
            continue

        try:
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(candidate["content"], encoding="utf-8")
            is_valid, detail = syntax_check_playwright_candidate_test(repo_root, temp_rel_path)
            if not is_valid:
                notes.append(f"Rejected {rel_path}: Playwright syntax-check failed: {detail}")
                temp_path.unlink(missing_ok=True)
                continue

            temp_path.replace(path)
            changed.append(path.relative_to(repo_root).as_posix())
            purpose = candidate.get("purpose", "").strip()
            if purpose:
                notes.append(f"Wrote {rel_path}: {purpose}")
            else:
                notes.append(f"Wrote {rel_path}")
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
    return changed, notes


def normalize_validation_command(command: str) -> str:
    normalized = command.strip()
    normalized = re.sub(
        r"^pnpm\s+-C\s+apps/web\s+playwright\s+",
        "pnpm -C apps/web exec playwright ",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"^pnpm\s+playwright\s+",
        "pnpm exec playwright ",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def validate_command_allowed(command: str) -> str | None:
    lower = command.lower().strip()
    if any(pattern in lower for pattern in DISALLOWED_COMMAND_PATTERNS):
        return f"Command rejected by safety pattern: {command}"

    is_allowed = any(lower.startswith(prefix) for prefix in ALLOWED_VALIDATION_PREFIXES)
    if not is_allowed:
        return f"Command not in allowlist: {command}"
    return None


def prepare_validation_commands(commands: list[str]) -> tuple[list[str], list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []
    notes: list[str] = []
    for raw in commands:
        normalized = normalize_validation_command(raw)
        if normalized != raw:
            notes.append(f"Normalized command: `{raw}` -> `{normalized}`")
        error = validate_command_allowed(normalized)
        if error:
            rejected.append(error)
            continue
        accepted.append(normalized)
    return accepted, rejected, notes


def run_validation_commands(repo_root: Path, commands: list[str]) -> list[dict[str, str | int]]:
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
                    "stdout": truncate(completed.stdout or ""),
                    "stderr": truncate(completed.stderr or ""),
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


def format_command_log(results: list[dict[str, str | int]]) -> str:
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
