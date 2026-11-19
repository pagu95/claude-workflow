---
name: ckore-diagnose
description: Diagnosis loop for bugs, prod incidents and slow paths. Use when the user reports something broken, wrong in prod, throwing, failing or slow, or says "debug", "investigate", "why is X happening". Replaces systematic-debugging.
---

# Diagnose

Built on Matt Pocock's `diagnosing-bugs`, with parts of superpowers `systematic-debugging` and `verification-before-completion` and pstack's principles. The order matters: pin the facts, get a red signal, then theorise. Skip a phase only with a stated reason.

**Profile.** Read the active profile in `~/.claude/profiles/` (the one whose "Applies to" matches this repo). Its sections "Environments and ids", "Prod data access" and "Test and build" fill in the specifics below. If no profile matches, take them from the project's CLAUDE.md and ask for what's missing.

**Reporting rules for every phase:**
- Label each claim in the same sentence as **measured** (a command or query was run), **inferred** or **guess**.
- Never hand the user a check you could run yourself.
- Redact tokens, secrets and customer PII from every command, output and payload you show, and quote only the lines that carry the signal.

## Phase 0: Pin the facts (before reading code)

Most bad investigations start from the wrong environment, branch or id. Write these down in chat first, in one short block:

- **Environment**: which one is broken, using the profile's environment names. Which DB, which deploy target, which branch. If the user didn't say, ask; don't infer it from a URL or a variable name.
- **Identifiers**: the exact ids, and **which kind** each one is (the profile lists the kinds that get confused). Confirm each one resolves to a real record, using the profile's prod data access, before you build on it.
- **Symptom**: the user's words, plus the full error and stack trace if there is one. Note the exact `file:line` and error code before you open any code.
- **Expected**: the result the user expected (fields and status).
- **Done when**: if it's missing, ask one short question.

## Phase 1: Find the divergence

- **Compare.** Find a case that **works** and one that **fails** on the same path: two records, two users, or before and after a deploy. Diff the data, the log lines and the code branches each one takes. The cause is usually a single divergence.
- **Check recent changes.** Look at recent commits and config changes on the failing path.
- **Prod data** goes only through the profile's approved access, with both ids and a time window.
- **Counts and rates.** For any count or rate from prod, list what else the number could be measuring: the wrong env, errors, skipped or cached work, records in an old format, or a time window that's too narrow. Rule each one out with a query, and report the count with its window and filter.

## Phase 2: Build a red loop

Before you theorise, have **one command** that you've already run, that takes seconds, and that asserts **the user's exact symptom**. "Runs without error" doesn't count. Confirm it reproduces the user's failure, not a nearby one: the wrong bug means the wrong fix. Pick from:

1. A failing test at the seam that reaches the bug, using a fixture copied from the real (redacted) prod record.
2. A replay of a captured payload, queue message or webhook body through the handler, run in isolation.
3. A script that runs the function against a local or staging DB seeded with the minimal records.
4. A differential run of the same input through the old and new commit (or `git bisect run`).

Special cases:
- **Intermittent bug.** Don't hunt for a clean repro. Raise the reproduction rate instead: loop it 100 times, run it in parallel, narrow the timing, inject sleeps. Keep going until it fails often enough to debug.
- **Slow path.** Take a baseline measurement first (timing, the query plan or `ckore-explain`), then bisect. Don't add logs. Before you report a speedup or act on a number (from poteto's `benchmark-checklist`): run each side at least 5 times, alternating A, B, A, B, and give the median and range; count errors, since failures are often fast; prove the work ran inside the timed region; name the limiter; and give the change as a share of the end-to-end path the user waits on. A gap smaller than the run-to-run range is no difference.

If you can't build a loop, stop. Say what you tried, and ask for access, a captured artifact, or permission to add temporary logging. **No red command, no hypotheses.**

Then shrink it. Cut fields, records and steps until every remaining part is needed for the failure.

## Phase 3: Hypotheses (short)

Give at most 5 ranked hypotheses, one line each, in this form: "If X, then changing Y makes it go green." Show them to the user in a list of 5 lines or fewer. They often know which one it is. Don't block if they're away.

## Phase 4: Probe

- **One variable at a time.** Run one probe per hypothesis. One debugger or REPL breakpoint beats ten logs, so never "log everything and grep". Tag every temporary log `[DEBUG-xxxx]`, so cleanup is a single grep.
- **Check your lens first.** When a check passes too easily or the data looks wrong, suspect how you looked (the env, the DB, the kind of id, the time window) before suspecting the system.
- **After a restart or deploy.** If it fails only after one of these, suspect persisted state first: caches, records written by older code, payloads already in a queue.

## Phase 5: Smallest fix + regression test

- **Fix the source.** Fix where the system first did the wrong thing, not where it showed. Trace back: who passed in the bad value? Ask whether that state is legitimate. If it is, the code that broke on it is the bug. If it isn't, a guard at the symptom only hides it. Then search for other places with the same fault.
- **Keep the fix small.** Propose the **smallest** fix that turns the loop green. Ask before adding queues, locks, jobs or new tables or collections.
- **Make the repro the regression test.** Watch it fail, apply the fix, watch it pass, then re-run the original loop. If you forced the red by mutating code or a fixture, diff against a pristine copy to prove the mutation actually landed.
- **Use independent expected values.** Take them as literals from the real record or the spec, not recomputed the way the code computes them. A test like that passes by construction.
- **No faithful seam?** Report that as a finding instead of writing a shallow test.
- **After 2 failed fixes, stop.** Write the assumption they shared as one sentence, then run one check that would come out differently if that assumption were false. Tell the user what each fix revealed, and ask whether the design is wrong rather than the code.

## Phase 6: Cleanup and proof

- [ ] The **original** Phase 2 command passes, and its result is quoted in this message. A green unit test or a code change on its own doesn't count. If you didn't run it, write "not run", never "should work".
- [ ] No `[DEBUG-` left (grep)
- [ ] The root cause is stated in one sentence in the PR body
- [ ] Any new trap for the area is added to that area's CLAUDE.md, or handled by the profile's context-upkeep skill
- [ ] If the deciding fact took a deep dig, propose (don't add) one cheap permanent signal, such as a log line or a field, that would have shown it at first look
