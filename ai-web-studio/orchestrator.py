from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from crew_defs import build_implementation_phase_crew, build_validation_phase_crew
from runtime_tools import (
    DEFAULT_ATTEMPT_REPORT_DIR,
    DEFAULT_OUTPUT_FILES,
    DEFAULT_PLAN_FILE,
    REPO_ROOT,
    append_changed_files_summary,
    append_file_header,
    append_report_note,
    apply_structured_edit_plan,
    apply_unified_diff,
    diff_repo_hashes,
    extract_structured_edit_plan,
    extract_unified_diff,
    extract_validation_commands,
    format_command_log,
    generate_implementation_report_with_llm_fallback,
    is_invalid_implementation_output,
    parse_validation_contract,
    prepare_validation_commands,
    read_excerpt,
    resolve_output_path,
    resolve_output_targets,
    run_validation_commands,
    snapshot_repo_hashes,
    write_playwright_candidate_tests,
)


@dataclass
class AttemptArtifacts:
    attempt: int
    directory: Path
    architecture: Path
    engineering: Path
    implementation: Path
    validation: Path
    command_log: Path


def _build_attempt_artifacts(attempt_root: Path, attempt: int) -> AttemptArtifacts:
    attempt_dir = attempt_root / f"attempt-{attempt:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    return AttemptArtifacts(
        attempt=attempt,
        directory=attempt_dir,
        architecture=attempt_dir / "architect.md",
        engineering=attempt_dir / "engineering.md",
        implementation=attempt_dir / "implementation.md",
        validation=attempt_dir / "validation.md",
        command_log=attempt_dir / "command-logs.md",
    )


def _format_prior_attempt_summary(failures: list[str], artifacts: list[AttemptArtifacts]) -> str:
    lines = ["Prior attempts summary:"]
    if not artifacts:
        lines.append("- No prior attempts in this run.")
        return "\n".join(lines)
    for item in artifacts:
        lines.append(
            f"- Attempt {item.attempt}: "
            f"architect={item.architecture.name}, engineering={item.engineering.name}, "
            f"implementation={item.implementation.name}, validation={item.validation.name}"
        )
    if failures:
        lines.append("Failure history:")
        lines.extend(f"- {failure}" for failure in failures[-10:])
    return "\n".join(lines)


def _build_validation_context(
    *,
    current_attempt: AttemptArtifacts,
    prior_attempts: list[AttemptArtifacts],
    changed_files: list[str],
    failures: list[str],
) -> str:
    sections: list[str] = [
        "Current attempt outputs:",
        "Architect output:\n```markdown\n"
        + read_excerpt(current_attempt.architecture, max_chars=12000)
        + "\n```",
        "Engineering output:\n```markdown\n"
        + read_excerpt(current_attempt.engineering, max_chars=12000)
        + "\n```",
        "Implementation output:\n```markdown\n"
        + read_excerpt(current_attempt.implementation, max_chars=12000)
        + "\n```",
        "Detected repository changed files:\n"
        + "\n".join([f"- `{path}`" for path in changed_files] if changed_files else ["- (none detected)"]),
    ]

    if prior_attempts:
        sections.append("Prior attempt output index:")
        for item in prior_attempts:
            sections.append(
                f"- Attempt {item.attempt}: "
                f"{item.architecture.as_posix()}, {item.engineering.as_posix()}, {item.implementation.as_posix()}, {item.validation.as_posix()}"
            )
        for item in prior_attempts:
            sections.append(
                f"Prior attempt {item.attempt} architect excerpt:\n```markdown\n"
                + read_excerpt(item.architecture, max_chars=6000)
                + "\n```"
            )
            sections.append(
                f"Prior attempt {item.attempt} engineering excerpt:\n```markdown\n"
                + read_excerpt(item.engineering, max_chars=6000)
                + "\n```"
            )
            sections.append(
                f"Prior attempt {item.attempt} implementation excerpt:\n```markdown\n"
                + read_excerpt(item.implementation, max_chars=7000)
                + "\n```"
            )
            sections.append(
                f"Prior attempt {item.attempt} validation excerpt:\n```markdown\n"
                + read_excerpt(item.validation, max_chars=7000)
                + "\n```"
            )

    if failures:
        sections.append("Failure history:\n" + "\n".join(f"- {entry}" for entry in failures[-10:]))

    return "\n\n".join(sections)


