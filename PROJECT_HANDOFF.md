# What We Built and How to Rebuild It

This is a sanitized project handoff for the local single-user AI email classification dashboard. It summarizes what was built, how the pieces fit together, how to run it, and what a new builder should understand before continuing development.

It intentionally excludes secrets, OAuth tokens, API keys, private Gmail data, local machine-specific paths, and personal runtime state files.

## Short Summary

We built a local Flask web app called **Duc Haba Atelier / Agentic AI Email Classifier**. The app helps a single user turn email overload into a structured dashboard. It can load synthetic demo emails, uploaded email JSON, or live Gmail messages, then classify them into five categories:

- Urgent Priority
- Work
- Personal
- Social Media
- Spam

The app supports both deterministic mock classification and OpenAI-powered classification. It also includes a daily inbox brief, category charts, prompt versioning, ground-truth testing, raw email retrieval, and AI-generated editable reply drafts.

The latest release at the time of this handoff is:

`v0.70`

GitHub repository:

`https://github.com/duchaba/codex-email-classification`

## Why The App Matters

The app is designed around one practical idea: not every email deserves the same attention. It helps separate real work and personal obligations from newsletters, promotions, social updates, and spam-like noise.

The most important design principle is that the user should stay in control:

- Classification does not run automatically on startup.
- The user chooses the data source.
- The user chooses whether to use mock rules or AI.
- Prompt versions are visible and selectable.
- Gmail sending requires explicit confirmation.
- Ground-truth test values are protected and never changed by classification.

## Chronological Build Log

This section describes the development conversation in order. It is written as a sanitized project history so another builder can understand not just what exists, but why the features and fixes were added.

### 1. Initial Local App Build

The project started as a request to build a local, single-user, agentic Python email classification dashboard. The goal was a dashboard that could classify email, summarize activity, and let the user experiment with either mock rules or an AI model.

Core foundation added:

- Flask backend app.
- Local dashboard UI.
- Synthetic email fixture support.
- Email classification workflow.
- Summary cards and category overview.
- Local JSON data storage.
- Agent-style Python classes for fetch, preprocess, classify, summarize, chart, audit, and prompt management.

The first priority was getting a runnable local app rather than designing a production SaaS product.

### 2. Startup And Runtime Questions

After the initial build, the app was started locally and checked from the browser. The user asked whether it was ready to run, which command to use, and when the site was ready.

What was clarified:

- The app runs locally with `python run.py`.
- The local site is served on `http://127.0.0.1:5000`.
- The app is intended for one local user.
- Background Flask processes should be stopped when development pauses.

This created the operating rhythm used throughout the project: run locally, inspect in the browser, fix, verify, stop services when done.

### 3. Gmail And OpenAI Configuration

The user asked how to connect Gmail and where to add the ChatGPT/OpenAI key.

What was added or clarified:

- `.env` is used for the OpenAI key.
- `OPENAI_API_KEY` enables AI mode.
- Without an OpenAI key, the app falls back to mock classification.
- `data/client_secret.json` is used for the real Google OAuth client secret.
- `data/client_secret_sample.json` was later added as a safe example file.
- `data/token.json` is generated locally after Gmail OAuth succeeds.

Important security decision:

- Real `.env`, OAuth client secret, Gmail token, and real email data are not committed.

### 4. Making Mock Vs AI Classification Obvious

The user asked whether classification was actually using AI. That revealed a UX problem: the dashboard did not make it obvious whether the app was using mock rules or an AI model.

UI and logic improvements:

- Added clearer classification engine status.
- Made mock-vs-AI behavior more visible in the interface.
- Kept fallback behavior explicit: missing API key means mock mode.
- Improved dashboard messaging so the user can tell what engine is active.

This mattered because the app is partly an AI demo and partly a practical tool; users must know which mode produced the result.

### 5. Category System Redesign

The user changed the taxonomy to five top-level categories:

- Urgent Priority
- Work
- Personal
- Social Media
- Spam

Several old categories were moved into subcategories:

- `News & Releases`, `Sales & Marketing`, and `Invitations & Events` became subcategories under Social Media.
- `Bills & Utilities`, `Personal Projects`, `Banking`, and `Friends` became subcategories under Personal.

Important behavior changes:

- Graphs and summaries show only the five top-level categories.
- Subcategories remain useful detail but do not drive the main dashboard counts.
- The classification prompt was rewritten to reflect the new taxonomy.
- The app was adjusted so each email belongs to exactly one primary category.
- The category priority order became: Urgent Priority, Work, Personal, Social Media, Spam.

This was one of the major product-shaping decisions. It turned the app from a broad classifier into a focused triage dashboard.

### 6. GitHub Upload And Repository Setup

The user asked to upload the project to GitHub under:

`duchaba/codex-email-classification`

What happened:

- Git repository was prepared.
- GitHub authentication was completed by the user.
- The project was pushed to GitHub.
- Later changes were committed, tagged, pushed, and released across multiple versions.

Important distinction learned later:

- A Git tag is not the same thing as a GitHub Release.
- Tags such as `v0.70` can exist while the GitHub Releases sidebar still shows an older release unless a release is explicitly created.

### 7. Synthetic Email Dataset Handling

The user noticed the synthetic email file was not visible under `data/` in Git and asked where the 200 synthetic emails were stored.

Fixes and changes:

- Synthetic emails were moved into a tracked file under `data/synthetic_emails.json`.
- Startup logic was changed to generate the synthetic data only if the file is missing.
- The data file became part of Git so the project is reproducible.
- Later, the user asked to generate 50 synthetic emails using AI, with full email content in `full_body_optional`.

Important dataset design:

- `body_preview`, `category`, and `subcategory` are prediction/runtime fields and start empty.
- `expected_category` and `expected_subcategory` are ground-truth fields.
- Classification must not overwrite expected values.

This separated raw input, expected labels, and model predictions.

### 8. Ground-Truth Testing Feature

The user wanted another agent to test AI category and subcategory predictions against expected values and show accuracy plus a graph.

Feature added:

- `GroundTruthTestAgent`.
- Gear-panel action named **Test Ground Truth**.
- Accuracy report comparing:
  - `category` vs `expected_category`
  - `subcategory` vs `expected_subcategory`
- Chart comparing predicted and expected category distribution.

Important behavior:

- The test does not rerun classification if category/subcategory values already exist.
- The test does not modify `expected_category` or `expected_subcategory`.
- The expected labels are treated as ground truth.

This made the project testable as an AI evaluation app, not just a dashboard.

### 9. Startup Classification Behavior

The app originally classified automatically on startup. The user asked that startup should not automatically run classification.

Change made:

- Startup loads the available email data.
- Classification waits until the user clicks the classification button.

Reason:

- The user should control cost, timing, and whether AI is invoked.
- This prevents accidental OpenAI calls on every restart.

### 10. Prompt Strictness And Urgent Priority Fixes

The user noticed that too many emails were being classified as Urgent Priority. In particular, many marketing, social, or support-style messages were incorrectly elevated.

Prompt policy was rewritten multiple times to make urgent stricter:

- Only real work or real personal obligations can be elevated to Urgent Priority.
- Marketing urgency is not real urgency.
- Generic `support@` sender patterns are not urgent by default.
- Social media, newsletters, sales, releases, invitations, and promotions should not become urgent.
- Work is narrowly tied to GenAI Incubator and ELVTR.
- Suspicious messages pretending to be urgent should be Spam.

This was a major classification-quality lesson: the app needed a much narrower definition of urgent than a general-purpose AI model might infer.

### 11. UI Redesign Inspired By Uploaded Image

The user uploaded an illustrated AI practitioner/builder infographic and asked for the dashboard UI to adopt that visual style.

UI direction:

- Friendly illustrated dashboard.
- Warm colors.
- Rounded cards.
- Playful but practical information hierarchy.
- Custom icons and visual treatment inspired by the reference image.

Specific UI improvements:

- Better dashboard layout.
- Larger, friendlier cards.
- Improved chart container so the graph stays inside the Category Overview card.
- About box in the lower-left area.
- The About box shows:
  - Original Author: Duc Haba
  - GNU 3.0 license
  - Current version number

This became the `v0.20` visual milestone.

### 12. Version Tags And About Box Versioning

The user noticed the About box still said `v0.40` even after the project had advanced.

Fix:

