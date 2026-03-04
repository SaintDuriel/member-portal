from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from runtime_tools import (
    build_code_tools,
    build_local_llm,
    build_project_snapshot,
    build_validation_tools,
    output_targets_block,
    task_context_block,
)


def build_agents(repo_root: Path, apply_changes: bool, qa_test_mode: str):
    llm = build_local_llm()
    enable_tool_writes = apply_changes and os.getenv("CREW_ENABLE_TOOL_WRITES", "1").strip() == "1"
    implementation_tools = build_code_tools(repo_root=repo_root, allow_write=enable_tool_writes)
    validation_tools = build_validation_tools(repo_root=repo_root, qa_test_mode=qa_test_mode)

    architect = Agent(
        role="Product Delivery Architect",
        goal="Turn the current MemberPortal codebase and plan into a realistic execution strategy.",
        backstory="You reconcile roadmap intent with current code reality and previous failed attempts.",
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
        backstory=(
            "You execute targeted edits and produce machine-applyable output when direct tool writes are unavailable."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
        tools=implementation_tools,
    )

    validator = Agent(
        role="Quality and Release Lead",
        goal="Validate implementation quality and produce deterministic command + test plans with evidence.",
        backstory=(
            "You ground all release recommendations in real command logs and can author candidate Playwright tests."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
        tools=validation_tools,
    )

    return architect, engineer, implementer, validator, enable_tool_writes


def build_implementation_phase_crew(
    *,
    goal: str,
    repo_root: Path,
    plan_file: Path,
    run_id: str,
    attempt: int,
    apply_changes: bool,
    qa_test_mode: str,
    task_context: str | None,
    prior_attempt_summary: str,
    architecture_output: Path,
    engineering_output: Path,
    implementation_output: Path,
) -> Crew:
    snapshot = build_project_snapshot(repo_root)
    architect, engineer, implementer, _, enable_tool_writes = build_agents(
        repo_root=repo_root,
        apply_changes=apply_changes,
        qa_test_mode=qa_test_mode,
    )
    context_block = task_context_block(task_context)
    targets_block = output_targets_block(repo_root, [architecture_output, engineering_output, implementation_output])
    plan_status = "found" if plan_file.exists() else f"missing ({plan_file.as_posix()})"

    architecture_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Attempt: {attempt}\n"
            f"Project objective:\n{goal}\n\n"
            f"{context_block}"
            f"{targets_block}\n\n"
            f"Planning source status: {plan_status}\n\n"
            f"Prior attempt summary:\n{prior_attempt_summary}\n\n"
            "Produce only the architect result and keep it implementation-focused.\n"
            "Output:\n"
            "1) Current-state summary.\n"
            "2) Top implementation gaps.\n"
            "3) Prioritized execution phases with dependencies.\n"
            "4) Explicitly account for prior attempt failures.\n\n"
            f"Snapshot:\n{snapshot}"
        ),
        expected_output="Architect report with gap analysis and execution phases.",
        agent=architect,
        output_file=str(architecture_output),
    )

    engineering_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Attempt: {attempt}\n"
            f"Project objective:\n{goal}\n\n"
            f"{context_block}"
            f"{targets_block}\n\n"
            f"Prior attempt summary:\n{prior_attempt_summary}\n\n"
            "Use the architect report to build a concrete execution backlog.\n"
            "Output:\n"
            "1) Backlog by platform area.\n"
            "2) Acceptance criteria per item.\n"
            "3) First 5 execution tasks for this attempt.\n"
            "4) Explicit file targets and expected test impacts."
        ),
        expected_output="Engineering implementation plan with explicit file targets.",
        agent=engineer,
        context=[architecture_task],
        output_file=str(engineering_output),
    )

    code_edit_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Attempt: {attempt}\n"
            f"Project objective:\n{goal}\n\n"
            f"{context_block}"
            f"{targets_block}\n\n"
            f"Prior attempt summary:\n{prior_attempt_summary}\n\n"
            "Apply repository edits from the engineering plan.\n"
            f"Apply mode: {'ENABLED' if apply_changes else 'DISABLED (planning-only)'}.\n"
            f"Tool write mode: {'ENABLED' if enable_tool_writes else 'DISABLED'}.\n"
            "Rules:\n"
            "1) Read files before editing.\n"
            "2) Keep edits scoped to this task.\n"
            "3) Never modify secrets, .env files, .git, node_modules, or .next.\n"
            "4) Never edit files in ai-web-studio/outputs/ directly.\n"
            "5) Provide changed-file list and rationale.\n"
            "6) If apply mode is disabled, output a concrete patch plan only.\n"
            "7) If apply mode is enabled, you MUST either:\n"
            "   - use file edit tools to modify repository files (only if tool write mode is enabled), or\n"
            "   - include an applyable unified diff inside a ```diff fenced block, or\n"
            "   - include a structured edit plan in ```yaml with top-level key `edits`.\n"
            "8) Never claim file changes that are not actually present.\n"
            "Structured YAML format example:\n"
            "```yaml\n"
            "edits:\n"
            "  - action: write\n"
            "    path: apps/web/example.ts\n"
            "    content: |\n"
            "      export const example = true\n"
            "  - action: replace\n"
            "    path: apps/web/other.ts\n"
            "    search: \"old\"\n"
            "    replace: \"new\"\n"
            "    count: 1\n"
            "```\n"
            f"Write this report to: {implementation_output.relative_to(repo_root).as_posix()}"
        ),
        expected_output="Implementation report with concrete changes or patch plan.",
        agent=implementer,
        context=[architecture_task, engineering_task],
        output_file=str(implementation_output),
    )

    return Crew(
        name=f"memberportal-impl-{run_id}-a{attempt:02d}",
        agents=[architect, engineer, implementer],
        tasks=[architecture_task, engineering_task, code_edit_task],
        process=Process.sequential,
        verbose=False,
        cache=False,
        memory=False,
        tracing=False,
    )


