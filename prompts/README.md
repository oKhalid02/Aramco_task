# Prompts

The exercise requires AI assistance to be disclosed, with prompts kept as versioned files. This folder
holds two kinds.

## `session/` — prompts given to the AI coding assistant

One file per prompt, numbered in order: `NNN_<phase>_<short-topic>.md`. Each file records:

- **Prompt (verbatim)**: exactly as typed, typos included
- **Phase**: which project phase it belongs to
- **What the assistant did**: short summary of actions taken
- **Outputs**: files created or changed
- **Decisions / follow-ups**: anything that feeds the decision log
- **Time spent**: approximate, counted against the 6–8 h cap

## `pipeline/` — prompts used inside the solution

Any prompt the code sends to an LLM (for example, mapping a description to a contracted service, or
extracting rules from the H2 prose contract). Each prompt is versioned: `<name>_v1.md`, `<name>_v2.md`, …
Each new version states what changed and why (what failed on H1 with the previous version). Old
versions are kept, not overwritten.
