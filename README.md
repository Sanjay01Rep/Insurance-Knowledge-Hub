# Insurance Learning Assistant

A simple app on your laptop: upload D365 and insurance documents, then ask questions. Answers that come from your files always show which document they came from.

You do **not** need to be a developer. Follow the steps below in order.

Answers use the model you pick on the **Ask** tab (Gemini, ChatGPT, Claude, Cursor, or Azure OpenAI). Paste that model’s key in **Auth** on the right, or in `.env`. Searching your uploaded files is always **local and free** on this PC. Excel and PDF contents are **never** sent to Tavily or the internet.

---

## Every day (after the first setup)

1. Double-click **run.bat** in this folder.
2. Open **http://localhost:8501** in Chrome or Edge. You should see **v0.7.0** in the header.
3. **Documents:** search or filter, then click a file to expand. Upload stays collapsed until you open it.
4. **Auth:** paste a model key if you have not already, then **Save key**.
5. **Ask:** pick Gemini / ChatGPT / Claude / Cursor / Azure OpenAI, then type a question.

Leave the `run.bat` window open while you work. Close it (or press Ctrl+C) to stop the app.

---

## 1. Install Python (one-time, only if you don't have it)

1. Open: https://www.python.org/downloads/
2. Download Python 3.12 (or newer).
3. Run the installer.
4. **Important:** tick the box **Add python.exe to PATH**.
5. Click Install, then close the installer.
6. Close any terminal windows you already had open (so Windows notices Python).

---

## 2. First-time setup (one-time)

1. Open the folder **Insurance Knowledge Hub** on your Desktop.
2. Double-click **setup.bat**.
3. Wait. The first run can take several minutes while it downloads what the app needs.
4. When you see `Setup finished`, press any key to close that window.

If Windows asks “Do you want to run this file?”, choose **Run**.

---

## 3. Choose an answer model (needed for written answers — not needed to open the empty app)

The empty app still opens without a key. Searching your documents does **not** use a cloud key.

1. Start the app and look at **Auth** on the right (same idea as the Auth token in Test Management Hub).
2. On the **Ask** tab, choose Gemini (free), ChatGPT, Claude, Cursor, or Azure OpenAI.
3. Paste that model’s key in Auth (password box) and click **Save key**.
4. It is written to `.env` and used immediately — no restart.

**Optional web fallback** (only if a question is **not** in your documents):

This app uses the **Tavily Search API**  
`POST https://api.tavily.com/search`

1. Get a key from https://app.tavily.com/
2. Paste it under **Web search (optional)** in Auth and click **Save Tavily key**.

Only your **typed question** is sent to Tavily. Uploaded Excel/PDF/Word files are never uploaded or searched on the internet.

Never send `.env` to anyone. Never paste keys into the app’s **chat** box — only into Auth.

### Where to get each API key

| What you picked | Where to get the key |
|---|---|
| Gemini (free) | https://aistudio.google.com/apikey — create a key, then paste it in Auth or in `.env` as `GEMINI_API_KEY`. |
| ChatGPT | https://platform.openai.com/api-keys — create a secret key (you need billed OpenAI API access, not only ChatGPT Plus). |
| Claude | https://console.anthropic.com/settings/keys — create an API key. |
| Cursor | https://cursor.com/dashboard/integrations — create a Cursor API key. |
| Azure OpenAI | https://portal.azure.com/ — open your Azure OpenAI resource: **Keys and Endpoint**, plus the **deployment name**. |
| Tavily (web fallback) | https://app.tavily.com/ — copy an API key. |
| Groq | https://console.groq.com/keys — then Auth → **Add another model** → Groq. |
| DeepSeek | https://platform.deepseek.com/api_keys — then Auth → **Add another model** → DeepSeek. |
| Other OpenAI-style API | Get a key from that provider, then Auth → **Add another model** → Other, and paste the API address. |

Saved extra models stay on this PC and appear on the Ask tab next time. To remove one: pick it on Ask, then in Auth click **Delete this saved model**. Gemini, ChatGPT, Claude, Cursor, and Azure stay in the list (you cannot delete those).

---

## 4. Start the app (do this every time you want to use it)

In a terminal in this folder, run:

```bat
.\run.bat
```

Or double-click **run.bat**.

Then open **Chrome** or **Edge** and go to:

**http://localhost:8501**

You should see **Insurance Learning Assistant** with two tabs: **Documents** and **Ask**.

Leave the terminal window **open**. Closing it stops the app.

**Do not** use Cursor / VS Code Live Preview. That will show “site can’t be reached”, a blank page, or an **old copy** of the app. Always start with **run.bat** and open **http://localhost:8501**.

`run.bat` closes any previous copy still using port 8501, then starts a fresh one.

Stop the app: in the terminal press **Ctrl+C**.

---

The app’s working files (Python packages) are stored on your PC, not in OneDrive, so the app stays fast. Your documents and the app itself stay in this folder.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| Terminal stuck on `Email:` | Close that window, then run `.\run.bat` again. That prompt is skipped now. |
| `This site can’t be reached` | The app is not running yet. Run `.\run.bat` and **leave it open**, then open http://localhost:8501 |
| `Python was not found` | Install Python (step 1), tick **Add python.exe to PATH**, then close all terminals and run **setup.bat** again. |
| `The app is not set up yet` | Run **setup.bat** first, wait until it finishes, then run **run.bat**. |
| Windows blocked the `.bat` file | Right-click it → Properties → tick **Unblock** → Apply, then run it again. |
| Cursor Live Preview / a random port | Ignore it. Always use **http://localhost:8501** after `run.bat`. |
| App looks like an old version / missing a new button | An old copy was still running. Close extra terminals, double-click **run.bat** (it replaces the old copy), then refresh **http://localhost:8501**. Look for **v0.7.0** in the header. |
| Terminal frozen / “stopping” never finishes | Close that window. If it will not close, open Task Manager, end **python.exe**, then double-click **run.bat** again. |
