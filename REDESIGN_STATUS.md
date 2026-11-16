# Stock Planning redesign release status

The mint-and-white redesign and both production UI bundles are included in this separate private repository. The original Stock-Planning repository and its database were not modified.

Verified on 16 November 2026:
- Frontend and administration production builds completed.
- TypeScript check passed.
- Overview tests passed for section/tools permissions, blank and non-finite stock, coverage, filters, purchasing counts and sales dates.
- Self-contained compiled startup and Home/navigation startup checks passed. TypeScript, Overview and Home/navigation checks were repeated successfully before release preparation.

Still unverified:
- The full frontend regression suite was interrupted when the Windows environment disconnected and produced no final report.
- Desktop/mobile visual inspection could not be completed because desktop/browser automation timed out.
- Streamlit deployment cannot be confirmed: access to the deployment dashboard was unavailable. Merging source does not by itself prove the app is live.

See STREAMLIT_DEPLOYMENT.md for the correct redesign repository and settings. The existing restore/initial-repository-2026-11-16 branch retains the initial repository state.

## Mint tabs and graph tables update
All tabs now share mint headers, panels, controls and table styling. Saved worksheet views include filtered record-count cards and segment charts. Stock/status/coverage, sales-month, worksheet segment and Insights values open their matching permitted records; chart values support keyboard activation.

Validation: TypeScript and production build passed. Compiled graph-table and Home/navigation startup tests passed. Overview permissions/missing stock, graph label clicks and sorted/windowed evidence identity, account navigation, section navigation, segment selection, production navigation and sales date parsing checks passed. Browser visual review stopped because the automation layer could not verify the current Windows browser URL; visual/mobile review remains unverified.

Code restore point before this update: restore/pre-tab-graphs-2026-11-16-072c6a2. No database restore is needed for this UI-only update.
