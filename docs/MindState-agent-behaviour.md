Yes. MindState is exactly the right place to unify memory across Codex, GitHub Copilot, and Claude Code. The practical issue is not storage any more. It is **control of behavior**.

And here the answer is slightly inconvenient: you cannot truly *force* those agents from inside the model alone. You can only get reliable behavior by combining three things:

1. a common memory interface they can call,
2. persistent instructions that tell them when to call it,
3. outer execution controls for the cases where instructions are ignored.

All three tools now have MCP integration in some form, which is the obvious integration path. OpenAI documents MCP support for Codex CLI and the IDE extension. Anthropic documents MCP support for Claude Code. GitHub documents MCP support for Copilot Chat, Copilot CLI, and the Copilot coding agent, alongside repository and path-specific custom instructions. ([OpenAI Developers][1])

So the right design is not “teach each agent about Postgres.” It is:

**MindState database → MindState service/API → MindState MCP server → custom instructions / skills / prompt files / wrappers**

That gives you one behavioral surface and three clients.

The core idea is that each agent should see MindState as a toolset with a very small number of cognitive operations. Not SQL. Not raw DB access. Something like:

* `MindState_recall`
* `MindState_remember`
* `MindState_build_context`
* `MindState_find_related`
* `MindState_get_topic_digest`
* `MindState_log_work_session`

That is the minimum viable memory API for coding agents.

Now to your two questions.

First, how do you get the three agents to update MindState?

The clean answer is: do not rely on voluntary memory writes alone. Use a two-tier approach.

The first tier is **instruction-driven updates**. In Codex and Claude Code, MCP tools are a natural fit, and Claude Code also supports skills through `SKILL.md`; GitHub Copilot supports repository-wide instructions, path-specific instructions, and prompt files for reusable workflows. ([OpenAI Developers][1])

So for all three agents you give a standing instruction of roughly this kind:

“When beginning work, recall relevant memory from MindState. When finishing a meaningful unit of work, write back a concise session summary, decisions made, files changed, unresolved issues, and next steps.”

That works reasonably well, but not perfectly. Models skip instructions. They forget. They optimize for the immediate task.

So the second tier is **outer enforcement**.

That means wrappers, hooks, or commands around the agent invocation. For example:

* a shell wrapper around `codex`, `claude`, or `gh copilot` that first calls `MindState_build_context`
* a post-session command that asks the agent for a structured summary and sends it to `MindState_remember`
* git hooks or task runner hooks that persist commit intent, branch context, or worklog entries
* a REPL slash-command such as `/memsave` or `/checkpoint` that you invoke at meaningful milestones

That is the important distinction:

**instructions give you best-effort memory behavior; wrappers and hooks give you operational reliability.**

If you want genuine consistency, the outer layer has to exist.

For coding agents specifically, I would define three write patterns.

The first is **session start hydration**. Before the agent starts serious work, it retrieves context from MindState based on repo, branch, issue, task, or current directory. This is read-only.

The second is **checkpoint writeback**. After a meaningful change, the agent or wrapper writes a compact summary:
what it tried, what changed, what remains open, what it learned about the codebase.

The third is **completion digest**. At the end of a session, a higher-value summary is stored:
task intent, architectural decisions, files affected, tests run, blockers, follow-up items.

That is enough to make memory compound.

Now the second part: how do you ask them to obtain information?

This is much easier. Retrieval is where MCP and custom instructions work best.

Codex supports MCP in CLI and IDE contexts. Claude Code supports MCP and skills. Copilot supports MCP in supported IDE/agent flows and supports repository-wide and path-specific instructions plus prompt files. ([OpenAI Developers][1])

So the standard read path should be:

* agent sees task
* instruction says “consult MindState first for project memory”
* agent calls `MindState_build_context` or `MindState_recall`
* result comes back already shaped for task execution

That last point matters. If your MCP server returns raw notes, retrieval quality will be mediocre. It should return structured, agent-usable context. For example:

* current project summary
* relevant prior decisions
* known conventions
* recent failures
* open questions
* related files/modules
* provenance links

In other words, do not expose “memory search” only. Expose **task-shaped context assembly**.

That is how you make retrieval feel automatic.

Here is the practical pattern I would recommend.

For all three agents, define a shared instruction contract:

At the start of non-trivial work:

* identify repo, folder, branch, task
* call `MindState_build_context`

During work:

* if a new architectural insight, decision, or blocker appears, call `MindState_remember`

At the end:

* call `MindState_log_work_session`

That gives one consistent mental model across all tools.

Now, tool by tool.

For Codex, MCP is the natural route. OpenAI explicitly documents MCP support for Codex CLI and IDE usage. There is also documentation for running Codex in multi-agent workflows and exposing it through MCP-oriented orchestration. ([OpenAI Developers][1])

So for Codex I would do this:

* register your MindState MCP server
* add persistent local instructions saying Codex must hydrate from MindState before substantial work
* create thin shell aliases, for example `codex-mem`, that call MindState first and then launch Codex with the retrieved context injected or referenced
* add a `checkpoint` or `done` command pattern that saves back to MindState

