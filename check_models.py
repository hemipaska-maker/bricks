"""Diagnostic: check SDK version and list available models."""
import os
import sys

import anthropic

print(f"Python: {sys.version}")
print(f"anthropic SDK version: {anthropic.__version__}")
print()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not set")
    sys.exit(1)

client = anthropic.Anthropic(api_key=api_key)

# List available models
print("Fetching available models...")
try:
    models = client.models.list()
    print(f"Found {len(models.data)} models:")
    for m in models.data:
        print(f"  {m.id}  ({m.display_name})")
except Exception as e:
    print(f"models.list() failed: {e}")

# Try a minimal call with candidate model IDs
print()
print("Testing model IDs with a minimal call...")
candidates = [
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-latest",
    "claude-3-haiku-20240307",
]
for model_id in candidates:
    try:
        resp = client.messages.create(
            model=model_id,
            max_tokens=5,
            messages=[{"role": "user", "content": "Hi"}],
        )
        print(f"  OK  {model_id}")
    except anthropic.NotFoundError:
        print(f"  404 {model_id}")
    except Exception as e:
        print(f"  ERR {model_id}: {e}")
