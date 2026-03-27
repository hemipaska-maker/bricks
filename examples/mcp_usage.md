# Using Bricks as an MCP Server

## Installation

```bash
pip install "bricks[ai,mcp]"
```

## Configuration (Claude Desktop)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bricks": {
      "command": "bricks",
      "args": ["serve"],
      "env": { "ANTHROPIC_API_KEY": "your-key-here" }
    }
  }
}
```

## Advanced

```bash
# Use a custom config file
bricks serve --config agent.yaml

# Use a different model
bricks serve --model gpt-4o-mini
```

## Tool: `execute_task`

The server exposes a single tool:

| Field    | Type   | Required | Description                                      |
|----------|--------|----------|--------------------------------------------------|
| `task`   | string | yes      | Natural language description of what to compute. |
| `inputs` | object | no       | Input values for `${inputs.key_name}` references.|

Example call:

```json
{
  "task": "filter active users and compute total spend",
  "inputs": {
    "users": [
      {"id": 1, "active": true, "spend": 42.0},
      {"id": 2, "active": false, "spend": 10.0}
    ]
  }
}
```

Example response:

```json
{
  "outputs": {"total_spend": 42.0, "active_count": 1},
  "cache_hit": false,
  "api_calls": 1,
  "tokens_used": 312
}
```

On subsequent calls with the same task description the blueprint is served
from the store: `cache_hit` is `true` and `api_calls`/`tokens_used` are `0`.
