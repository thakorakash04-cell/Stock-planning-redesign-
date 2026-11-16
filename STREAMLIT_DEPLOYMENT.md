# Deploy the separate Stock Planning redesign

Use this guide for this redesign repository; older inherited deployment notes elsewhere may name the original application.

1. Open https://share.streamlit.io and create or select the separate redesign app.
2. Repository: thakorakash04-cell/Stock-planning-redesign-
3. Branch: main
4. Main file path: app.py
5. Advanced settings: Python 3.12.
6. In Streamlit Secrets, reuse the existing Stock Planning app's DATABASE_URL, ADMIN_USERNAME and ADMIN_PASSWORD, plus optional integration settings that the existing app uses. Copy them directly within Streamlit; never commit real values to GitHub or paste them into chat.
7. Deploy and verify the Overview, an existing viewer login, current workbook, section/segment access and navigation. Reusing the same database preserves current accounts, permissions and uploads; no workbook re-upload or user recreation should be necessary. These deployments will share database writes.

If a separate Streamlit app already watches this repository's main branch, the source merge can trigger its update; confirm the running UI and logs in Streamlit rather than assuming deployment succeeded. The original app should continue to use its original repository.

Both built interfaces are committed in frontend_dist and admin_dist. Streamlit starts app.py; it does not need to run npm during deployment. The app intentionally shows setup instructions until real secrets are configured.
