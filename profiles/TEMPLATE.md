# Profile: <name>

Copy this file to `~/.claude/profiles/<name>.md` and fill in what applies. Leave out a section if it doesn't apply. The workflow skills read the active profile for every project-specific fact. Keep it under 80 lines.

## Applies to
<!-- folder paths or git remotes that select this profile -->

## Branches and commits
<!-- base branch, commit message format, hook quirks (e.g. --no-verify), authorship rules -->

## Environments and ids
<!-- environment names (prod, staging…), databases, deploy targets; id kinds that get confused -->

## Prod data access
<!-- the only approved way to read prod data (agent, scripts); what never to do -->

## Repos and readers
<!-- sibling repos, apps and jobs that read the same data or payloads; dependency maps -->

## Data store risks
<!-- review checklist additions for this stack: injection forms, auth gates, hot tables, limits -->

## Risky areas
<!-- task kinds that get an extra spec check in `ckore-build` -->

## Project skills
<!-- repo skills the workflow hands off to: shared-lib changes, finishing a feature, context upkeep, knowledge base -->

## Guardrails
<!-- mechanical mistakes worth a hook (input for `ckore-correct`) -->

## Names
<!-- names to use exactly as written (for `ckore-unslop`) -->

## Test and build
<!-- per-area test commands; what "done" must run -->
