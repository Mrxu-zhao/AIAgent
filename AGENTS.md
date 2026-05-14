# Repository AGENTS Guide

This file is the working contract for any model or agent that analyzes, reviews, or modifies this repository.

The goal is simple: do not guess, do not skip discovery, and do not produce plans that are disconnected from the real code.

## Mission

- Treat this repository as an AI Agent project with prompt assets, knowledge assets, profiles, team workflow assets, and control-plane code.
- Work from repository facts first, not from generic framework memory.
- Prefer a smaller accurate answer backed by files over a broad answer based on assumptions.

## Required Reads

Before giving a design, root-cause explanation, refactor plan, or code change proposal, read at minimum:

1. `README.md`
2. `CODE_WIKI.md`

Then read the files that are directly related to the task. Do not stop at directory names or summaries.

## Required Workflow

Follow this order unless the user explicitly asks for something narrower:

1. Read the repository entry docs.
2. Identify the current mainline implementation and any compatibility layer.
3. Read the concrete files that implement the relevant behavior.
4. State what you confirmed from code before proposing a plan.
5. Make the smallest change that solves the task.
6. Run validation relevant to the changed files.

If you have not done steps 1 to 4, you are not ready to give a final plan.

## Output Contract

For analysis, design, review, or implementation tasks, include these sections in your working response:

- `已读文件`
- `确认事实`
- `计划改动`
- `验证方式`
- `未确认项`

Rules:

- `已读文件` must list the actual files you inspected.
- `确认事实` must contain only facts supported by those files.
- `计划改动` must map the proposal to specific files or directories.
- `验证方式` must name the tests, commands, or checks you will run.
- `未确认项` must be explicit when information is still missing.

Do not present assumptions as facts.

## Repository Anchors

Use these repository facts as your starting frame:

- Current recommended mainline: `.hermes/team/control_plane/`
- Historical compatibility area: `.hermes/team/调度框架/`
- Team shared knowledge: `.hermes/team/knowledge/`
- Role templates: `.hermes/agents/`
- Runtime profiles: `.hermes/profiles/`
- Global agent behavior prompt: `.hermes/SOUL.md`

Do not assume the historical compatibility area is the default place to edit. Confirm whether the task belongs to the current mainline or to compatibility logic.

## AI Agent Project Checks

When the task involves agent behavior, prompting, knowledge loading, routing, or collaboration flow, check the relevant combination of:

- `.hermes/SOUL.md`
- `.hermes/agents/*/SOUL.md`
- `.hermes/agents/*/config.yaml`
- `.hermes/skills/*/SKILL.md`
- `.hermes/team/knowledge/`
- `.hermes/team/control_plane/`

Do not inspect only one prompt file and claim you understand the agent system.

## Forbidden Behavior

- Do not give a final solution before reading the relevant code.
- Do not infer repository architecture from prior experience alone.
- Do not treat one file as representative of the whole subsystem without checking surrounding files.
- Do not ignore the difference between mainline code and compatibility code.
- Do not make unrelated refactors while solving a scoped task.
- Do not overwrite or revert user changes you did not create.
- Do not create a new branch for this repository unless the user explicitly asks. Work on `master`.

## Change Rules

- Prefer minimal, targeted changes.
- Keep existing naming and directory conventions unless the task requires otherwise.
- When adding documentation, tie it to real repository paths and real workflow expectations.
- When changing behavior, add or update focused tests if there is an existing test surface nearby.

## Validation Rules

After making changes:

1. Run the most relevant tests or checks for the touched area.
2. Report the result clearly.
3. If you could not run a validation step, say so and explain why.

Never say a change is complete without mentioning validation.

## Review Standard

If the task is a review:

- lead with findings,
- prioritize bugs, regressions, incorrect assumptions, and missing tests,
- keep summaries short,
- cite files for each important claim.

## Decision Rule

When in doubt, slow down and read more code.

Accuracy is more important than speed. Evidence is more important than elegance.