def _append_validation_postamble(
    validation_output: Path,
    *,
    command_results: list[dict[str, str | int]],
    command_notes: list[str],
    rejected_commands: list[str],
    candidate_test_notes: list[str],
    candidate_test_files: list[str],
) -> None:
    existing = validation_output.read_text(encoding="utf-8") if validation_output.exists() else ""
    parts = [existing]
    if command_notes:
        parts.append("## Runtime Command Notes\n\n" + "\n".join(f"- {note}" for note in command_notes))
    if rejected_commands:
        parts.append("## Rejected Commands\n\n" + "\n".join(f"- {entry}" for entry in rejected_commands))
    if candidate_test_notes:
        parts.append("## Candidate Test Writes\n\n" + "\n".join(f"- {entry}" for entry in candidate_test_notes))
    if candidate_test_files:
        parts.append("## Promotion Candidates\n\n" + "\n".join(f"- `{path}`" for path in candidate_test_files))
    parts.append("## Executed Command Logs (System Generated)\n\n" + format_command_log(command_results))
    validation_output.write_text("\n\n".join(parts).strip() + "\n", encoding="utf-8")


def _copy_attempt_outputs_to_legacy_targets(
    attempt: AttemptArtifacts,
    implementation_output: Path,
    validation_output: Path,
) -> None:
    def read_or_placeholder(path: Path, placeholder: str) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else placeholder

    implementation_output.parent.mkdir(parents=True, exist_ok=True)
    validation_output.parent.mkdir(parents=True, exist_ok=True)
    implementation_output.write_text(
        read_or_placeholder(attempt.implementation, "# Implementation output missing\n"),
        encoding="utf-8",
    )
    validation_output.write_text(
        read_or_placeholder(attempt.validation, "# Validation output missing\n"),
        encoding="utf-8",
    )

    architect_output = implementation_output.with_name(f"{implementation_output.stem}-architect.md")
    engineering_output = implementation_output.with_name(f"{implementation_output.stem}-engineering.md")
    command_log_output = validation_output.with_name(f"{validation_output.stem}-command-logs.md")
    architect_output.write_text(
        read_or_placeholder(attempt.architecture, "# Architect output missing\n"),
        encoding="utf-8",
    )
    engineering_output.write_text(
        read_or_placeholder(attempt.engineering, "# Engineering output missing\n"),
        encoding="utf-8",
    )
    command_log_content = read_or_placeholder(
        attempt.command_log,
        "# Executed Validation Command Logs\n\n(no commands executed)\n",
    )
    command_log_output.write_text(command_log_content, encoding="utf-8")


