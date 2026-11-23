# Lessons

The ledger of what `ckore-retro` measured and changed. Only `ckore-retro` reads it. One row per lesson, one headline number each; the full evidence is in the commit that applied it (`git log -S'L<n>'`). Rules live where they change behaviour (a skill, CLAUDE.md, a hook) and cite the id as `(Ln)` instead of repeating the story.

Status: `proposed` → `applied <date>` → `verified <date>: <new number>` or `retired <date>: <reason>`. An `applied` lesson that hasn't moved after 2 checks goes to `ckore-correct` (a hook, lint or test). A pattern a script can detect goes to a hook (tool calls, time, context size) or a test/lint in the project (code) from the start, and its prose line is deleted (SKILL §4). Open holds at most 12 rows, and a status cell holds only the latest check; when the table is full, close or merge a row before adding one. Traps holds at most 8 rows under the same rules: a trap is a pattern from the quality pass with no dollar headline, so its headline is the number of sessions that showed it and its re-check is "times it recurred". When a lesson is `verified`, delete its row: the fix lives in the hook, skill or test, and the evidence in git (`git log -S'L<n>'`). Only `retired` lessons and facts that stop a failed fix from being proposed again stay, one line each, under "Don't retry". Keep the trend log to the last 6 runs. Never write a work project's name here: write "work repo".

## Open

| id | since | pattern (headline number) | lives in | re-check | status |
|---|---|---|---|---|---|

## Traps

| id | since | pattern (sessions) | lives in | re-check | status |
|---|---|---|---|---|---|

## Don't retry

## Trend log (last 6 runs; per-project baselines live in that project's memory)