- `config.py` was updated so the app can resolve the current version from the latest local Git tag.
- `APP_VERSION` can still override the displayed version if needed.
- The About box now follows tags such as `v0.70`.

Important note:

- The About version updates from local Git tags, not automatically from GitHub Releases.
- If the local repo does not have the latest tags fetched, the displayed version may lag.

### 13. Separating Mock And AI Classifier Agents

The user inspected the code and wanted the original `EmailClassifierAgent` split into two agents.

Refactor:

- `MockEmailClassifierAgent` handles deterministic local rules.
- `AIEmailClassifierAgent` handles OpenAI-backed classification.
- Routing logic chooses the right agent based on engine/mode and API availability.

Reason:

- Mock and AI logic have different responsibilities.
- Separate agents make the code easier to reason about, test, and extend.

This became part of the `v0.30` milestone.

### 14. Prompt Version File And Prompt Manager Behavior

The user asked where the classification prompt is stored and whether the prompt manager reads from the prompt version JSON file.

Clarified and improved:

- Classification prompts live in `data/prompt_versions.json`.
- `PromptManagerAgent` reads prompt versions from that file.
- The prompt version file was added to Git.
- Runtime prompt selection state is stored separately and ignored.

This allowed prompt history to become a first-class part of the app.

### 15. Taxonomy Migration Prompt Safeguard

A prompt version with `source: taxonomy-migration` was created automatically during an earlier taxonomy migration. The user later deleted it on GitHub and asked why it was created.

Explanation:

- It was created to keep the saved prompt aligned with the new five-category taxonomy.
- The intent was helpful, but automatic prompt creation was too surprising.

Fix:

- The app no longer silently creates taxonomy-migration prompt versions.
- It prompts the user to accept or reject taxonomy migration before creating a new version.
- If the user is manually editing the prompt and saves/runs it, the taxonomy migration popup should not appear.

This preserved safety while restoring user control.

### 16. Classification Prompt Panel Improvements

The user wanted more control over prompt versions.

UI and logic changes:

- Added a dropdown to select prompt versions.
- Default selection is the latest prompt version.
- Each version shows who created it, such as `user`, `default`, or `taxonomy-migration`.
- The prompt preview area was widened.
- Added option to run the currently selected prompt without creating a new version.
- Added `Active prompt: ...` label.
- Dropdown selection is only a preview.
- Active prompt changes only after clicking run or save-and-run.
- Dropdown width was reduced to fit the longest option more naturally.

This made the prompt workflow clearer:

- Select means preview.
- Run means activate and classify.
- Save means create history.
- Save and run means create history, activate, and classify.

### 17. Daily Brief With AI

The user asked that if AI classification is used, the **At a Glance / Today's Brief** box should use AI to write a short, witty, easy-to-read summary.

Added:

- `DailyBriefAgent`.
- OpenAI-backed brief generation when AI mode is active.
- Mock/local fallback when AI is unavailable.

Then the user said a single big paragraph was too hard to skim.

Improvement:

- The brief was formatted with blank-line topic breaks.
- The tone stayed short, witty, and readable.

This made the dashboard feel more human and less like a dense report.

### 18. Raw Email Retrieval And AI Response Drafting

The user asked that for emails in Urgent Priority, Work, and Personal, each email should include:

- Retrieve raw email
- AI write response

Added:

- Raw email retrieval button.
- AI response draft button.
- `EmailResponseAgent`.
- OpenAI response generation through the OpenAI service.
- Editable draft text area.
- Save draft button.
- Send button.

Important safety behavior:

- Drafts can be saved locally.
- Sending requires Gmail connection and explicit user confirmation.
- Raw body retrieval is on demand, reducing unnecessary full-body Gmail fetches.

This became part of the `v0.40` milestone.

### 19. AI Token And Cost Estimate

The user asked for an approximate token and cost estimate to classify 50 emails using `gpt-4.1-mini`.

The estimate was discussed as approximate because real cost depends on:

- Full prompt length.
- Email body length.
- Whether body previews or full bodies are used.
- JSON output size.
- Retries or failed calls.

The practical takeaway:

- Using previews/snippets is much cheaper than sending full bodies.
- Batch classification can reduce repeated prompt overhead.
- Mock mode is useful for free local testing.

### 20. Gmail OAuth Fixes

