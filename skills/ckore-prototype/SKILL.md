---
name: ckore-prototype
description: Settle a design fork by building a throwaway sketch and observing it, instead of asking the user or guessing. Covers UI variants behind one switcher, and logic, state or timing questions run as a tiny script. Use from `ckore-design` when a question is a fact you could observe ("which layout reads better", "does this state model hold", "is this fast enough"), or when the user says "prototype", "mock it up" or "try both".
argument-hint: "the decision this prototype should settle"
---

# Prototype

Built on Matt Pocock's `prototype` and poteto's Prototype playbook and `exhaust-the-design-space` principle. A prototype is throwaway code that answers one question. Here speed beats polish: no tests, no abstractions, no production framework unless the question is about the framework. The rigor is in picking the right decision cheaply.

**Profile.** "Test and build" names the dev server and stack; "Data store risks" says what a prototype must never touch.

## 1. Name the decision

Write the one decision in one line, plus what would decide it ("B wins if the table fits 20 rows without scrolling at 1280px"). No decision means no prototype: go back to `ckore-design`.

Pick the branch:
- **Visual** (layout, density, flow): the user judges by looking.
- **Logic** (a state model, edge cases, a data shape): the user or you judges by driving it through the hard cases.
- **Empirical** (timing, payload size, a library's real behaviour): a number or an output decides it, not a person.

## 2. Build it throwaway

- **Location:** outside the source tree, or in a git-ignored `prototypes/<name>/` folder. Never on the feature branch. Nothing writes to a shared DB. If the question needs data, use a copied, redacted fixture or a scratch table named `prototype_<name>`.
- **Visual:** one HTML file with CDN dependencies, every variant behind one switcher (buttons or a `?v=` param), each labelled. Use the real copy and a realistic amount of real-shaped data, since lorem ipsum hides layout problems. Offer one variant the user didn't ask for if it might win.
- **Logic:** one HTML file or script that pushes the model through the cases that are hard to reason about on paper, and prints the full state after every step.
- **Empirical:** the smallest script that exercises the question, with the number printed. For timing, follow `ckore-diagnose`'s slow-path rules: several alternating runs, errors counted, and proof the work actually ran.
- **One command to run it**, stated in the reply.

## 3. Observe

Open visual variants in the browser pane and screenshot each one at the widths that matter (the profile's breakpoints, or 375 and 1280). Run logic and empirical prototypes yourself and quote the output. The observation is the test. Ask the user only for taste calls a screenshot can't settle.

## 4. Record the decision and throw the code away

- Add the decision to the design's handoff file under "Decisions", with the evidence (the screenshot path or the quoted output) and the rejected variants under "Rejected".
- Delete the prototype, or keep it outside the repo if the user wants to look again. Never commit it with the feature.

## Reply (≤150 words)

The decision, the variants tried, the evidence for each, your pick with the tradeoff, the run command, and a plain note that the code is throwaway. Then return to the `ckore-design` step that asked.
