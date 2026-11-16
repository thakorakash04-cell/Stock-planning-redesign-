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