When connecting Gmail, the user hit:

`OAuth 2 MUST utilize https.`

Fix:

- The app allows insecure transport only for localhost-style OAuth redirects during local development.

Then the user hit:

`Missing code verifier.`

Fix:

- The app persists the PKCE code verifier during OAuth connect.
- The callback passes the verifier back when exchanging the authorization code.

These fixes became part of the `v0.50` milestone.

### 21. Gmail Retrieval Performance And Display Bug

The user reported that retrieving and classifying Gmail took more than five minutes, then no email displayed, and the status still showed `synthetic demo`.

Fixes:

- Gmail retrieval was optimized to avoid fetching every full body upfront.
- The app retrieves Gmail metadata/snippets first.
- Full bodies are retrieved later only when needed.
- Frontend state was fixed so Live Gmail mode remains visible after retrieval/classification.
- Classification and data refresh behavior were adjusted so results actually display after Gmail processing.

This was one of the most important usability fixes because it moved Gmail from slow and confusing to practical.

### 22. Gmail Count For Today's Emails

The user noticed Gmail had more emails today than the app retrieved.

Investigation and fix direction:

- The app needed to be careful about local date boundaries, Gmail query behavior, pagination, and filtering.
- Retrieval was adjusted to better fetch all messages for the current local day instead of returning a partial set.

Lesson:

- Gmail API search and local calendar-day logic need careful handling because timezone and pagination can make results appear incomplete.

### 23. Status Bar And Gear Panel UX

The user asked that retrieving Gmail and running classification show a status bar.

Added:

- Status/progress bar for Gmail retrieval.
- Status/progress bar for classification.
- Status/progress bar for raw email retrieval.

The user also asked that selecting Live Gmail in the gear panel should close the panel immediately so the status bar is visible.

Fix:

- Gear panel closes right after Live Gmail selection begins.

Reason:

- During long operations, the user needs visible feedback instead of a hidden busy state.

### 24. Email Reading Font Size

The user said the display font for reading each email was too small and should match Today's Brief.

UI fix:

- Email reading/detail font family and size were adjusted to match the Today's Brief style.

This improved readability for the core email-review workflow.

### 25. Upload Email JSON

The original button was named `Upload CSV`, but the app workflow actually uses JSON email data.

Fix:

- Button renamed to `Upload Email JSON`.
- Upload logic was routed through the same load-agent flow as startup data loading.
- Button was moved under the gear icon.

This removed a mismatch between the UI label and the real file format.

### 26. Email Ordering

The user asked that email listing be chronological with the latest time on top.

Fix:

- Email display sorting was adjusted so newest messages appear first.

This matches normal inbox expectations.

### 27. Summary Card Click Behavior

The user asked that the four summary cards be clickable:

- Processed today
- Top category
- Need attention
- Need review

Fix:

- Summary cards now navigate/filter to their respective output sections.

This made the dashboard summary more than decoration; it became navigation.

### 28. Project Releases And Milestones

The project was repeatedly committed, pushed, tagged, and sometimes released:

- `v0.10`: Base functionality complete.
- `v0.20`: Fantastic illustrated UI update.
- `v0.30`: Separate AI and mock classifier agents; prompt version tracking.
- `v0.40`: AI daily brief, raw email retrieval, editable response drafts.
- `v0.50`: Gmail OAuth local callback and PKCE fixes.
- `v0.60`: Gmail retrieval, status UX, prompt/classification refinements.
- `v0.70`: Prompt version selection, active prompt behavior, migration safeguards, version display from Git tags.

The user confirmed that rollback to a tag such as `v0.10` is possible by resetting/checking out that tag, though doing so should be treated carefully because it changes the working tree.

### 29. Service Shutdown And Restart Habit

Many development cycles ended with the user asking to stop the app and kill background services or open listening ports.

Operational practice:

- Find the Flask process for this project.
- Stop it.
- Check listening ports, especially port `5000`.
- Restart only when the user asks.

This matters because local web apps can quietly keep running and confuse later tests.

### 30. GitHub Sync Habit

The user often updated GitHub directly and then asked for a pull and sync.

Operational practice:

- Pull from GitHub before continuing.
- Restart the app after syncing when requested.
- Be careful not to overwrite user changes.

