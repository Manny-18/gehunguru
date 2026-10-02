# GehunGuru (गेहूं गुरु): AI wheat advisory chatbot

An AI chatbot that gives wheat farmers in Punjab, Haryana, western UP, Delhi NCR and north Rajasthan
stage-aware, weather-linked advice in English, Hindi, Punjabi or Hinglish, by text, voice or leaf photo,
and hands them to a human expert when the answer is uncertain or risky.

Use case #18 (Agri-advisory bot for a specific crop/region), AI Applications end-term project.

## What it does

| Feature | How it works |
| --- | --- |
| Crop-stage Q&A | Sowing date gives days after sowing (DAS) and crop stage via a fixed crop calendar (`core/crop_stage.py`); the AI gets this as context. |
| Weather-linked advisory | Live 7-day forecast from Open-Meteo (free, no key). Fixed rules raise alerts for rain, wind, yellow-rust weather, heat and frost (`core/weather.py`). |
| Pest/disease identification | Attach a leaf photo in the chat; Gemini returns up to 3 possible causes, field checks and actions, never a certain diagnosis. |
| Local-language support | Replies in English, Hindi, Punjabi or Hinglish; voice questions via the mic button. |
| Grounded answers | 24-entry wheat knowledge base (`core/knowledge_base.py`); every answer shows its sources. |
| Guardrails | No pesticide doses (and a filter removes any that slip through), phone/Aadhaar masking, fixed emergency replies, prompt-injection refusal, out-of-scope redirect. |
| Human hand-off | Kisan Call Centre 1800-180-1551, KVK link, reference ticket, downloadable chat summary. |
| Failure handling | Model fallback chain, then offline knowledge-base answers if Gemini is down or no key is set. |

## Project structure

```
app.py                     Streamlit app (UI, chat flow, hand-off)
core/knowledge_base.py     Wheat knowledge base (sample data) + offline search
core/crop_stage.py         Crop calendar: DAS -> stage, irrigation schedule
core/weather.py            Open-Meteo client, sample weather weeks, alert rules
core/guardrails.py         Input checks, PII masking, emergency + hand-off detection
core/prompts.py            System prompt and photo-check prompt
core/llm.py                Gemini wrapper: fallback chain, JSON parsing, output guardrails
core/ui.py                 CSS and HTML for the crop track, weather and cards
sample_data/farmer_profiles.csv   4 demo farmers (one per season stage)
tests/                     42 unit tests + a fake AI client for offline testing
.streamlit/config.toml     Theme (colours, Mukta font)
```

## Step 1: get a free Gemini API key (2 minutes)

1. Open https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key**, then copy it. Keep it private: never paste it into the code or GitHub.

## Step 2: put the code on GitHub (5 minutes)

1. Create a free account at https://github.com if you don't have one.
2. Click **New repository**, name it `gehunguru`, choose **Public**, tick **Add a README**, and create it.
3. Click **Add file > Upload files**, drag in everything from the unzipped folder **except** the `.streamlit` folder, and click **Commit changes**.
   Check that the `core`, `sample_data` and `tests` folders appear in the repo.
4. The `.streamlit` folder is hidden on most computers, so create its file by hand:
   **Add file > Create new file**, type the name `.streamlit/config.toml`, paste in the contents of
   `.streamlit/config.toml` from the zip (open it in Notepad/TextEdit), and commit.
   Do **not** upload `secrets.toml.example` with your real key in it.

## Step 3: deploy on Streamlit Community Cloud (5 minutes)

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **Create app > Deploy a public app from GitHub**.
3. Repository: `your-username/gehunguru`, Branch: `main`, Main file path: `app.py`.
4. Optional: set **App URL** to something memorable, such as `gehunguru-yourname`.
5. Open **Advanced settings**: choose Python **3.12**, and in **Secrets** paste:
   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ```
6. Click **Deploy**. The first build takes 2 to 4 minutes. Your shareable link looks like
   `https://gehunguru-yourname.streamlit.app`.

## Step 4: check it works

1. Open the link, click **I understand, start**.
2. In the sidebar, pick the sample farmer **Gurpreet, Ludhiana** and tap the first suggested question.
3. The answer should show "Answered by gemini-..." underneath. If it says "offline", see Troubleshooting.

## Troubleshooting

| What you see | Fix |
| --- | --- |
| "Offline mode: no Gemini API key is configured" | The secret is missing or misnamed. In the app's **Settings > Secrets** it must be exactly `GEMINI_API_KEY = "..."`. Save and reboot the app. |
| Answers say "offline" and Session insights shows "rate limit / quota reached" | The free tier's per-minute or daily limit was hit. Wait a minute (daily quota resets at midnight Pacific time). |
| Session insights shows "model not available" for every model | Google renamed or retired a model. Pick a current Flash model from https://ai.google.dev/gemini-api/docs/models and add `GEMINI_MODEL = "model-id"` to Secrets. |
| "API key rejected" | Create a new key in AI Studio and update Secrets. |
| "Live weather is unavailable" | Open-Meteo was unreachable; choose a sample week under **Weather data**, the rest still works. |
| App shows a "wake up" screen | Free apps sleep when nobody visits for a while. Open your link on the morning of evaluation and click the button. |

## Run on your own computer (optional)

```bash
pip install -r requirements.txt
mkdir -p .streamlit && echo 'GEMINI_API_KEY = "paste-your-key-here"' > .streamlit/secrets.toml
streamlit run app.py
```

Run the tests (no key or internet needed):

```bash
pip install pytest
python -m pytest -q
```

## Data and disclaimer

The knowledge base is paraphrased from public guidance by ICAR-IIWBR Karnal, PAU Ludhiana and CCS HAU Hisar,
compiled as sample data for an academic project; it is not an official document. The sample farmers and sample
weather weeks are invented for demonstration. GehunGuru is an AI assistant: advice is general and should be
confirmed with a KVK or the Kisan Call Centre (1800-180-1551) before spending money on inputs.
