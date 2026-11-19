# Visual companion

A local browser page that shows mockups and options side by side and records which one the user clicks. The scripts are from superpowers' brainstorming companion (MIT, see `LICENSE.superpowers`), with the remote logo removed and the session folder renamed to `.design-companion/`. `$C` below is this folder: `~/.claude/skills/ckore-design/companion`.

## When to use it

Decide per question. Use the browser only when the user would understand the question better by seeing it: layouts, screens, flows, visual hierarchy, a state diagram. Scope, tradeoffs and approach choices stay in the terminal, even when they're about a UI. "What should the wizard do?" is a terminal question. "Which of these wizard layouts?" is a browser question.

## Start (only after the user said yes)

1. Make sure `.design-companion/` is in the repo's `.gitignore`.
2. Start the server. On Windows the script runs in the foreground, so use `run_in_background: true` on the Bash call:
   ```bash
   bash $C/start-server.sh --project-dir <repo root> --open
   ```
3. Read `<repo root>/.design-companion/<session>/state/server-info` for `url`, `screen_dir` and `state_dir`. Always give the user the **full** URL including `?key=`. The server rejects requests without it.

## The loop

1. Check that `state_dir/server-info` exists and `state_dir/server-stopped` doesn't. If the server stopped, restart it with the same `--project-dir`. It reuses the port and the open tab reconnects.
2. Write a **new** file into `screen_dir` with the Write tool, never a heredoc: `layout.html`, then `layout-v2.html`, and so on. The newest file is served. Write a content fragment; the server wraps it in the frame.
3. In the terminal: the URL, one line on what's on screen, and the question in `ckore-design`'s format ("Which layout, A, B or C? → B"). End the turn.
4. Next turn: read `state_dir/events` (JSON lines, `{"type":"click","choice":"a",...}`) if it exists. The terminal reply is the main answer, and the clicks add to it. The last click is usually the choice.
5. When the next question isn't visual, push `waiting-N.html` with `<p class="subtitle">Continuing in terminal...</p>` so a settled choice doesn't stay on screen.
6. At `ckore-design` step 5, stop it: `bash $C/stop-server.sh <session dir>`. Record the chosen option and the screen file in the handoff's "Decisions".

## Fragment building blocks

```html
<h2>Which layout fits the admin table?</h2>
<p class="subtitle">20 rows at 1280px, filters always visible</p>
<div class="options">                      <!-- add data-multiselect for multi-choice -->
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content"><h3>Filters on top</h3><p>One line on the tradeoff</p></div>
  </div>
</div>
```

- `.cards` > `.card[data-choice]` > `.card-image` + `.card-body`: visual designs to pick from
- `.mockup` > `.mockup-header` + `.mockup-body`: one framed mockup; `.split` puts two side by side
- `.pros-cons` > `.pros` / `.cons`: short lists under a mockup
- Wireframe pieces: `.mock-nav`, `.mock-sidebar`, `.mock-content`, `.mock-button`, `.mock-input`, `.placeholder`
- Text: `h2` title, `h3` section, `.subtitle`, `.section`, `.label`

## Making the options worth choosing

- 2 to 4 options per screen, each labelled, each with its one tradeoff.
- Use the product's real copy, field names and a realistic amount of data. Lorem ipsum hides the problems you're trying to compare.
- For an app with its own design tokens, use the project's colours and spacing tokens inline, so the mockup reads like the product.
- Wireframe fidelity for layout questions, real styling only for look-and-feel questions.
- If a question is about behaviour (what happens on click, a state model) rather than looks, it's a `ckore-prototype`, not a companion screen.