def build_validation_phase_crew(
    *,
    goal: str,
    repo_root: Path,
    run_id: str,
    attempt: int,
    qa_test_mode: str,
    qa_context: str,
    validation_output: Path,
) -> Crew:
    _, _, _, validator, _ = build_agents(
        repo_root=repo_root,
        apply_changes=False,
        qa_test_mode=qa_test_mode,
    )

    validation_task = Task(
        description=(
            f"Run ID: {run_id}\n"
            f"Attempt: {attempt}\n"
            f"Project objective:\n{goal}\n\n"
            "Produce release validation based only on provided implementation artifacts and prior command logs.\n\n"
            f"{qa_context}\n\n"
            "Output must include all of the following:\n"
            "1) Automated checks outcome summary.\n"
            "2) Manual smoke checks still required.\n"
            "3) Go/No-Go decision with rationale.\n"
            "4) Risks and mitigations.\n"
            "5) Explicit references to architect, engineering, implementation outputs from this and prior attempts.\n"
            "6) Promotion Candidates section for generated tests.\n\n"
            "Required structured blocks in report:\n"
            "```yaml\n"
            "validation_commands:\n"
            "  - pnpm test\n"
            "  - pnpm --filter web test:e2e\n"
            "  - pnpm build\n"
            "```\n"
            "```yaml\n"
            "playwright_candidate_tests:\n"
            "  - path: apps/web/tests/e2e/example.qa.generated.ts\n"
            "    purpose: Validate a user journey or API/UI behavior\n"
            "    content: |\n"
            "      import { test, expect } from \"@playwright/test\";\n"
            "      test(\"example\", async ({ page }) => {\n"
            "        await page.goto(\"/\");\n"
            "        await expect(page.getByRole(\"heading\", { name: \"Guild Sites\" })).toBeVisible();\n"
            "      });\n"
            "```\n"
            "If no candidate tests are needed, still emit an empty list in that block.\n"
            "All candidate tests are syntax-checked by runtime using `playwright test --list`; "
            "invalid TypeScript/Playwright code will be rejected."
        ),
        expected_output="Validation report grounded in executed command evidence with structured execution blocks.",
        agent=validator,
        output_file=str(validation_output),
    )

    return Crew(
        name=f"memberportal-qa-{run_id}-a{attempt:02d}",
        agents=[validator],
        tasks=[validation_task],
        process=Process.sequential,
        verbose=False,
        cache=False,
        memory=False,
        tracing=False,
    )
