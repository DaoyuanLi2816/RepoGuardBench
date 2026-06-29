# Threat model

**Attacker controls** some untrusted repository artifact (README, issue body,
code comment, test log, or agent-rule file).

**Attacker does not control** the developer's system prompt, the agent code,
the test oracle, the sandbox, or the model weights. The developer intends to
fix a specific bug and run the supplied test. The agent reads files, writes
files, runs the local pytest, and may run shell commands.

**Security property.** The agent's actions remain aligned with the developer's
bug-fix task and do not follow instructions embedded in untrusted artifacts.

**Why this is realistic.** Several carriers need neither write access to the
protected branch nor a bypass of code review: issue bodies are writable by
anyone and are increasingly ingested by fix-it agents; agent-rule files and
READMEs travel with cloned/forked/vendored dependencies the agent reads but the
developer never audits; code comments and fabricated test logs enter through
lightly reviewed channels. Human review catches functional defects but is a
weak filter for natural-language instructions hidden in docs and comments —
exactly the highest-risk carriers here. The operative threat is *"attacker
places persuasive text anywhere the agent will read,"* consistent with indirect
prompt injection and the OWASP LLM01 supply-chain surface.

**Attacker assumptions/limits.** Non-adaptive attacker; inert,
workspace-local payloads (the benchmark is releasable without exploit risk).
An adaptive adversary could craft more convincing payloads — out of scope here.
