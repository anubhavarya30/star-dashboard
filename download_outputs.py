import anthropic
import os
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# List files Star wrote overnight
try:
    files = client.beta.files.list(
        scope_id="sesn_01LfYNqMFgQe9u1tfpMoWcQt",
        betas=["managed-agents-2026-04-01"]
    )

    print(f"Found {len(files.data)} files:")
    for f in files.data:
        print(f"  - {f.filename}")

    for f in files.data:
        print(f"\nDownloading: {f.filename}")
        content = client.beta.files.download(f.id)
        with open(f.filename, "wb") as out:
            out.write(content.read())
        print(f"✅ Saved: {f.filename}")
except Exception as e:
    print(f"❌ Error: {e}")
    print("The scope_id or betas parameter may be incorrect.")