This kept local and remote project state aligned.

### 31. Safe Sharing Request

The final request was to create a shareable summary of the whole conversation for a friend, without secrets.

This handoff file was created for that purpose.

Sanitization choices:

- No OpenAI key.
- No OAuth client secret.
- No Gmail token.
- No private Gmail message text.
- No personal browser session details.
- No local runtime state values.
- Repo-relative paths are used where possible.

The goal is that a friend can understand what was built, why decisions were made, and how to rebuild the project safely.

## Current Feature Set

### 1. Data Sources

The app supports three email input modes:

`Synthetic demo`

Uses `data/synthetic_emails.json`. This file contains demo emails with ground-truth labels for testing. The raw prediction fields are intentionally blank before classification.

`Uploaded email JSON`

The user can upload a JSON array of email objects. Required fields:

- `sender_email`
- `subject`

Optional fields include:

- `email_id`
- `date`
- `sender_name`
- `body_preview`
- `full_body_optional`

`Live Gmail`

Uses Google OAuth to fetch Gmail messages for the current local calendar day. Gmail retrieval is optimized to fetch metadata/snippets first, then retrieve full email bodies only on demand when the user asks to view raw email or draft a response.

### 2. Classification Modes

`Mock rules`

Uses deterministic local logic. This mode is useful for development, demos, tests, and running without an OpenAI API key.

`AI model`

Uses OpenAI through `services/openai_service.py`. The current default model is:

`gpt-4.1-mini`

The app falls back to mock mode when no API key is configured.

### 3. Main Categories

The app uses five primary categories:

- `Urgent Priority`
- `Work`
- `Personal`
- `Social Media`
- `Spam`

Important classification policy:

- An email must belong to exactly one primary category.
- Work is narrowly defined around the user's actual work domains: GenAI Incubator and ELVTR.
- Urgent Priority is intentionally narrow and should only be used for truly urgent qualifying work email under the current prompt policy.
- Social media, newsletters, marketing, sales, events, product releases, and support-style messages should generally not become urgent.

### 4. Subcategories

Social Media subcategories:

- `News & Releases`
- `Sales & Marketing`
- `Invitations & Events`

Personal subcategories:

- `Bills & Utilities`
- `Personal Projects`
- `Banking`
- `Friends`

The graph and summary focus only on the five primary categories, not subcategories.

### 5. Prompt Versioning

The Classification Prompt panel supports:

- Viewing prompt versions.
- Seeing who created a version, such as `user`, `default`, `reset`, or `taxonomy-migration`.
- Previewing a prompt version from a dropdown.
- Seeing a separate active prompt label.
- Running the selected version without creating a new prompt.
- Saving a prompt as a new version.
- Save and rerun, which saves the prompt and activates the new version.

Important behavior:

- Changing the dropdown only previews a prompt.
- It does not make that version active.
- `Run selected version` makes the selected prompt active, then runs classification.
- `Save prompt` creates a new version but does not activate it.
- `Save & rerun` creates a new version, activates it, and runs classification.

### 6. Taxonomy Migration Safeguard

Earlier, the app could automatically create a prompt version with:

`source: taxonomy-migration`

That behavior was changed. Now taxonomy migration prompts require manual approval.

The app can detect a possible taxonomy prompt update, but it asks the user to accept or reject it before creating a new prompt version.

Local user decisions are stored in ignored runtime files and should not be committed:

- `data/prompt_migration_decision.json`
- `data/prompt_selection.json`

### 7. Dashboard UI

The UI was redesigned to use a playful illustrated dashboard style inspired by an uploaded AI-builder/practitioner infographic.

Important UI elements:

- Top welcome card.
- Classification engine status indicator.
- Status/progress bar for longer operations.
- Summary cards:
  - Processed today
  - Top category
  - Needs attention
  - Needs review
- Category overview chart.
- Today's brief.
- Email list with expandable details.
- Prompt editor.
- Gear/setup panel.
- About box with author, license, and current version.

The About version now auto-resolves from the latest local Git tag. For example, tag `v0.70` displays as `v0.70`.

### 8. Status Bar

A visible status/progress bar appears during:

- Live Gmail retrieval.
- Classification.
- Raw email retrieval.

