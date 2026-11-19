---
name: ckore-blast-radius
description: Find what a change could break outside the diff (other services, apps, jobs and dashboards reading the same data or payloads) and prove the one fact that makes it safe by running real code. Use for "what could this break", before changing a shared lib, schema field, status value or API response, or for a small diff you don't trust.
disable-model-invocation: true
---

# Blast radius

Built on poteto's `blast-radius`, with the merge-danger section of Matt Pocock's `pr` and pstack's idempotency and explain-the-number principles. Listing callers isn't the job, since grep does that. The job is finding the breakage grep doesn't show.

**Profile.** Read the active profile in `~/.claude/profiles/`. Its "Repos and readers" section lists where grep stops for this project, and "Prod data access" says how to check real data. If no profile matches, ask the user which other repos read this data.

## Where grep stops

For every field, status, table or collection, and payload the diff touches, check its readers:

- **The profile's "Repos and readers" list.** Sibling services, mobile or web apps, dashboards, and dependency maps.
- **Work that runs later or elsewhere:** cron jobs, queue consumers and webhook handlers.
- **Values and shapes:** enum and status values compared as strings; field renames or removals (old records still exist in prod); defaults on records written before the change; the indexes the new query depends on.
- **Reruns:** for every handler, job or webhook the diff touches, ask what happens if it runs twice, and what happens if the previous run crashed halfway. If the answer depends on what was left behind, flag it.

## One-way or two-way door

State which this change is:

- **Two-way:** a revert restores the old behaviour.
- **One-way:** a data migration, a deleted field, a message already sent, or a state the old code can't read.

A one-way change needs the "old records" check proven at level 5 and a stated rollback plan.

## How sure are you

Take each safety fact as far down this list as is cheap, and say where it stopped:

1. Asserted. Worthless on its own.
2. Pointed at: a real `file:line`.
3. Walked: you traced the failure case and showed it can't be reached.
4. Ran: a script or test that calls the real code and fails loudly if you're wrong.
5. Observed in data: the profile's prod data access shows prod records have the shape you assume, for example a count of records missing the field. Give the count with its window and filter, and rule out the other things it could be counting (the wrong env, an old format, a window that's too narrow).

## Steps

1. Read the diff, including what it now does differently that the diff doesn't spell out.
2. Find the **one fact** the change is safe because of, for example: "every reader of `status` treats unknown values as pending".
3. Check the readers. A search that finds nothing is still an answer, so give the query you ran.
4. Prove the fact to level 4 or 5.

## Reply (≤250 words)

- **What it does**, including the non-obvious part
- **Door**: one-way or two-way, plus the rollback if one-way
- **The one safety fact**, the level it reached, and the proof (or "unproven")
- **Risks**: how it breaks, `file:line`, how likely and how bad, how to check
- **Cleared**: what you checked and why it's fine, one line each
- **Before merge**: the cheapest test or prod query that would catch the real bug

Paste the "readers checked" list into the PR description. The door and readers feed `ckore-review`'s `Merge danger:` line, which goes first in the PR body.