For Claude Code, the model is even cleaner because Claude Code supports both MCP and skills. Skills can bundle instructions and commands in `SKILL.md`, and Claude Code can connect to external tools via MCP. ([Claude API Docs][2])

So for Claude Code I would create a dedicated skill, something like `MindState-memory`, that says:

* before coding, call `MindState_build_context`
* when user says “checkpoint”, call `MindState_remember`
* when user says “close session”, call `MindState_log_work_session`

That is better than relying on a long universal instruction block because it packages the behavior in a reusable unit.

For GitHub Copilot, the surface is a bit more fragmented, but the official docs are clear that Copilot supports repository-wide custom instructions, path-specific instructions, prompt files, and MCP integration in supported environments. The Copilot CLI can also add MCP servers. ([GitHub Docs][3])

So for Copilot I would use three layers:

* `.github/copilot-instructions.md` for global memory behavior
* optional path-specific instructions for subdomains of the repo
* one or two prompt files for explicit memory workflows, such as “load project memory” and “save session memory”
* MCP tools connected so Copilot can actually execute those memory actions

That is the practical answer to your “skills, custom instructions, how would that work?” question:

Codex: mostly MCP plus launcher/wrapper discipline.
Claude Code: MCP plus skills.
Copilot: MCP plus repository instructions plus prompt files.

Now the harder part: what should the instructions actually say?

They should be short, imperative, and behavioral. Not conceptual essays. Something along these lines:

“Before any non-trivial coding task, retrieve MindState context for the current repository, module, and task. Reuse prior decisions and conventions when relevant. When you discover a new design decision, recurring issue, codebase convention, or unresolved blocker, store it in MindState. At the end of a meaningful work session, write a concise session summary including intent, changed areas, key decisions, tests run, and open issues.”

That is enough. Long instruction sets decay.

The MCP server then needs to expose a few purpose-built tools.

I would keep them to six.

`MindState_build_context`
Input: repo, cwd, branch, task, optional issue ID
Output: compact context bundle for the coding task

`MindState_recall`
Input: free-text query plus scope
Output: ranked memory items and summaries

`MindState_remember`
Input: text, type, scope, confidence, tags
Output: stored memory id

`MindState_log_work_session`
Input: task, files changed, decisions, blockers, next steps
Output: session log id

`MindState_find_related_code`
Input: symbol, path, module, concept
Output: related memories, decisions, files, known pitfalls

`MindState_get_recent_project_state`
Input: repo/project
Output: last summaries, active threads, unresolved work

This is enough to make the system useful without making the agents choose among twenty overlapping tools.

There is also a point you should not miss: memory writes should be **structured** even if the user-facing interface is natural language.

So `MindState_log_work_session` should internally store fields such as:

* repo
* branch
* task
* summary
* decisions
* blockers
* files_changed
* symbols_touched
* next_steps
* confidence
* source_agent

That structure is what will later make retrieval good. If you save everything as plain undifferentiated prose, MindState will work, but badly.

Now the uncomfortable truth: you cannot count on all three agents to behave identically. Their support surfaces differ, and their obedience to instructions differs. So you should design for a graded model of reliability.

Level 1 is advisory: custom instructions only.
Level 2 is tool-assisted: instructions plus MCP.
Level 3 is enforced: wrappers/hooks invoke MindState regardless of whether the model remembers to.

You want Level 3 for writes that matter.

Concretely, the easiest robust pattern is probably this:

* create a command-line front door, for example `tmem` or `mstate`
* `mstate codex <task>`: fetch context, launch Codex, save summary afterward
* `mstate claude <task>`: same idea
* `mstate copilot <task>` or `mstate prompt`: same idea where possible in your workflow

Then the agents *can* still use MCP directly during the session, but the minimum hydration and final writeback no longer depend on model obedience.

That also fits your existing REPL/chat access model. You keep the raw/bare-bones route available for direct querying, but layer agent automation above it.

My direct recommendation is this:

Do not begin by trying to make the agents continuously and autonomously maintain memory. That sounds elegant and usually becomes noisy. Start with three disciplined moments:

* start-of-task recall
* explicit checkpoint save
* end-of-task session save

That will already unify memory across Codex, Copilot, and Claude Code without turning MindState into a garbage heap.

The architecture in one sentence is:

**MindState should be the canonical memory substrate, exposed as an MCP server with a small cognitive API, guided by per-agent instructions, and operationally reinforced by wrappers or hooks for guaranteed hydration and writeback.**

If you want, the next useful step is to draft the actual MCP tool contract and the instruction files for all three agents side by side.

[1]: https://developers.openai.com/codex/mcp/?utm_source=chatgpt.com "Model Context Protocol"
[2]: https://docs.anthropic.com/en/docs/claude-code/mcp?utm_source=chatgpt.com "Connect Claude Code to tools via MCP"
[3]: https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot?utm_source=chatgpt.com "Adding repository custom instructions for GitHub Copilot"