The status bar is indeterminate because the current backend routes return when the operation finishes rather than streaming live progress updates.

### 9. Ground-Truth Testing

The gear/setup panel includes **Test Ground Truth**.

It compares saved synthetic predictions against:

- `expected_category`
- `expected_subcategory`

Important rules:

- It does not rerun classification.
- It does not call OpenAI.
- It does not call mock rules.
- It does not modify expected labels.
- It reports accuracy and a chart comparing prediction vs expected labels.

### 10. Raw Email Retrieval And AI Draft Replies

For emails in:

- Urgent Priority
- Work
- Personal

The UI can show:

- `Retrieve raw email`
- `AI write response`

AI-generated responses are editable and can be saved locally. Sending through Gmail is available only for live Gmail messages and requires explicit confirmation.

## Technology Stack

Backend:

- Python
- Flask
- Google Gmail API client libraries
- OpenAI Python SDK

Frontend:

- Server-rendered HTML template
- Vanilla JavaScript
- CSS
- Canvas-based charts

Testing:

- Pytest
- JavaScript syntax check with `node --check`

Data:

- JSON files under `data/`
- Local runtime state is ignored by Git where appropriate

## Major Files And Responsibilities

`app.py`

Main Flask app. Defines routes, app setup, dashboard payload, classification flow, Gmail connect/callback, prompt endpoints, upload endpoints, raw email/reply endpoints, and ground-truth endpoint.

`config.py`

Loads `.env`, local config, and app settings. Resolves the app version from the latest Git tag, with `APP_VERSION` environment variable as an override.

`run.py`

Simple local app entrypoint.

`templates/index.html`

Main dashboard template.

`static/js/app.js`

Frontend behavior: rendering state, category selection, charts, prompt version UI, classification actions, Gmail/upload mode actions, raw email retrieval, response drafting, ground-truth UI, and status bar updates.

`static/css/styles.css`

Base CSS.

`static/css/responsive-fixes.css`

Main visual overrides and newer UI refinements.

`agents/`

Contains local "agent" classes:

- `AIEmailClassifierAgent`
- `MockEmailClassifierAgent`
- `EmailFetchAgent`
- `EmailPreprocessAgent`
- `PromptManagerAgent`
- `GroundTruthTestAgent`
- `DailyBriefAgent`
- `EmailResponseAgent`
- `SummaryAgent`
- `ChartAgent`
- `AuditLogAgent`
- `CategoryRegroupAgent`

`services/gmail_service.py`

Handles Gmail OAuth, token refresh, Gmail fetch, raw message hydration, and Gmail sending.

`services/openai_service.py`

Handles OpenAI classification, daily brief generation, and response drafting.

`data/synthetic_emails.json`

Tracked synthetic demo fixture. Prediction fields should remain blank in the raw fixture. Expected fields provide ground truth.

`data/prompt_versions.json`

Tracked prompt version history.

`data/client_secret_sample.json`

Safe sample shape for Google OAuth client secret. Real secrets must never be committed.

`tests/`

Pytest coverage for agents and app endpoints.

## Files That Must Not Be Shared Or Committed

Do not share or commit these files:

- `.env`
- `data/client_secret.json`
- `data/token.json`
- `data/config.json`
- `data/classification_state.json`
- `data/audit_log.json`
- `data/response_drafts.json`
- `data/prompt_migration_decision.json`
- `data/prompt_selection.json`
- Any real Gmail message export containing private content

The repo `.gitignore` is configured to exclude local runtime and secret files.

## How To Rebuild Locally

### 1. Clone The Repo

```bash
git clone https://github.com/duchaba/codex-email-classification.git
cd codex-email-classification
```

### 2. Create A Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run The App

```bash
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

At startup, the app loads raw synthetic data but does not automatically classify. Click **Classify emails** or **Run selected version** when ready.

## Optional OpenAI Setup

To use AI classification instead of mock rules, create a local `.env` file:

```bash
cp .env.example .env
```

Add:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Do not commit `.env`.

Without an OpenAI key, the app uses mock rules.

## Optional Gmail Setup

To connect Gmail:

1. Create a Google Cloud project.
2. Enable the Gmail API.
3. Configure OAuth consent screen.
4. Create an OAuth client of type **Desktop app**.
5. Download the OAuth JSON.
6. Save it locally as:

```text
data/client_secret.json
```

Use `data/client_secret_sample.json` only as a shape/example.

When the app connects to Gmail, it creates:

```text
data/token.json
```

Do not commit `client_secret.json` or `token.json`.

## Gmail OAuth Issues We Solved

During development, two common local OAuth problems were fixed:

`insecure_transport`

The OAuth library blocks local `http://127.0.0.1` callbacks unless local insecure transport is explicitly allowed. The app now allows this only for localhost-style redirects.

