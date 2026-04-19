# UNDatathon

A published version of the dashboard can be found here: https://fynnstarke.com. It is password-protected, so we will share the credentials with the team over Discord.

## Run Locally

### 1. Install dependencies

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables (optional)

Create a `.env` file in the project root.

```env
# Optional: Enables AI search and summary features.
ANTHROPIC_API_KEY=your_key_here
```

If `ANTHROPIC_API_KEY` is missing, the dashboard still runs and shows a fallback summary message.

### 3. Start the dashboard

From the project root:

```bash
python dashboard/main.py
```

Then open:

```text
http://localhost:8000
```