# Task-Based Model Routing

Read when assigning work. Researched 2026-10-02; refresh live controls before execution. These are starting
recommendations, not measured superiority. Role, model, effort, tools, and isolation are separate choices.
More thinking cannot replace missing requirements or access.

## Choose by work, not job title

| Work | Claude Code candidate | Codex candidate | Evidence to require |
|---|---|---|---|
| Deterministic build/lint/test | Run directly; Haiku only if delegation helps | Run directly; Luna low/medium only if delegation helps | Exit code/log |
| Focused lookup/research | Haiku, effort omitted; Sonnet medium for synthesis | Luna high; max for bounded synthesis | Scoped citations and exact answer |
| Small logic, settled behavior | Sonnet low/medium | Luna high; max for edge-heavy bounded logic | Behavior tests and focused diff |
| Complex logic/state/integration | Sonnet high; Opus high if ambiguity remains | Sol 6.1 medium/high; xhigh for hard reasoning | Contract tracing and regression evidence |
| UI taste/layout/visual system | Opus high; medium for existing-system polish | Sol 6.1 high/xhigh; Astra high for hard design | Approved visual brief, rendered inspection, responsive/accessibility evidence |
| QA cases/browser diagnosis | Sonnet high; Opus for ambiguous cases | Sol 6.1 high; Luna high for executing settled narrow checks | Requirement trace and actual target/build |
| Independent code/security review | Opus high; Sonnet high for bounded review if permitted | Sol 6.1 high; Astra high for hard cross-cutting risks | Fresh context and concrete findings |
| Consequential architecture/advice | Opus high; stronger available family when justified | Astra high; xhigh/max only for demonstrated need | Evidence-backed options; advice never approves |
| Factual docs from accepted results | Sonnet medium; Haiku for mechanical edits | Luna medium/high | Facts, links, audience fit |

Specialist skill runtime requirements override defaults. `Luna max` is useful for bounded logic with many
cases, not a universal minimum. Start lighter for mechanical work; raise effort for edge cases and model
tier for ambiguity, coupled context, or repeated quality failure. Do not escalate merely on a test failure.

Opus-for-UI reflects user preference and a plausible candidate, not a proven taste ranking. Agree visual
references/rubric in planning and inspect rendered output. Additional thinking alone does not establish
visual quality. Avoid mandatory post-implementation aesthetic approval when the brief already settles it.

## Resolve actual capability

1. Inspect live roles/tools, available models, supported effort values, and slots.
2. Record intended and effective selection separately. A requested setting is not proof.
3. Prefer a fitting installed role. If pinned, report its effective runtime or use an available configurable
   general worker with the same scoped implementation contract. Do not weaken permissions/isolation or
   repurpose a restricted specialist to obtain a cheaper model.
4. If overrides are unsupported, inherit/report or use the approved fallback. Do not edit global agents,
   start another platform/CLI, or install capabilities as an implicit fallback.
5. Record observed identity after dispatch when available; otherwise label configured or unknown. Reassign
   within approved quality/cost limits without another prompt; material cost/tool expansion needs authority.

Parallelize only dependency-ready, disjoint writes within live capacity. Three workers is a useful default
upper bound in a four-slot session, not a universal constant. Reuse useful context; isolate QA/review.

## Claude Code

Custom subagents expose `model` (family/full ID/inherit) and `effort`. Supported levels depend on model;
omitted effort inherits. Current effort documentation does not list Haiku as supported, so omit its effort.
Do not assume Agent/Task accepts an effort argument merely because frontmatter does. Check the live client.
Use Opus/Sonnet family aliases for durable guidance; record resolved IDs when exposed.
Sources: [subagents](https://code.claude.com/docs/en/sub-agents),
[effort](https://platform.claude.com/docs/en/build-with-claude/effort).

## Codex

Custom files expose `model` and `model_reasoning_effort`; pinned values take precedence over spawn/defaults.
Live spawn tools may offer dynamic overrides for generic roles. Use exact available IDs such as
`gpt-6-luna`, `gpt-6.1-sol`, `gpt-6-astra`. Preserve specifically requested `gpt-6-sol` when available.

Workspace observation: code-implementer is pinned Sol 6.1/medium, qa-engineer Sol 6.1/high, advisor
Astra/high. Refresh these, not portable constants. “Use Luna” in a pinned role's prompt changes nothing.
If the spawn API disallows overrides with a full-history fork, use a bounded fresh context and required
role contract. Never inherit implementation history into independent QA.
Source: [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## GitHub Copilot

Distinguish CLI, IDE, and cloud. Custom profiles expose `model`; current CLI additionally documents
`models` fallbacks, `modelPolicy`, and `reasoningEffort`. Do not project CLI fields onto IDE/cloud. Choose
required-model policy only when the task truly needs it. Other surfaces use verified controls; effort can
be inherited/unavailable. Apply the task table only to models accessible under the actual client/policy.
Never label a fallback as the requested model.
Sources: [custom agents](https://docs.github.com/en/copilot/reference/custom-agents-configuration),
[CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference),
[models](https://docs.github.com/en/copilot/reference/ai-models/supported-models).

## Google Antigravity

Current subagent schema documents `model: inherit|flash|pro`, without per-agent effort. Map routine work
to Flash and demanding logic/synthesis/visual work to Pro as a tier heuristic. Do not claim Pro means Opus
or a specific Gemini ID. CLI exposes per-run `--model` and `--effort low|medium|high`; `agy models` lists
slugs. Run-level options do not prove subagent effort control. Do not silently open another CLI session.
Sources: [subagents](https://antigravity.google/docs/subagents?tab=cli),
[CLI controls](https://antigravity.google/docs/cli/headless/).

## Research basis and limits

OpenAI recommends lighter Luna for scoped edits, Sol for complex work, and higher Sol effort for polished
visual systems. Calibrate matched tasks rather than making max universal.
[OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection).
Anthropic positions Haiku for straightforward volume, Sonnet for everyday coding, and Opus for demanding
agentic work. These are provider recommendations, not independent comparative benchmarks.
[Anthropic model selection](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model).
Its frontend work supports explicit evaluation of subjective taste, not an absolute Opus-wins claim.
[Frontend evaluation](https://www.anthropic.com/engineering/harness-design-long-running-apps).

Validate with matched small-logic, coupled-logic, UI-rubric, and research tasks. Compare correctness/visual
quality first, then unnecessary questions, latency, and available token/cost telemetry. Unknown metrics
stay unknown. Refresh when live controls or outcomes contradict guidance; this skill does not mutate
shared platform mappings.
