# Deploying the Coach Dashboard (free hosted link)

Coaches just click a URL — they need **no** account, no GitHub, no install.
You (once) need a free GitHub account and a free Streamlit account.

## One-time: put the code on GitHub
1. Make a free account at https://github.com (if you don't have one).
2. Create a new **empty** repository (e.g. `d3-ohio-xc`), Private is fine.
3. From this folder, push it up (the 6 MB database ships; the 564 MB scrape
   cache is excluded by .gitignore):
   ```
   cd /home/john/d3-ohio-xc
   git add -A
   git commit -m "Coach dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/d3-ohio-xc.git
   git push -u origin main
   ```

## Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in **with your GitHub account**.
2. Click **Create app → Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `<your-username>/d3-ohio-xc`
   - **Branch:** `main`
   - **Main file path:** `src/d3xc/dashboard/app.py`
   - **Advanced settings → Python version:** 3.12
4. Click **Deploy**. First build takes a few minutes; then you get a URL like
   `https://<something>.streamlit.app`.

## Lock it down (recommended)
The app has a built-in optional password. To turn it on:
1. In the app's page on Streamlit Cloud: **⋮ → Settings → Secrets**.
2. Paste:
   ```
   app_password = "PickSomethingSimple"
   ```
   Save. The app reloads and now asks for that password.
3. Share the URL **and** the password with your coaches.

(Alternatively, make the app **Private** in Settings → Sharing and invite
`shellhouse1@kenyon.edu` by email — then no password is needed.)

## Sending it to a coach
> "Here's the live dashboard: <URL>  (password: <password>).
>  Open it in any browser — start on Coach Mode, pick your program, and slide
>  the recruiting/training controls. No install needed."

## Updating it later
Any time you change the code or rebuild the database, just:
```
git add -A && git commit -m "update" && git push
```
Streamlit Cloud redeploys automatically within a minute.

## Notes
- Free tier **sleeps when idle**; the first visitor waits ~30s while it wakes.
- To refresh the data, rebuild `data/d3xc.db` locally, then commit & push it.
