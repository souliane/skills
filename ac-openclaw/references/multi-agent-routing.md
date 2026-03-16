# Multi-Agent Routing

Route different contacts or channels to dedicated agents, each with their own personality, memory, and tools.

## Architecture

```
Signal contact A ──► Agent "assistant" (default, dashboard)
Signal contact B ──► Agent "friend" (casual personality)
Signal contact C ──► Agent "work" (formal, project-focused)
Dashboard        ──► Agent "assistant" (main)
```

Each agent gets:

- **Own workspace** — `SOUL.md`, `AGENTS.md`, `USER.md` in `~/.openclaw/agents/<agentId>/`
- **Own session store** — no cross-talk unless explicitly enabled
- **Own personality** — different system prompts, tone, knowledge
- **Own tool policies** — restrict which skills/tools each agent can use

## Configuration

### Define agents in `openclaw.json`

```json
{
  "agents": {
    "assistant": {
      "model": "claude-sonnet-4-6",
      "systemPrompt": "You are a helpful personal assistant.",
      "workspace": "~/.openclaw/agents/assistant"
    },
    "friend": {
      "model": "claude-sonnet-4-6",
      "systemPrompt": "You are a casual, witty friend. Keep it light.",
      "workspace": "~/.openclaw/agents/friend"
    },
    "work": {
      "model": "claude-sonnet-4-6",
      "systemPrompt": "You are a professional work assistant. Be concise.",
      "workspace": "~/.openclaw/agents/work"
    }
  }
}
```

### Route Signal contacts to agents via bindings

Bindings are deterministic routing rules. Most specific match wins.

```json
{
  "bindings": [
    {
      "agentId": "friend",
      "match": {
        "channel": "signal",
        "peer": { "kind": "direct", "id": "+33612345678" }
      }
    },
    {
      "agentId": "work",
      "match": {
        "channel": "signal",
        "peer": { "kind": "direct", "id": "+33698765432" }
      }
    },
    {
      "agentId": "assistant",
      "match": {
        "channel": "signal"
      }
    }
  ]
}
```

**Routing priority:** peer-specific bindings beat channel-wide bindings. In this example:

- `+33612345678` → `friend` agent (peer match)
- `+33698765432` → `work` agent (peer match)
- Everyone else on Signal → `assistant` agent (channel-wide fallback)
- Dashboard → `assistant` agent (default)

### CLI commands

```bash
# List agents
openclaw agents list

# Add an agent
openclaw agents add --id friend --model claude-sonnet-4-6

# Configure agent workspace
openclaw agents config set --id friend systemPrompt "You are a casual friend."

# Add a binding
openclaw agents bind --id friend --channel signal --peer "+33612345678"
```

## Contact acceptance workflow

When a new Signal contact messages your bot for the first time, you can:

1. **Auto-accept to the default agent** — all new contacts go to `assistant` until you explicitly reroute them
2. **Manual routing** — review new contacts via the dashboard, then bind them to the appropriate agent

There is no built-in "accept request" flow that auto-creates a dedicated agent per contact. You define the agents and bindings manually. But you can script it:

```bash
# When you want to give someone their own agent:
openclaw agents add --id "contact-alice" --model claude-sonnet-4-6
# Copy a personality template:
cp ~/.openclaw/agents/friend/SOUL.md ~/.openclaw/agents/contact-alice/SOUL.md
# Bind their number:
openclaw agents bind --id "contact-alice" --channel signal --peer "+33611111111"
```

## Session isolation

- **DMs** share the agent's main session by default
- **Groups** are automatically isolated: `agent:<agentId>:signal:group:<groupId>`
- Each agent has its own memory and conversation history

## Sources

- [Multi-Agent Routing — OpenClaw Docs](https://docs.openclaw.ai/concepts/multi-agent)
- [OpenClaw Agents CLI](https://github.com/openclaw/openclaw/blob/main/docs/cli/agents.md)
- [Multi-Agent Orchestration Guide](https://zenvanriel.com/ai-engineer-blog/openclaw-multi-agent-orchestration-guide/)
- [Per-Contact Agent Routing](https://eastondev.com/blog/en/posts/ai/20260205-openclaw-multi-agent-routing/)