def run_memberportal_crew(
    goal: str,
    repo_root: Path = REPO_ROOT,
    plan_file: Path = DEFAULT_PLAN_FILE,
    apply_changes: bool = False,
    task_context: str | None = None,
    required_outputs: list[str] | None = None,
    max_attempts: int = 5,
    qa_test_mode: str = "tests-only",
    attempt_report_dir: str = DEFAULT_ATTEMPT_REPORT_DIR,
):
    dotenv_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path if dotenv_path.exists() else None)

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if qa_test_mode != "tests-only":
        raise ValueError("qa_test_mode currently supports only 'tests-only'")

    implementation_output, validation_output, output_targets = resolve_output_targets(repo_root, required_outputs)
    _ = output_targets if output_targets else [Path(item) for item in DEFAULT_OUTPUT_FILES]

    run_id = uuid4().hex[:8]
    attempt_base = resolve_output_path(repo_root, attempt_report_dir) / f"run-{run_id}"
    attempt_base.mkdir(parents=True, exist_ok=True)

    fallback_task_commands = extract_validation_commands(task_context)
    failures: list[str] = []
    completed_attempts: list[AttemptArtifacts] = []
    final_validation_result = None

    for attempt_number in range(1, max_attempts + 1):
        current = _build_attempt_artifacts(attempt_base, attempt_number)
        attempt_outputs = [
            current.architecture,
            current.engineering,
            current.implementation,
            current.validation,
            current.command_log,
        ]
        for file_path in attempt_outputs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        excluded_output_files = {path.relative_to(repo_root).as_posix() for path in attempt_outputs}
        repo_hashes_before = snapshot_repo_hashes(repo_root, excluded_output_files)

        prior_summary = _format_prior_attempt_summary(failures, completed_attempts)
        implementation_crew = build_implementation_phase_crew(
            goal=goal,
            repo_root=repo_root,
            plan_file=plan_file,
            run_id=run_id,
            attempt=attempt_number,
            apply_changes=apply_changes,
            qa_test_mode=qa_test_mode,
            task_context=task_context,
            prior_attempt_summary=prior_summary,
            architecture_output=current.architecture,
            engineering_output=current.engineering,
            implementation_output=current.implementation,
        )
        implementation_crew.kickoff()

        repo_hashes_after_implementation = snapshot_repo_hashes(repo_root, excluded_output_files)
        changed_repo_files = diff_repo_hashes(repo_hashes_before, repo_hashes_after_implementation)

        implementation_text = (
            current.implementation.read_text(encoding="utf-8")
            if current.implementation.exists()
            else ""
        )
        if is_invalid_implementation_output(implementation_text):
            fallback_text = generate_implementation_report_with_llm_fallback(
                goal=goal,
                task_context=task_context,
                architecture_output=current.architecture,
                engineering_output=current.engineering,
                apply_changes=apply_changes,
            )
            current.implementation.write_text(fallback_text, encoding="utf-8")
            append_report_note(
                current.implementation,
                "Runtime Fallback",
                "Primary implementer output was invalid/refusal-like. Generated fallback via direct LLM call.",
            )
            implementation_text = current.implementation.read_text(encoding="utf-8")

        if apply_changes and not changed_repo_files:
            unified_diff = extract_unified_diff(implementation_text)
            if unified_diff:
                applied, apply_message = apply_unified_diff(repo_root, unified_diff)
                append_report_note(current.implementation, "Runtime Diff Apply", apply_message)
                if applied:
                    repo_hashes_after_implementation = snapshot_repo_hashes(repo_root, excluded_output_files)
                    changed_repo_files = diff_repo_hashes(repo_hashes_before, repo_hashes_after_implementation)
        if apply_changes and not changed_repo_files:
            structured_plan = extract_structured_edit_plan(implementation_text)
            if structured_plan:
                _, plan_messages = apply_structured_edit_plan(repo_root, structured_plan)
                append_report_note(
                    current.implementation,
                    "Runtime Structured Apply",
                    "\n".join(f"- {msg}" for msg in plan_messages) if plan_messages else "- (no messages)",
                )
                repo_hashes_after_implementation = snapshot_repo_hashes(repo_root, excluded_output_files)
                changed_repo_files = diff_repo_hashes(repo_hashes_before, repo_hashes_after_implementation)

        append_changed_files_summary(current.implementation, changed_repo_files)

        if apply_changes and not changed_repo_files:
            failure = f"Attempt {attempt_number}: apply mode enabled but no repository source files changed."
            failures.append(failure)
            append_report_note(current.implementation, "Attempt Failure", failure)
            completed_attempts.append(current)
            continue

        qa_context = _build_validation_context(
            current_attempt=current,
            prior_attempts=completed_attempts,
            changed_files=changed_repo_files,
            failures=failures,
        )
        validation_crew = build_validation_phase_crew(
            goal=goal,
            repo_root=repo_root,
            run_id=run_id,
            attempt=attempt_number,
            qa_test_mode=qa_test_mode,
            qa_context=qa_context,
            validation_output=current.validation,
        )
        final_validation_result = validation_crew.kickoff()

        validation_text = current.validation.read_text(encoding="utf-8") if current.validation.exists() else ""
        contract = parse_validation_contract(validation_text)

        missing_contract_sections: list[str] = []
        if apply_changes:
            if not contract["has_validation_commands_block"]:
                missing_contract_sections.append("validation_commands YAML block")
            if not contract["has_playwright_candidate_tests_block"]:
                missing_contract_sections.append("playwright_candidate_tests YAML block")
            if missing_contract_sections:
                failure = (
                    f"Attempt {attempt_number}: validation report missing required contract sections: "
                    + ", ".join(missing_contract_sections)
                )
                failures.append(failure)
                append_report_note(current.validation, "Attempt Failure", failure)
                completed_attempts.append(current)
                continue

        selected_commands = contract["validation_commands"] or fallback_task_commands
        accepted_commands, rejected_commands, command_notes = prepare_validation_commands(selected_commands)
        command_results: list[dict[str, str | int]] = []
        if accepted_commands:
            command_results.extend(run_validation_commands(repo_root, accepted_commands))
        if rejected_commands:
            command_results.extend(
                {
                    "command": "rejected-command",
                    "exit_code": 126,
                    "stdout": "",
                    "stderr": entry,
                }
                for entry in rejected_commands
            )

        candidate_test_files, candidate_test_notes = write_playwright_candidate_tests(
            repo_root,
            qa_test_mode=qa_test_mode,
            candidates=contract["playwright_candidate_tests"],
        )
        if candidate_test_files:
            append_report_note(
                current.validation,
                "Candidate Test Files",
                "\n".join(f"- `{path}`" for path in candidate_test_files),
            )

        current.command_log.write_text(format_command_log(command_results), encoding="utf-8")
        _append_validation_postamble(
            current.validation,
            command_results=command_results,
            command_notes=command_notes + contract["errors"],
            rejected_commands=rejected_commands,
            candidate_test_notes=candidate_test_notes,
            candidate_test_files=candidate_test_files,
        )

        failed_commands = [entry for entry in command_results if int(entry["exit_code"]) != 0]
        if failed_commands:
            failed_list = ", ".join(
                f"`{item['command']}` (exit {item['exit_code']})" for item in failed_commands
            )
            failure = f"Attempt {attempt_number}: validation failed: {failed_list}"
            failures.append(failure)
            append_report_note(current.validation, "Attempt Failure", failure)
            completed_attempts.append(current)
            continue

        _copy_attempt_outputs_to_legacy_targets(
            attempt=current,
            implementation_output=implementation_output,
            validation_output=validation_output,
        )
        for path in [
            *attempt_outputs,
            implementation_output,
            validation_output,
            implementation_output.with_name(f"{implementation_output.stem}-architect.md"),
            implementation_output.with_name(f"{implementation_output.stem}-engineering.md"),
            validation_output.with_name(f"{validation_output.stem}-command-logs.md"),
        ]:
            if path.exists():
                append_file_header(path, apply_changes, goal)
        return final_validation_result

    summary_lines = [
        f"Run failed after {max_attempts} attempts.",
        f"Attempt artifacts root: {attempt_base.relative_to(repo_root).as_posix()}",
    ]
    if failures:
        summary_lines.append("Failure summary:")
        summary_lines.extend(f"- {item}" for item in failures[-max_attempts:])

    if completed_attempts:
        latest = completed_attempts[-1]
        _copy_attempt_outputs_to_legacy_targets(
            attempt=latest,
            implementation_output=implementation_output,
            validation_output=validation_output,
        )
        for path in [
            latest.architecture,
            latest.engineering,
            latest.implementation,
            latest.validation,
            latest.command_log,
            implementation_output,
            validation_output,
            implementation_output.with_name(f"{implementation_output.stem}-architect.md"),
            implementation_output.with_name(f"{implementation_output.stem}-engineering.md"),
            validation_output.with_name(f"{validation_output.stem}-command-logs.md"),
        ]:
            if path.exists():
                append_file_header(path, apply_changes, goal)

    raise RuntimeError("\n".join(summary_lines))
