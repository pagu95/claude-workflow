# Writing the plan

Adapted from superpowers `writing-plans`. Read this only when the work is more than a few hours. The plan is for a worker that hasn't seen the codebase or this conversation. It writes good code once it knows the exact interface and the exact test. What it can't know is what you decided, so the plan records exactly that, and nothing more.

Save it next to the handoff: `~/.claude/handoffs/<TICKET>-<YYYY-MM-DD>-plan.md`, and put its path in the handoff's "Artifacts".

## Header

```
# <ticket> — <goal in one sentence>
Spec: ~/.claude/handoffs/<handoff file>    Profile: <name>
Global constraints: <the spec's project-wide rules, exact values copied, one line each>
Review focus: <up to 5 inputs or failure modes the spec implies but no test covers yet, most likely first.
               Each one gets its test added to the task that owns the code.>
```

## Files first

Before any tasks, list every file to create or change, with its one responsibility. Follow the repo's existing layout. Files that change together stay together.

## Tasks

A task is the smallest unit that carries its own test cycle and could be rejected on its own. Setup, config and docs fold into the task that needs them.

```
### Task N: <name>
Files: create `path`, modify `path:lines`, test `path`
Interfaces: consumes <exact signatures from earlier tasks>; produces <exact names and types later tasks use>
1. Failing test `<test name>`: <the assertions, with the spec's exact values>
2. Run `<command>` → expect FAIL: <the reason>
3. Implement `<signature>` in `<file>`. One line on the approach only if the signature and test leave a real choice.
4. Run `<command>` → expect PASS
```

No commit step: `ckore-build` and the inline path commit per task in the profile's format.

## What a step must contain

A step is done when the worker can write exactly one reasonable thing from it. Lines that decide nothing ("handle edge cases", "add validation", "TBD") are gaps. A function body that the signature and the test already determine is a transcript, so leave it out. A plan longer than the code it describes has written the code instead.

## Self-review (yourself, no subagent)

1. **Coverage:** every requirement in the spec points to a task.
2. **Steps:** no step decides nothing, and none carries a body the test already fixes.
3. **Names:** signatures and names in later tasks match the earlier tasks that define them.
4. **Review focus:** each line has its test in the owning task.
5. **Proportion:** if code blocks are most of the plan, replace bodies with signatures and assertions.

Fix what you find inline, then go to the size gate. Don't ask the user to choose an execution method; the size gate decides.
