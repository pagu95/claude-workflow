---
name: ckore-build
description: Build a big feature from a handoff file and plan in a fresh session. The Opus main thread only orchestrates, and Sonnet worker subagents implement one task each. Use for /ckore-build <handoff>, or when the design size gate said "Build in a NEW session". Replaces subagent-driven development.
argument-hint: "path to the handoff file"
disable-model-invocation: true
---

# Build

Slimmed from superpowers `subagent-driven-development` and Matt Pocock's `implement-spec`, based on measured sessions. The cheapest real runs, at about $0.55 per edit, had Sonnet implementers and a light main thread. About 90% of per-task reviews only confirmed, so this skill runs about one agent per task instead of three.

**Your job as orchestrator:** read, dispatch, check, commit. Don't implement tasks yourself, and don't read whole files a worker will read anyway. Keep your own context small.

## 1. Load (one message, all reads together)

- The handoff file from the argument, then the plan it points to.
- The active profile in `~/.claude/profiles/` (named in the handoff). You'll need "Branches and commits", "Risky areas", "Project skills" and "Test and build".
- The worktree, branch and base the handoff names. Confirm the branch is checked out, and that `git status` is clean before you start.
- The root CLAUDE.md and the area CLAUDE.md for each path the plan touches. Read only their gotchas sections. An area with no CLAUDE.md has no area gotchas; that's not an error.
- Check that the handoff's env and ids are still marked verified. If they aren't, verify them through the profile's prod data access before task 1.

Post a 3-line start note: the goal, the number of tasks, and the first batch.

## 2. Batches

Group the plan's tasks into batches:
- A batch may run in **parallel** only if its tasks touch **disjoint files** and don't depend on each other.
- Anything else runs **sequentially**.
- Tasks that touch a shared lib or the schema run alone, with the profile's shared-lib skill (if any) in the worker brief.

## 3. Worker brief (Agent tool, `model: sonnet`)

Each worker gets:

```
Task <n>/<N>: <task text copied verbatim from the plan>
Repo: <absolute path>  Branch: <branch>  Base: <base>
Area gotchas (pasted by you, ≤30 lines): <from the area CLAUDE.md files you read in step 1>
Files to change: <from plan>. Don't re-read whole CLAUDE.md files; the gotchas above are what applies.
Rules (the `ckore-tdd` skill, in short): one behaviour per test through the public interface; run it and see it fail
for the missing behaviour, not a typo; smallest code to green; expected values are literals from the spec;
mock only network, time and third-party clients.
Run: <exact test command for this area, from the profile/CLAUDE.md>. Don't run the whole suite unless the plan says so.
Do NOT commit, push, or touch files outside the list. If a file grows beyond the plan, stop.
Issue independent reads/greps together in one message.
Report (≤150 words):
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Files changed
- Test command + result (quoted)
- Concerns or questions
```

## 4. After each batch (you, not another agent)

1. For each worker report:
   - **DONE:** run `git diff --stat`, then re-run the task's test command yourself and quote the result. A worker's "passed" is a claim until you've seen it.
   - **DONE_WITH_CONCERNS:** read the concern. Fix it with a follow-up brief, or note it for the final review.
   - **NEEDS_CONTEXT:** add the missing context and re-dispatch on Sonnet.
   - **BLOCKED** because of reasoning or design: re-dispatch once on **Opus** with what the Sonnet worker learned. If it's still blocked, stop and ask the user.

   Never retry the same brief on the same model unchanged.
2. **Spec check, only for tasks in the profile's "Risky areas".** Read the task's diff hunk against the task text yourself. No reviewer agent.
3. **Commit** each task separately, using the profile's commit format and hook rules.
4. **Update the handoff file:** append "Task n done (commit)" under Verified. This lets a crashed or compacted run resume from the file.

## 5. Finish

1. Run the area's full test and build commands once and quote the results.
2. `ckore-blast-radius`, if the plan touched data, a payload or a lib that other code reads.
3. `ckore-review` (2 agents, 1 pass), then fix the findings by its section 5.
4. The profile's finish skill, if it has one (with any personal overrides the profile lists), or else open the PR yourself. The PR body goes through `ckore-unslop`.

## Stop and ask the user when

- Two tasks in a row come back BLOCKED.
- A worker's change contradicts the plan or the design decisions.
- The plan turns out to be wrong. Say which task and why in 3 lines or fewer, and propose updating the plan. Don't improvise a redesign.