`Missing code verifier`

Google OAuth can use PKCE. The app now saves the generated code verifier during connect and passes it back during callback.

## Gmail Retrieval Design

The app originally fetched full Gmail bodies for all messages before classification, which was slow.

The current design:

1. Fetch Gmail metadata and snippets quickly.
2. Filter to the current local calendar day.
3. Classify using snippets/previews.
4. Fetch full raw body only if the user clicks raw email or asks for a draft response.

This makes live Gmail substantially faster and reduces unnecessary sensitive data handling.

## Classification Prompt Policy

The current prompt policy is intentionally strict:

- Work is only for GenAI Incubator or ELVTR-related email.
- Support-style generic email should not become urgent.
- Marketing urgency should not become Urgent Priority.
- Social/newsletter/promotion/event/release emails should usually be Social Media.
- Suspicious/fake-urgent messages should be Spam.

The exact prompt history lives in:

```text
data/prompt_versions.json
```

## How Releases Work

Git tags and GitHub Releases are different.

The project uses tags:

- `v0.10`
- `v0.20`
- `v0.30`
- `v0.40`
- `v0.50`
- `v0.60`
- `v0.70`

The app About box reads the latest local Git tag automatically. If the latest local tag is `v0.70`, the About box shows `v0.70`.

GitHub Releases must be created separately from tags. A Git tag alone does not create a GitHub Release page.

## Release History

`v0.10`

Base functionality complete.

`v0.20`

Major UI redesign with illustrated style and About box.

`v0.30`

Separated mock and AI classifier agents. Added prompt version file tracking.

`v0.40`

Added AI daily brief improvements, raw email retrieval, and editable AI response drafts.

`v0.50`

Fixed Gmail OAuth local callback and PKCE verifier issues.

`v0.60`

Improved Gmail retrieval, status UX, AI classification resilience, and prompt history.

`v0.70`

Added prompt version preview/active behavior, run-selected-version support, migration safeguards, local prompt state ignores, and automatic About versioning from Git tags.

## Testing

Run all tests:

```bash
pytest
```

Run JavaScript syntax check:

```bash
node --check static/js/app.js
```

At the time of this handoff:

- Python tests pass.
- JavaScript syntax check passes.

## Suggested Next Improvements

1. Add streaming progress or polling for Gmail/classification instead of an indeterminate status bar.
2. Add a release automation script that creates both Git tag and GitHub Release in one command.
3. Add a safer prompt-diff view so users can compare prompt versions before selecting or saving.
4. Add Gmail fetch diagnostics showing messages returned, messages kept, and messages filtered out.
5. Add support for user-configurable work domains instead of hardcoding GenAI Incubator and ELVTR in the prompt.
6. Add more realistic evaluation datasets for urgent vs non-urgent classification.
7. Add screenshot-based UI regression tests if the UI continues to evolve.

## Important Security Notes

This is a local single-user app, not a hardened production SaaS app.

Keep secrets local:

- OpenAI API key belongs in `.env` or local config only.
- Google OAuth client secret belongs in `data/client_secret.json` only.
- Gmail token belongs in `data/token.json` only.

Do not upload private Gmail data to GitHub.

Do not commit local state files.

Do not share `.env`, OAuth files, Gmail tokens, or real email exports.

## Final Mental Model

Think of the app as a small local email command center:

1. Load raw emails.
2. Choose the classification engine.
3. Choose the prompt version.
4. Run classification.
5. Review categories, summaries, charts, and urgent items.
6. Test against ground truth when using synthetic data.
7. Retrieve raw email or draft replies only when needed.

The app is intentionally transparent: prompt versions, sources, active prompt state, mock-vs-AI mode, and evaluation results are all visible to the user.
