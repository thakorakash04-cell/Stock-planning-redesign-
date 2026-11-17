
### Persistent upcoming-plan material availability
After Check material availability succeeds, the availability/shortage result and its calculation details are stored durably for that plan and permission scope. All later logins and process restarts reuse the result. Initial production rows include only a compact saved status and checked time; full component/quantity details are loaded only on opening the check and reuse the fingerprint-validated server cache. The workspace bootstrap cache includes a compact availability revision so same-day browser-session restoration also shows newly saved checks. No added polling or automatic recalculation is used.
Every master upload invalidates checks by BOTH content version and upload timestamp, even if the uploaded contents are identical. A material or quantity change also invalidates the result. Date, description and other non-calculation edits retain it, with the current plan revision. Deleted/started plans do not display saved checks. Failed checks are not stored as successful results. Existing Production and segment permissions are checked before summaries/details; permission scopes have separate cache entries. The saved result describes the uploaded stock snapshot and does not reserve stock or combine demand across plans. Availability arithmetic and current-stock/QI/on-order rules are unchanged.


Structured notification emails: subsequent Product Status and Stock & Planning notifications use HTML headings, summary bullets and escaped source-owned detail tables, plus a readable plain-text alternative. Existing Gemini settings optionally rewrite compact authorized rule-summary facts only; recipient email addresses, product/material records, owner names and full workbook/document data are not sent for email composition. AI cannot select recipients, change schedules, calculate or replace table values. Invalid output, unsupported numbers, missing keys and provider failures fall back to deterministic bullets and the same tables. At most one bounded AI request is made per claimed recipient report, with successful identical summaries reused in a bounded process cache. Formatting performs no additional database reads or workbook downloads. Tables show at most 50 rows/12 columns and explicitly label omitted details. Existing duplicate protection and access revalidation apply. This release changes future message presentation, not policy activation or delivery history; no old messages are resent for formatting.


### Stock upload and first-visit notification rules
Manage users → Email management → Stock & Planning · Automatic reports contains eight policies. New policies default to **preview only**. Save matching settings while paused, preview recipient reports, then explicitly enable real delivery. Existing SMTP/Resend secrets are reused; deployment sends no test email.

| Rule | Source and timing |
| --- | --- |
| 1. Packaging stock below 3,000 | Once per distinct master version. BOM components classified by editable description terms, packaging material types, or included codes; exclusions take precedence. Current stock is Unrestricted plus In Quality Inspection, in each material's workbook unit. |
| 2. New production entries | Compare the saved Excel Completed view and the shared Under QC / Ongoing calculations against the preceding captured upload. Quantity changes alone do not add a new production identity. |
| 3. New sales entries | Compare each Primary / Secondary upload independently. Primary entries must match BOM FG/parent codes, exactly as the Sales view. Canonical row fingerprints ignore row/column order and preserve duplicate occurrence counts. Corrections to an existing sales row appear as a replacement row addition. |
| 4. Ongoing batches due or overdue | Once per IST day on the first authenticated visit; Expected End Date on or before today, including saved planning overrides. |
| 5. New upcoming plans | Daily first visit; immutable plan creation events before today's IST midnight, with missed days caught up. |
| 6. Forecast purchasing above zero | Once per master version, Need to Order Quantity > 0. Include source purchasing columns and linked FG forecast totals, transfer quantity, current stock and pending quantity. |
| 7. QC pending at least 14 days | Once per master version. Use the production worksheet reference date (upload date fallback), latest 101 date, and existing no-321 QC logic; include matching material/batch movement history (first 50, with total count). |
| 8. Production plan modifications | Daily first visit; ongoing expected-date/quantity edits and upcoming plan changes before today's IST midnight, including author and before/after details. |

Changes made during a day are included in the next daily report; ongoing due reminders use the current compact saved list on the first visit. Date checks continue daily until an order leaves Ongoing or its expected date moves into the future. Upload batches can send later the same day independently of the already completed daily batch. All matching policies for a recipient combine into one email **per upload or daily batch**. Multiple distinct uploads may therefore produce multiple emails that day. Empty matches do not send.

Only active registered accounts with a saved email, relevant section access and matching segment access are recipients. Shared packaging stock is a material-level quantity; shared aggregate forecast purchasing rows require rights to **every** contributing segment, matching the existing worksheet access boundary. Unmapped rows are available only to all-segment users/admins. Permission fingerprints are checked again before transport, including truncated report counts. No grants are changed. Previews are admin-only and consume no upload/day delivery marker.

Hooks commit compact notification records atomically with uploads or plan edits. Existing saved master/sales data is used once to seed comparison fingerprints when possible; a first-ever source establishes its baseline without emailing its entire production/sales history. Only the previous source's identity counts are retained for comparisons, not a second workbook. Deterministic master compression avoids a false version change from gzip timestamps. Production preparation reuses the shared source snapshot cache.

Daily built-in checks read compact due/event records and durable batch markers, never the master or sales workbook payload. PostgreSQL excludes processed upload batches before returning event payloads; no recurring built-in notification timer or external scheduler is used. Claims survive restart and parallel logins. Failed/ambiguous SMTP submissions are marked uncertain and never blindly resent; queued work can resume on a later authenticated visit. Reports show up to 50 records per policy, with matching counts; open the authorized tables for the full list. Sender configuration must be ready before a day is consumed.

Existing custom worksheet rules and their legacy schedule remain available while Automatic reports is paused, only on authenticated active sessions. Once enabled, saved enabled custom worksheet rules join the first-visit daily report (their clock time is ignored), rather than sending a second scheduled message. This compatibility path needs one version-cached master read per cold process/day if custom rules are enabled; the eight built-in rules do not. Existing explicit custom-rule manual delivery remains a separate administrator action. Database transfer savings have been verified at the query-path level; exact monthly egress still depends on upload size, matches, recipients and cold starts.

# Stock & Planning — Streamlit

## Separate UI redesign

### Mint section layouts and graph records
All workspace tabs share the Overview mint headings, rounded panels, controls and table treatment. Saved worksheet tabs also show current-filter record counts and segment-count charts. These are record counts, not summed stock/cost quantities. Shared materials appear in each linked segment. Production subviews retain their existing shared-plan controls.

Graph values are visible and interactive. Stock bars open the exact segment/status rows with the active Overview search and segment filters; the coverage percentage opens its numeric-stock denominator records. Sales points/month values open the saved transactions for that source and month. Worksheet graph values open matching filtered rows. Insights value labels retain the original evidence index after date sorting and windowing and use the existing source-record drill-through. Chart tables retain existing column/filter/grouping and download permissions. Enter/Space activate graph values and Escape closes the table. Overview/worksheet/sales chart tables use already permitted snapshots without additional source queries.


This private redesign preserves the existing Streamlit backend, calculations and account controls. The default Overview adds the mint-and-white dashboard, saved stock line counts, segment/search filters, stock coverage, saved sales activity and links to existing workspaces. Missing/non-finite stock values are excluded from coverage; stock quantities across different units are never added. Shared materials appear in each linked segment. Overview data uses the existing authorized payload and saved sales snapshots without additional polling. Insights shortcuts require both section access and tools permission.

The original production app and its database remain separate. To connect the redesign later, configure its Streamlit secrets explicitly; no credentials or uploaded workbooks belong in this repository. Build the Streamlit component with `npm run build` from `frontend`, and run `npm run check`, `npm test`, `npm run test:startup` and `node tests/overview.cjs` before deployment.

A Streamlit Cloud version of the Stock & Planning workspace, with username/password sign-in, one configured administrator, and administrator-created viewer accounts.

## Deploy on Streamlit Community Cloud

1. Open https://share.streamlit.io and create an app from `thakorakash04-cell/Stock-Planning`.
2. Select branch `main`, entry point **`app.py`**, and **Python 3.12** in Advanced settings.
3. Create a persistent PostgreSQL database (for example, Supabase or Neon). For Community Cloud, use a provider connection/pooler reachable over IPv4. Copy the PostgreSQL connection string, with SSL enabled.
4. In Advanced settings → Secrets, paste the three settings from `secrets.example.toml` and replace **every placeholder**. Use your own admin username (for example `thakorakash04-cell`) and a unique password of at least 12 characters. Do not commit the actual secrets to GitHub.
5. Deploy. Sign in with the admin username/password you configured.
6. Use **Update workbook** at the top right of the dashboard and select your refreshed `Master File.xlsx`.
7. Open **Manage users** in the dashboard sidebar to create viewer usernames and passwords. Share those credentials privately, along with the Streamlit URL.

No default password, company workbook, extracted model, or existing user credentials are included in this public repository. Your workbook is uploaded inside the protected app and stored in your PostgreSQL database. The app does not write uploads back to GitHub.

### Required Cloud Secrets

```toml
ADMIN_USERNAME = "thakorakash04-cell"
ADMIN_PASSWORD = "REPLACE_WITH_YOUR_OWN_RANDOM_PASSWORD_AT_LEAST_12_CHARACTERS"
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"
```

The app intentionally shows a setup screen until real settings are provided. There is no first-visitor registration or hard-coded admin password. Changing `ADMIN_PASSWORD` in Secrets and restarting the app rotates the admin password and revokes previous admin sessions. Changing `ADMIN_USERNAME` disables the previous admin account.

The database user needs permission to create tables and read/write them. `accounts` and `datasets` are created automatically. Use a database/user dedicated to this app. Preserve your database and its backups when redeploying; deleting it removes accounts and uploaded data.

## Permissions

| Capability | Admin | Viewer |
|---|---:|---:|
| Sign in and view the shared dataset | Yes | Yes |
| Search, filter, hide/unhide columns, show sums, full screen | Yes | Yes |
| Open underlying model tables | Yes | Yes |
| Upload or replace the shared workbook | Yes | No |
| Create, disable, enable, reset viewer accounts | Yes | No |
| Export visible/filtered data through original table controls | Yes | No |

User creation, password resets, account changes, data reads and data writes are authorized server-side. Passwords are stored as salted PBKDF2-SHA256 hashes with 600,000 iterations. Five failed attempts lock an account for 15 minutes. Every server action and the 60-second heartbeat recheck account access. Browser sessions last until midnight Asia/Kolkata and restore after a page refresh without re-entering the password. Disabling or resetting a viewer revokes their existing sessions.

Streamlit's `client.disableDataExport = true` removes built-in CSV export and clipboard copying for read-only dataframes. Static serving is disabled; viewer accounts receive no download controls or raw-file links. The original table export controls are available only to administrators. This controls application export features; authorized users can still photograph/screenshoot the screen or capture data their browser receives. No website can make visible data impossible to copy. Do not give viewers GitHub/Streamlit/database owner credentials.

## Workbook views

The original worksheet layout is expected:

| App view | Workbook source |
|---|---|
| Stock overview | `Summary` |
| BOM cost | `BOM Cost` |
| Sales & transfers | `Sales Data` |
| Production | `Production Data` |
| Forecast planning | `Forecast Planning` |
| Forecast purchasing | `Forecast Need to Order List` |
| Order requirements | `Need to Order Sheet-B.O. PS` |

- Forecast opens with product totals. **Pending = sum of forecast − sum of transfers − current stock once per material.** Monthly details remain available; filtered stock/pending totals use the same rule.
- Purchasing views preserve the named worksheets' saved values, including blank cells, negative balances and the unmatched-component row.
- Segment options come from **Source.Name** in the material/BOM tables. Shared components inherit their parent products' segments; no marketing `Segment` fallback is used. The supplied workbook's five categories are General Wound Care, Advance Wound Care, Ostomy Care, Energy Devices and Designer Cap.
- Select a cell to open a full-width record page. All related embedded tables, columns, components, parent products, batches and periods are available. **Entire workbook** removes the material restriction.
- The original ChatGPT Sites React interface is used directly inside Streamlit: the same seven-item sidebar, light-gray workspace, table headers, per-column filter controls, Columns and Totals menus, grouping, and full-window record screens. Use the table's **Full screen** button at the upper right. Column/total preferences remain per table in the browser.
- The four KPI cards are omitted.

## Excel refresh and embedded models

Refresh All and save in Excel before uploading. The server reads saved worksheet cells with `openpyxl` and extracts embedded Power Pivot tables using `pbixray`. Direct `.xlsx` uploads include the embedded model automatically; the older `.stock.zip` package format is also supported. No Power Query, SAP connection, or DAX refresh runs on the server. Related source records are provided as calculation context, not a new DAX engine.

Uploads are limited to 25 MB, with expanded archive/table bounds. Workbooks with missing required sheets are rejected. A parsing/validation failure leaves the previous shared dataset in place. A workbook without an embedded model can supply summary views, but will have no underlying-model tables.

## Local development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `secrets.example.toml` to `.streamlit/secrets.toml` and provide your own admin credentials. For local testing only, use:

```toml
DATABASE_URL = "sqlite:///stock_planning.db"
```

Then:

```bash
streamlit run app.py
python -m unittest discover -s tests -v
```

Local SQLite is **not durable on Streamlit Cloud**. Cloud deployments should use PostgreSQL. The app displays a warning if SQLite is selected. The checked-in `.streamlit/config.toml` is required; the app fails closed if data export is not disabled.

## Validation

Automated checks cover password authentication/lockout, admin/viewer write restrictions, disabled-session revocation, persistent saved data, workbook extraction and forecast aggregation, Source.Name segment filtering, Streamlit login/role UI rendering, and server-side authorization of component requests. PostgreSQL behavior requires a real deployment connection; local automated storage tests use SQLite with the same schema/authorization layer.


## Frontend source and build

`frontend/src/` contains the original Sites dashboard components, with a small Streamlit message bridge replacing the Sites endpoints. `frontend_dist/` contains the built static component. **Streamlit Cloud does not need Node or an extra build step.** No workbook records or secrets are built into these assets.

For frontend development with Node 22+:

```bash
cd frontend
npm install
npm run check
npm run build
```

Commit both frontend source and the updated `frontend_dist` build. Keep existing Streamlit Secrets and the PostgreSQL database unchanged when updating the UI. Login and account checks remain in Python. Client-side filtering stays responsive; a periodic server heartbeat checks access and refreshes changed datasets.

## Account access controls

See [ACCOUNT_ACCESS.md](ACCOUNT_ACCESS.md) for administrator permissions, persistent access logs and self-service password changes. These controls extend the original viewer-only defaults described above.


## One Zoho Cliq bot for all four apps

See [zoho_bot/README.md](zoho_bot/README.md) for the standalone unified backend, Docker deployment, Zoho Message Handler and account mappings. Streamlit does not need to stay awake for the separately hosted backend to answer.

## Ask AI

See [ASK_AI.md](ASK_AI.md) for the Gemini Secrets setup, data sharing, query evidence and permissions.

## FG planning inside Order requirements

Select an FG material, enter its planning quantity in the displayed unit, and
choose **Add FG**. Add more FG items or edit the quantity rows, then choose
**Calculate need to order**. Results contain only components linked to positive
entered quantities. Editing any quantity clears the previous result until it is
recalculated. Reloading materials or replacing the workbook clears the plan.
Plans are session calculations and do not replace the shared workbook.

The calculation reproduces the master's Power Query `BOM` → `Need to Order
Sheet` logic: multiply each entered FG quantity by `Component quantity`, convert
each BOM-row requirement to Int64 with round-to-even, group by `Component`,
`Component(text)` and `Material Type`, sum requirements, and deduct the minimum
merged available stock and minimum merged on-order stock once per group. The
final need-to-order quantity is converted to Int64. Nulls and negative balances
are preserved. There is no extra division by BOM base quantity, FG-stock
subtraction, or recursive BOM explosion in this PS calculation.

Planning needs an uploaded embedded `BOM` table with the existing merged stock
and on-order columns. An upload containing only saved worksheet summaries cannot
support recalculation. All planning requests recheck account access, and a stale
workbook version must be reloaded before calculation. No Gemini key is needed.

### Viewer downloads from a clicked value

Viewers can download the filtered matched-records table opened by clicking a
worksheet value. The Excel file contains only the displayed columns and matching
rows from that one source table. The server validates the selected worksheet row,
workbook revision, source table, columns and every exported row against the
related material context. This does not grant the broad `download` permission:
main worksheet tables, Entire workbook, ZIP exports and Ask AI exports retain
their existing access rules. Downloads are recorded in the administrator log.

Viewers can also download the **Forecast purchasing** table and the calculated
**Order requirements** material list as Excel, using the current grid filters
and visible columns. These are scoped exceptions; other table export permissions
are unchanged. Planning downloads are checked against the result calculated for
that login session and workbook version, and both downloads are audited.

FG planning inputs, unfinished entries and calculated results stay in memory
when navigating to another worksheet, Ask AI or Insights and returning during
the same login. Signing out, loading a newer workbook, choosing Clear plan or
reloading planning materials starts a new plan. Browser reloads start a new
in-memory view.

## Production workspace

Production provides four separately selectable views: the existing
completed/QC-released worksheet, ongoing orders, batches under QC release, and
shared upcoming production plans.

* **Under QC release:** match material **and batch**, restrict to FG/SFG types,
  require movement 101 and no 321 through the snapshot date, then use the latest
  101 posting date. The window includes the reference month and four preceding
  calendar months. Quantities come from matching production order records;
  unmatched quantities stay blank.
* **Ongoing:** confirmed quantity must equal zero; Basic start date must lie in
  the reference month or preceding month, no later than the snapshot date.
  Expected end date starts from Basic finish date. Expected FG uses median
  positive 321 receiving quantity / order quantity from up to ten completed,
  QC-released batches of the exact same material (same product size). Order
  quantities within ±25% are prioritised; otherwise all sizes for that material
  are used and labelled. SAP's negative 321 QC outflow is excluded to avoid
  cancelling the corresponding positive unrestricted-stock inflow. If no usable
  history exists, no quantity is invented. Estimates remain planning assumptions.
* **Reference date:** the dated header in the first five rows of Production Data
  is captured on workbook upload. Earlier uploads fall back to their upload date
  and show that fallback explicitly. Re-upload the refreshed workbook once to
  capture its worksheet date.
* **Shared changes:** expected FG quantity/end date overrides and upcoming plans
  are stored in `production_shared` in the same persistent database. Viewers
  start with edit access off. Manage users provides separate **Edit ongoing
  production** and **Add/edit upcoming plans** rights. Saves recheck permissions
  and dataset version, detect concurrent edits, and appear in the access log.
  Other users see updates on refresh or the production screen's 60-second poll.
* **Sidebar:** Manage users also controls each viewer's nine section permissions.
  Restricted menus are hidden, their worksheet rows are removed from the UI
  payload, and their view/tool/edit/export requests are denied server-side.
  These control section access; underlying records may still be available in an
  authorised section's drill-down or Ask AI context. Permission changes revoke
  existing sessions, so the viewer signs in again for the new rights.

The three new Production tables each have their own grouping selector and segment
filter. Material-backed rows use the workbook's Source.Name segment mapping.
Upcoming plans infer a segment from an exact material code/product-name match,
or an authorised editor can choose a workbook segment explicitly; unresolved
plans can be found under Unassigned. Batches beginning with a numeric character
are excluded from these three views (existing history remains stored). New
upcoming plans must use a batch that does not start with a digit. All table
pagination layouts keep Previous/Next beside the record count.

### Upcoming material selector and availability

Upcoming plans now offer a searchable FG/SFG catalogue. Selecting a material
loads its code and canonical description; legacy plans can be edited to select
their material. All three new production tables open the existing full-window
source-record drill-down when a value is clicked. Their matched-record downloads
validate the production selection server-side.

Each saved upcoming plan has a Material availability control. Green means every
BOM component is verified as sufficient; red opens shortages or explains why
availability cannot be verified. Required consumption is calculated as planned
FG/SFG quantity / BOM base quantity * component quantity, without premature
integer rounding. Duplicate joined BOM items are removed; distinct consuming
items are summed per component/unit and stock is deducted once. Current stock
includes unrestricted and quality-inspection stock; on-order receipts do not
count. The detail window shows shortages and every BOM calculation, including
base quantity and consumption. Missing/ambiguous BOMs, invalid quantities,
unknown stock and mismatched units never produce a green result. The check uses
one plan against the uploaded snapshot; it does not reserve stock across plans
or recursively explode SFG subassemblies. Plan revision, workbook version and
Production access are checked again before the result is returned.

Production save and availability requests use a separate `plan_id`; the RPC
request `id` is reserved for request/response correlation. New plan IDs are
created by the server. This prevents Invalid plan ID errors and edit/check
requests waiting for a response under the wrong ID.

Upcoming plans are automatically archived when both their resolved material code
and batch match Production Order Details. Matching ignores surrounding spaces
and letter case, never matches on material or batch alone, retains the saved
history/audit trail, and keeps archived plans out of future upcoming lists even
when a later SAP dump omits older orders.

### Shared edits, deletion and IST history

Upcoming plans offer Edit and Delete actions to administrators and viewers with
`edit_upcoming` access. Delete requires confirmation and soft-deletes the shared
plan so it disappears for everyone; it retains the record and history. Delete
rechecks the workbook version, plan revision and permissions to prevent deleting
someone else's intervening edit.

The Edit history tab is readable by users with Production section access. It
shows the latest 500 history events, with username, action, material/batch,
changed field, previous/new values and an IST timestamp. Creating/editing/deleting
plans and automatic production-order matches write history in the same database
transaction as the change. Detailed history starts with this deployment; earlier
before/after values cannot be recovered. Internal timestamps remain absolute
instants; production saved times, history, account logs, upload times and Insights
generation times are explicitly displayed in Asia/Kolkata (IST), independent of
the viewer's browser/server timezone. Date-only planning dates are unchanged.

## Private saved filters and column views

View settings are now saved in `user_view_preferences` under the authenticated
username and a distinct section/table scope. Column filters, visible columns,
totals and sorting survive logouts, future logins and use on another browser.
Sidebar searches, segment selections, grouping and forecast mode are stored per
section; the new production tables keep separate segment/grouping settings.
Drill-down tables also have distinct scopes for each originating section and
source table. Older unowned browser-local settings are not imported into another
user's account.

Changes save automatically after a short debounce, and pending changes flush
before queued navigation/logout requests. Users can clear column filters or use
Reset table view to reset that table's saved view. Saving never changes another
user's preferences or shared workbook data. Preferences survive workbook updates;
only fields available in the current table are applied.

The three new Production tables load by default when Production opens. A new
uploaded workbook automatically reloads their source data, clears stale
availability/detail windows and ignores older in-flight responses. The saved
filters and column views remain intact. Under-QC and ongoing-order source rows,
material catalogues and segment mappings are prepared once per master upload,
stored durably, and reused from server memory across logins. Process restarts
reload the stored snapshot instead of recalculating it. Existing uploads are
prepared lazily on first access. Saved planning edits and upcoming plans remain
live overlays; refreshing shared plans does not rebuild the source snapshot.

Order Requirements receives its master-version FG/SFG material summary and
BOM-planning options in the initial authenticated workspace response. Both are
prepared once per master upload, cached across logins, and stored for recovery
after server restarts. A new master replaces the snapshot; manual quantity
calculations still run only when requested. Materials without BOM records stay
visible in the summary but are not offered for BOM calculations.

### Lead time & Consumption
The sidebar reproduces the Days Calculation intervals from the supplied reference workbook using the active master model's BOM, Material Document List and Order List. Each material/batch uses its earliest movement date: inward=min(101,102,105,106), QC=321, use=min(261,262). Days are calendar differences; inward-to-use is not final FG release. PO joins include material, avoiding unrelated batches and PO items. Missing or ambiguous dates remain blank. Segment, material type, PO year, inward year, grouping and column views are private saved user settings. Admin controls section access through menu_9 independently of Gemini tools.

Forecast Purchasing recalculates component quantities from outstanding forecast demand and adds **Suggested order by date** for positive need-to-order rows only. This is a timing estimate: outstanding dated FG demand deducts transfers and FG stock once, then standard-BOM component quantity / base quantity × outstanding FG quantity determines monthly requirements, recursively expanding SFG components, as requested. No flattened BOM without SFG is required; purchasing totals use this same demand. Current FG stock (including QC stock), transfers and ongoing FG/SFG production available by its expected end date cover forecast demand before BOM expansion. Saved ongoing quantity/end-date overrides are respected. Under-QC orders are already covered by current planning stock (Unrestricted + In Quality Insp.); their material/batch pairs are excluded from ongoing supply to prevent duplicate counting. SFG stock and dated production cover SFG demand before expanding its components. Component stock and on-order are deducted once; the first uncovered date is the requirement date. Subtract only ceil(mean procurement PO-to-inward days). QC release and inward-to-consumption durations are never used, and missing QC/use history cannot block a suggested date. Backlog requirements are dated at the workbook reference date. Ongoing orders without yield history use SAP order quantity; orders without an expected end date are not assumed available. Historical means use non-negative material/batch observations, excluding repeated BOM/PO joins. All on-order is assumed available; scheduled PO delivery dates and working-day calendars are unavailable. Past suggested dates mean overdue. Cyclic or ambiguous alternative BOMs are marked for review. Missing histories or dated BOM links are reported instead of invented dates. Data and dates refresh with the master workbook; filters do not change purchasing calculations. Existing viewer Forecast Purchasing export includes the suggested date. Mail remains unconfigured.

Forecast Purchasing, saved Order Requirements and calculated FG planning results include **Average Lead Time (Days)** for every material with usable history, independent of whether it needs ordering. This numeric calendar-day average uses PO generation to inward only (no QC/use allowance); missing history stays blank and zero-day receipts remain valid. Downloads include the column under the existing table export permissions. PS quantity calculations are unchanged.

Table views now save column order as well as filters, visibility, totals and sorting per user/table. In Columns, use left/right arrows to move columns; new source columns append automatically and Reset table view restores source order. Sort by offers a column and direction, with ascending/descending controls also inside each column filter. Cell drill-downs retain the original source-column mapping; exports follow the visible column order and filtered/sorted rows. Ask AI evidence and Insights source/result tables use these controls too (paginated evidence sorts/filters the loaded page). Ask AI evidence opens with a visible administrator-only Excel result download; its Result table sheet respects the displayed projection. The separate Download all matching records button retains the full query result and underlying matches. Server validation rejects rows or columns outside the saved AI query result, and prior administrator-only access is preserved.

### Planning assistant and deployed knowledge
Ask AI now includes read-only tools for exact PS requirements, one-plan physical material availability, shared production views, and forecast purchasing dates. Follow-ups receive the last validated scenario and up to20 recent conversation messages; the chat retains40 messages for the current session. It asks for clarification when material, quantity or PS-versus-availability basis is ambiguous. This is bounded conversation context, not guaranteed understanding of every conversation or permanent memory of unrelated chats. Clear chat clears the scenario too. Tools enforce section access, do not save plans and use server calculation functions; production inspection disables automatic archival for the chat request. Material availability is not proof of complete production feasibility.

At each question, knowledge is rebuilt from PLANNING_RULES.md, current README feature notes and an allowlist of deployed calculation modules. The catalogue includes public function documentation and current implementation excerpts for core calculations, never secrets or authentication files. A hash identifies the deployed knowledge revision. New GitHub changes become visible after deployment; this does not train Gemini, read unpublished/private branches, or automatically create tools for unknown future workflows. For new features, update PLANNING_RULES.md/README and register any new calculation tool in planning_assistant.py. Ordinary data querying remains available. The model can explain newly documented functionality; it cannot execute arbitrary repository code or writes. Generated answers still require judgment and may ask clarifying questions. Gemini requests require existing consent and GEMINI_API_KEY.

All shared result grids now use one **Calculations** dropdown for Sum, Average, Count numbers, Minimum and Maximum, with per-column selection and multiple footer rows if desired. Choices persist privately by user and table. Average ignores blank/non-numeric values, includes zero, and uses all filtered loaded rows across grid pages. Evidence that is server-paginated still calculates over the loaded page only. No mixed-unit or distinct-material inference is made. The original custom forecast sum calculation is preserved; averages are arithmetic row averages.

Ask AI responses render safe Markdown headings, bold text, bullets, numbered steps and comparison tables instead of literal formatting markers. Raw HTML is disabled. Evidence grids are collapsed and only mount after selecting View query table; response narrative tables remain visible. New answers align to their beginning inside the transcript, without bottom jumps on loading, exports or query expansion.

### Attention-focused Insights
Insights & Graphs now shares Ask AI's deployed knowledge, source revision and read-only planning tools. A Needs attention board highlights server-calculated purchasing/forecast exceptions, missing history and estimates, overdue expected production dates, under-QC batch age and upcoming material shortages. Derived ongoing, QC and upcoming production sections respect Production menu access; Lead time review respects its own menu right. Physical material checks reuse the availability function, cap analysis at50 upcoming plans, and do not reserve stock across plans. QC age is not labelled overdue without an SLA.

Attention queries are prioritised before general comparisons. Each graph can include a directly linked finding and next check; clicks retain validated source tables and administrator Excel exports, including derived production tables. The AI review receives the same planning rules/current implementation context as Ask AI and can write substantially more supported findings and actions than the previous short fixed review. Calculated attention checks remain visible if Gemini's narrative is unavailable. No cross-view shortage totals, arbitrary delay thresholds or unsupported feasibility claims are introduced. Reports are cached against workbook, deployed knowledge, production-plan revisions and user/permission scope; production changes during generation require retry. New GitHub changes are reflected after deployment, not through model training or undeployed repository polling.

### Add Insight graphs in plain language
After Run analysis, each report section has **Add graph to [view]**. Describe the measure, comparison and filters, then press Enter or Add graph with AI (Shift+Enter inserts a line). The generated graph is appended to that view with calculated evidence, an AI interpretation/next check where supported, source-table drill-down and existing administrator Excel exports. Gemini's request and explanation use the shared deployed planning knowledge. Only the selected view's allowlisted read-only query is accepted; ambiguous or unsupported requests produce a clarification. Repeated queries suggest changing the existing graph style instead. A narration failure keeps the validated graph.

Additions remain in the current session report across sidebar navigation. Regenerating analysis replaces the report, and browser/session restarts do not persist custom graph templates. Private server report IDs bind view membership, workbook, planning revision, deployed knowledge, user/permissions and graph limits (30 per view,100 per report). A changed snapshot or permission requires a new report. Prior descriptions/queries inform follow-ups only in that report view. No question text is written into access logs, and no planning records are edited.


### Shared portal controls
Existing usernames and passwords are retained. In Manage users, select any existing account (including admin) and save its unique email address. It can then sign in using either username or email. New viewers can have an email assigned during creation. Forgot password sends an 8-digit code to the registered email; codes expire in ten minutes, allow five guesses and revoke old sessions on success. Configure RESET_FROM_EMAIL plus SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD, or RESEND_API_KEY, in Streamlit Secrets. Never commit real credentials.

Workspace settings edits title, login/sidebar text, navigation labels/order and additional segment labels. Fixed section IDs preserve calculations and access rights. Segment labels need matching source data to contain records. Manage users retains server-enforced per-section and action permissions. Edit history records settings, email/profile and access changes and dataset uploads; existing production history remains available in Production.

Email management supports rule preview and explicit delivery against saved worksheet rows. Use the exact saved section/header name and >, <, = or contains. Multiple matching rules for one email are combined into one report; unchanged manual reports are suppressed for 24 hours. Scheduled reports use one durable delivery job per recipient and due slot. Credentials are configured per portal. Scheduled delivery is enabled by default at 09:00 IST. Change or pause it in Email management → Scheduled delivery. Regulatory searches must be saved using Save results snapshot before alert evaluation; planning uses the last uploaded workbook. No test email is sent during deployment.

Planning uploads include a compatibility/change summary before explicit replacement; parsing errors preserve the prior workbook. Regulatory snapshots retain a schema/row summary in history.

### Active-site scheduled email delivery
Daily delivery is enabled by default at 09:00 IST for saved, enabled email rules. The server checks every 60 seconds while the portal is open, only after authentication. When no Streamlit session is running, no process is kept awake. The first active check after a sleep sends one latest overdue report per recipient; missed days do not create a burst of historical emails. If the site wakes before today's daily time, yesterday's missed report can still be delivered. Reports use the latest saved workbook/results snapshot, rather than reconstructing historical data. Empty matches do not send a message. Configure sender credentials in Streamlit Secrets as before. No GitHub Actions secrets or external scheduler is needed.

Schedule slots, recipient jobs and delivery results are stored in the database. Multiple visitors and server restarts cannot re-claim the same job. Safe pre-submission failures retry while active; Resend uses a stable idempotency key within its retry window. A failed or interrupted SMTP submission that may have been accepted is marked uncertain and is not automatically retried. Review Scheduled delivery history and provider logs before manually resending an uncertain report. Only administrators can change schedules or read delivery history. A saved enabled rule is required; this update does not invent recipients or send test messages.

### Product Status administration layout and rule assistant
Manage users, Email management, Workbook management, Workspace settings and Edit history now share Product Status's dark teal sidebar, card/dialog styling and the same reusable table components. Filters, column order/visibility, grouping, totals, full-window tables and authorized exports use the copied Product Status table implementation. Existing account usernames/passwords are retained. Accounts have username/email details, section/action permissions and an administrator password-reset dialog. Account authorization stays on the server.

Email management includes a chat-style rule assistant using the existing grounded_ai Gemini settings (GEMINI_API_KEY / GOOGLE_API_KEY and existing model configuration). Requests and up to eight recent conversation messages, selected recipients, current draft rules and saved table/column names inform follow-up requests. No account passwords or sender secrets enter the prompt. Gemini can propose named trigger points and literal, allowlisted filters; it cannot execute SQL/code, enable a rule, save changes or send email. Drafts are always paused. Review the points, enable them and Save rules. The combined preview uses real server-calculated matches and Product Status tables. All points for one recipient form one report. Registered recipient section permissions and active status are rechecked before sending; uncertain SMTP outcomes are not automatically retried. Previously saved explicit external recipients are retained for compatibility; new destinations must be added through account emails.

Workbook management displays the saved source name/date/user, table and row counts, paginated source tables, and a schema/row comparison before replacement. A preview never replaces data. Confirmation expires after ten minutes and rejects a source version changed since preview. Stock & Planning retains its original Excel/model parser; Regulatory Framework accepts .xlsx/.csv report snapshots and does not replace its bundled FDA/CDSCO search databases. Workspace text, segment labels and up/down sidebar ordering use the same administration shell.

Rebuild administration assets from admin_frontend with npm install, npm run check, npm test and npm run build; commit admin_dist alongside source. Streamlit serves these built assets.


Manage users → Manage rights includes Segment access. Existing accounts default
to all segments, including future master segments. Administrators can assign a
viewer selected Source.Name segments (an empty selection grants no segment rows).
Changes revoke viewer sessions and are recorded in Edit history. Administrators
always retain all segments. Server-side filtering applies before data reaches
workspace tables, drill-downs, planning/production snapshots, exports and AI
context. Snapshots are isolated by segment scope. Shared-plan access and report
emails also respect assigned segments. Unmapped rows and mixed-segment worksheet
totals that cannot be separated are withheld from restricted viewers. Shared
component source records remain visible where an assigned segment's BOM needs
them. Replacing the shared master requires all-segment access.

Login appearance: both username and registered email sign-in use a fixed branded sidebar and adjacent white sign-in card, stacking on narrow screens. Administrators can change the portal logo, title, purpose text and sign-in copy under Workbook management → Login logo and text. PNG/JPEG/WebP uploads are limited to 250 KB and 2000 × 2000 pixels. Use default portal logo restores the portal-specific icon. Save login appearance persists the changes and records them in edit history. Only this public appearance is exposed before sign-in; accounts, workbook data and email rules stay private. Existing credentials and recovery remain unchanged.

Email management’s Gemini assistant supports conversational setup, follow-up threshold/recipient edits, explicit rule deletion and the shared daily delivery time in IST. It uses the uploaded workbook’s exact tables/columns and known recipients; it does not invent calculations or duplicate Product Status’s dossier policies. Setup questions do not require a recipient or workbook. Review the proposal, select Apply proposal to working draft, enable desired trigger points, then Save rules. This saves reviewed rules and the shared schedule together with version checks and edit history. AI never sends or saves automatically. A Notification rule list shows saved points, staged changes and deletions. Questions, chat, proposals and unsaved working drafts persist per administrator in the current browser tab across navigation/reload. Save conflicts preserve drafts. Other accounts, passwords, permissions and login sessions are unchanged. Delivery while asleep still waits for wake; the portal supports one shared daily schedule, not separate 3/7/15-day per-rule calendars.

Database transfer saving: master payloads are retained in server memory by saved version and update time. Every read still checks current account rights and the durable master revision; a new upload replaces the cached payload automatically. Persistent data is unchanged.
Legacy custom-rule scheduled email checks share a process-level throttle across authenticated browser sessions, avoiding duplicate background scans while retaining durable delivery claims and wake-up catch-up. Existing provider quota exhaustion still requires allowance recovery; no data is deleted to reduce transfer.

Network transfer optimization: bounded server-memory caches retain unchanged payloads. PostgreSQL computes a content fingerprint and sends only that fingerprint on warm reads; changed content is downloaded again. Product Status covers product/page collections, workspace settings, planning snapshots and notification task/delivery/change metadata; Stock & Planning covers shared production plans and portal settings in addition to the version-checked master cache. Cache results are copied before use, capped at 32 MiB/16 entries per Store, and never bypass live account or permission checks. Database errors are not served from stale caches. Source data, daily/interval notification rules and calculations remain unchanged. Free-tier suitability depends on measured traffic, cold starts and uploads; it is not guaranteed. Separate Neon projects isolate per-project transfer allowances; cross-project planning pulls still depend on source access.


## Daily sign-in and network transfer

Users sign in with their normal password once per browser/device per calendar day in **Asia/Kolkata**. Refreshing the page or reconnecting the same browser restores the workspace until midnight. This is a remembered login, not an email OTP login. Browser cookies must be allowed; private browsing or a different device has its own sign-in.

The browser stores a random opaque token, never the password. Only its SHA-256 hash is stored in a repository-specific session table. The cookie uses SameSite=Strict and Secure on HTTPS. Its expiry is fixed at the next India midnight and is not extended by refresh. Sign-out revokes the token, including restored tabs. Account disablement, password changes/resets and permission-version changes invalidate it. Live authorization remains fresh; authentication is never replaced by a cached role. Existing usernames/passwords and database URLs stay valid. No new secret is required. The new table and indexes are created at startup.

The existing version-aware workbook and production caches remain. Saved table preferences now use the bounded database-fingerprint cache instead of downloading every saved filter payload on each component rerun. Authorization selects only account status, rights and segment scope; credentials are not fetched for routine checks.

The first load after a process restart or a changed dataset still needs a database download. Daily sign-in mainly reduces password prompts; payload caching and smaller query results provide the main transfer savings. These changes do not enforce a monthly 5 GB cap. Compare real transfer in the Neon dashboard under representative usage. Database errors never cause authorization to fall back to a stale cached identity.



## Browser continuity and five-minute database idle pause

Daily login v2 hydrates the same app's browser-local opaque token before showing sign-in, instead of relying only on cookies from Streamlit's initial WebSocket request. Login waits for a browser-storage acknowledgement before rendering the workspace. The token is also written as a Secure/SameSite=Strict cookie on HTTPS. Passwords are never stored in the browser; SQL retains only token hashes. Restore requires the browser user-agent fingerprint, the original token, an active account/session version, and a time before midnight Asia/Kolkata. Connection IP changes do not require sign-in. Sign-out, account disablement, password reset, revoked rights, or next IST day requires sign-in. Existing older tokens may require one new login after this update. No new secret is needed. Browser storage must be enabled.

Real pointer, keyboard, scroll and touch activity is tracked separately from authentication. Automatic data/production refresh and scheduled-notification SQL checks are gated by a signed-in, visible browser active within the last 300 seconds. Hidden tabs pause background checks immediately. Browser activity messages run in an isolated Streamlit fragment and do not query SQL or rerun the whole app. Browser timers never count as user activity. Native controls and embedded tables are both covered. A user returning after an idle pause remains signed in until their fixed daily expiry, and the next action/active refresh revalidates live permissions. Due notification checks catch up on the next active check; idle/logout pages no longer drive database notification scans. In-flight user work is allowed to finish. Other active users or apps sharing a database can still cause transfer; this does not enforce a monthly quota.


## PnL sidebar and financial access

PnL is a separate lazy-loaded sidebar section (menu_10). Existing and newly created non-admin users start without PnL access. An administrator grants PnL and segment access in Manage users. Master uploads, salary uploads, mappings, assumptions and individual employee allocation details are administrator-only. Authorized users see aggregate salary expense and other results only for their permitted segments. Source details are paged on demand (200 source rows); table filtering/export covers the displayed source page, while calculations include every matching source record. PnL uses the existing export permission and table tools. Secondary sales is visible as a disabled future option.

1. Open PnL and select the financial year.
2. Upload the monthly **cumulative** XLSX master with saved Revenue, Production Cost and R&D Cost reports. Confirm coverage from 1 April to the statement end. The source details must reconcile to each saved Grand Total. Later uploads replace that year's master, never append overlapping cumulative totals. Other years and the independently uploaded salary file remain intact.
3. Upload the annual employee file. Salary means **monthly fixed CTC**, not annual CTC. Accepted columns include Emp Code, Emp Name, Joing/Joining Date, Leaving Date, Segment and Salary. NA/blank exit dates mean no recorded exit. Actual calendar-day proration includes joining and leaving dates, and the salary share is divided by the employee's complete set of distinct segment tags before the report's segment filter. Employee codes must be unique.
4. Choose Master Sheet Revenue or Stock Transfers × Std DP. Product cost remains the sum of the PnL master's production costs, not an invented sold-unit cost. R&D remains the master's segment total. The saved Revenue/R&D reports have no row dates, so they apply to the full stated cumulative period; the app does not manufacture monthly revenue or monthly profit. The monthly supporting schedule contains production cost and salary allocation only.
5. Stock-transfer valuation reads dated Sales Data when available. If Sales Data is a batch summary without dates, use the embedded Material Document List: the verified original Mvm 601 transfer rule is minus Qty in Un. of Entry for movements 601/602, including reversals, restricted to finished goods and the inclusive statement period. Movement codes and the sign multiplier are admin editable. Std DP is matched by SKU, preferring the current DP MRP table; plain DP is never substituted. The original ledger SKU-price convention remains the default, with explicit warnings for differing transfer/price unit labels and an admin strict-unit option. No pack conversion or historical price is invented. Date/Year-Month aliases are supported; monthly totals cannot value a partial month. Source filename/version is displayed.
6. Review unresolved SKU mappings. Existing planning Source.Name mappings are normalized to the PnL segment vocabulary. Ambiguous or unmapped SKUs are not counted in multiple segments. Administrators can resolve them in PnL assumptions. All-segment administrators see an Unmapped column; restricted users never receive records assigned to another segment or unresolved private records.

Working-capital days reuse Lead time & Consumption's source build. Inventory days use the inward-to-component-use interval shown there as FG conversion; this is not finished-product QC release. Creditor days use PO-to-inward. Only inward dates inside the statement period and the selected material type/segments are included. Non-negative durations count each material/batch once; repeated PO joins do not multiply observations. Missing history remains unavailable unless an administrator supplies an explicit day override. Selected-total days retain master Revenue weights across sales modes, so changing sales basis does not change the lead-time assumptions. Working capital and financing still sum the individual segment calculations.

The original default assumptions remain 8.5% annual interest, 18% tax, 90 debtor days and a 360-day annual basis. Manufacturing OHD, SG&A, depreciation and capex start at zero. Administrative adjustments are full-statement amounts per segment; product cost may have an explicit override, including a real zero. The statement year fraction is the sum of covered calendar-month fractions divided by 12. Working capital uses sales/(annual basis × statement year fraction) × (debtor days + inventory days − creditor days). Interest on working capital plus capex is prorated by that year fraction. PAT, cash profit, full-WC deduction and ROI follow the original PnL logic; ROI includes R&D in the investment denominator and zero investment returns zero, as in the original IFERROR convention. Rates retain the original loss/tax-credit arithmetic. These are management-model assumptions, not a claim of statutory accounting treatment.

Missing salary or missing/incompatible Std DP blocks dependent profit. Blank COGS and unresolved allocation remain warnings and mark the report incomplete; EBITDA and downstream profit calculate from displayed recorded cost subtotals and are explicitly provisional until corrected or overridden. Blank COGS is never presented as a confirmed zero. Missing lead history blocks financing/PAT when sales are nonzero. Recorded cost subtotals remain visible with explicit source warnings. Zero-sales working capital is zero without manufacturing history. Date/period coverage is administrator-confirmed: the app reads saved reports and never refreshes or assumes that a workbook's embedded ledger and PivotTables cover identical periods.

### PnL transfer and persistence

Only prepared report records and employee inputs are retained in the separate `stock_pnl_documents` table; original XLSX binaries and the master's full embedded accounting ledger are not stored or sent to viewers. Each document is compressed, content-versioned and replaced with optimistic concurrency checks. Small version reads check warm server-memory caches before any payload download. Source caches are bounded to 16 entries/32 MB; calculation caches hold up to eight prepared results of at most 4 MB each, keyed by master, salary, settings, planning version, segment scope and filters. Live account checks run before reads and responses. PnL does not poll its documents on a timer; refresh or a user filter action reads the necessary versions. The existing five-minute idle/hidden-tab pause remains. A cold start can reuse a persisted summary; missing summaries and changed sources require calculation inputs; savings are not a guaranteed monthly quota.

The planning assistant has an explicit read-only PnL tool using the same calculation service and current PnL/segment permissions. Its evidence contains the scoped statement, not individual employee salaries. No credentials, annual employee files or private records are added to the assistant's deployed code knowledge or this repository.


PnL refresh and snapshot rules: administrator uploads appear above filters and the statement. Save only FY/sales basis/segments/material type as private user preferences, restored across logins. Keep a loaded statement unchanged until a filter action, explicit Load PnL, successful upload or saved assumption change; unchanged files do not trigger a PnL reload. Source-version changes detected by the existing active heartbeat refresh affected cached views. Persist only a compressed permission-scoped summary (no employee/source rows or admin settings) in stock_pnl_summaries, maximum 64 entries of at most 500 KB uncompressed each; retain 16 warm summaries in process. Check live authorization and small master/salary/settings/planning version metadata before reuse. A new login/cold process can reuse the summary without downloading the planning workbook or employee source. Keys include deployed calculation revision, source versions, filters, canonical segment scope and admin/viewer visibility. Changed versions invalidate reuse; explicit Load PnL forces recalculation. Supporting records remain on demand and must match the loaded source version. Individual salaries remain admin-only. A sales-basis change changes Sales and dependent profit/working-capital ratios; it does not change product/R&D/employee/manual costs, depreciation, capex or lead-time day assumptions. Actual Neon savings require production measurement.

The dated-ledger profile retains the source Transferred DP Value convention: net Qty in Un. of Entry × the current unique SKU Std DP. When ledger and DP unit labels differ, show an explicit SKU warning rather than inventing a pack conversion. Administrators can disable this original SKU-price convention to require strict unit matching. A missing/conflicting SKU price still blocks profit. Dated saved Sales Data keeps strict compatible-unit valuation.


## Independent Sales workspace

Sales is sidebar menu_11, denied to existing/new non-admin accounts until explicitly granted in Manage users. Primary Sales and Secondary Sales are independent monthly XLSX snapshots: an upload replaces only the selected type, never appends cumulative duplicates or changes stock/PnL data. The administrator selects a visible worksheet, header row (1–50), and optional Segment source column. Preview detects actual uploaded columns; blank/duplicate header labels are made unique. Limit 25 MB XLSX, 125 MB expanded archive, 100,000 rows, 150 columns, 16 MB prepared JSON. No workbook binary or extracted full accounting model is stored.

Retain row values, dates, negative quantities, cancellation flags and billing types as uploaded. Do not infer net sales, discard cancelled rows or convert quantities between units. Billing dates are displayed as ISO dates; obvious identifier columns remain text. Use column filters on cancellation status, dates and units before interpreting sums. Segment comes from a selected/recognized Segment column, otherwise a unique planning SKU Source.Name mapping captured at upload. Unknown/shared mappings become Unmapped; date-file Source.Name is not automatically treated as a division. Adding an explicit Segment column can resolve these rows on the next upload. A later planning upload does not silently change saved sales mappings.

Server-side Sales access and canonical assigned-segment filters apply before returning data, including conditional reads and assistant tools. Restricted accounts never receive other divisions or Unmapped rows. Upload/preview and file replacement are admin-only; exports retain existing download permission. Administration includes uploaded Sales segment labels when configuring access.

Use the existing DataGrid for sort direction, numeric sum/average/count/min/max across all filtered rows, column conditions/value filters, hide/show, column reordering, grouping, pagination and full-screen view. Top controls provide search, Segment and Group by. Primary/Secondary column schemas, filters, layouts and top controls have separate private persisted preferences; compatible column-name settings survive a replacement and obsolete names are ignored. Columns are taken from each uploaded table, not a hardcoded template.

Persist compressed prepared sales snapshots in stock_sales_documents with content SHA versions and optimistic compare-and-swap replacement. Cache up to four versions/32 MB uncompressed per app process; metadata checks reuse the existing payload across user logins until its source version changes. A fresh process must read a persisted payload once. Browser view-cache reuse is confirmed through an authorized scoped version check; role/segment changes never reuse a wider cached response. Sales snapshots are preloaded after the first authenticated screen paints, and pages stay mounted across sidebar navigation. The existing active/idle-aware heartbeat checks only source-version metadata; changed versions, explicit Load Sales or a successful upload refresh affected data. No separate Sales polling timer is introduced. Search, group, sort and column calculations use the already authorized rows locally. These reduce repeat Neon payload reads, not all browser traffic or a guaranteed monthly quota.

The read-only planning assistant sales operation uses the same scoped source and shared server aggregation, with explicit primary/secondary type, exact group/value columns and count/sum/average/min/max. It bounds group results to 200 and requires narrowing rather than returning misleading partial totals. It preserves source signs/cancellation flags, warns about units and performs no source writes. No sales or salary files are committed to repository knowledge.


## Preloaded PnL and Sales, retained views

After the first authenticated workspace screen paints, a separate request preloads the permitted PnL catalogue/current saved-filter statement and both permitted sales types. The browser acknowledges this bundle once; later component responses omit it, and the large per-session copy is released. Preloaded pages are mounted while hidden so switching sidebar tabs does not destroy state or issue source RPCs. Switching sales types uses the already supplied browser-memory snapshot. Fallback reads occur during initial preparation only when no bootstrap is available, not as a normal navigation refresh. A new login prepares data once from durable/server caches and restores private PnL filters, PnL statement hidden/reordered columns, and separate sales search/segment/group/grid preferences. Raw records are not put in local storage; authorization precedes browser delivery.

The existing active heartbeat reports small content-version stamps, without downloading source payloads. Only changed stamps invalidate their cache; the existing hidden/5-minute-inactivity pause still applies. Explicit Load actions, PnL filter changes, uploads and source-version changes may load/recalculate data. Unchanged tab navigation makes no PnL/Sales requests. A completely new browser/session and a cold server still require initial preparation; server warm caches reduce Neon payload reads, not every byte of browser startup traffic.

Primary Sales additionally includes only SKUs in the current planning BOM parent Material/FG Code field, never component-only codes. Use available embedded BOM tables and saved BOM Cost worksheets. BOM parent-code membership is authoritative; unrelated material-type catalogues do not add a further exclusion. Do not use BOM Material Type as a parent type because it may describe the component. Without a planning BOM or sales SKU column, no Primary rows qualify. Secondary Sales is unaffected. Apply this before server responses and shared assistant aggregation, including existing uploaded snapshots. Include planning/BOM version in the Primary response fingerprint so a changed BOM invalidates conditional responses. Changing BOM eligibility never alters stored invoice values or cancellation/sign conventions.

PnL and Sales use consistent financial-workspace styling: compact top upload cards, aligned filters, subdued source strips and cache indicators, readable numeric tables, emphasized PnL subtotal/profit rows, and expandable explanatory notes. PnL statement Columns controls persist visibility/order by header name. Hidden columns do not alter calculations or bypass access boundaries.

Primary Sales matching normalizes case, outer whitespace and spreadsheet text width while preserving punctuation and leading zeros. Use available BOM parent-code fields, including the saved BOM Cost sheet when no embedded model is present; never fall back to general stock or sales SKUs. Include the Sales rule revision in source-version signals and the BOM-index cache key so stale zero-match caches are invalidated after a matching-rule change. Clear sales filters explicitly removes search/segment and column conditions while retaining column visibility/order, grouping and calculations.

Planning table Segment dropdowns support checkbox selection of multiple segments, including worksheet views, production views, lead time and source records. A row matching any selected segment appears once; All segments includes unassigned rows. An empty selection shows no rows. Selections retain the existing per-user saved-view preferences across sessions; legacy single-segment preferences remain valid. Filtering uses already loaded authorised data without fetching workbook records again.

BOM Cost displays Std DP and MRP immediately after Grand Total, joined by FG material code from the current planning master workbook DP MRP model (or price-bearing model tables). It uses the existing authorised, version-cached workspace payload, with no separate price request or polling. Master workbook replacement invalidates the payload. Missing or conflicting prices are blank; zero prices are retained. Original cost totals are unchanged.

Product Status connector v6 includes BOM cost Std DP/MRP and SKU-scoped Primary/Secondary monthly Sales snapshots with document versions, alongside the original stock/transfer and production views. Export remains planning-admin-only and requires download access; no background cross-app polling is added. Product Status retains its authorised saved copy until another explicit pull.

Primary and Secondary Sales have independent saved Year–Month checkbox filters, including whole-year selection, based on the cached date columns or separate Year/Month columns. ISO, Indian day-first, named-month and Excel dates are supported. When multiple date columns exist the user may select the relevant one. All periods retains undated rows; selected periods exclude rows without a valid date. Changing period filters performs no sales read or database download. Product-name columns do not alter calculation inputs or source-row drill-through.
Stock & Planning opens matched FG/code/description/Product Name cells in an internal read-only product panel. Product Status → Planning sheet → Sync products to Planning (or the normal authorised workbook pull) copies the dossier, readiness sections and document evidence into separate versioned product snapshots, plus the small name/code catalogue. No credentials, account records, edit history or disabled brief images are copied. Stock administrators grant View imported Product Status details inside Planning to viewers; admins have access automatically. Both name lookups and detail reads enforce assigned segments, and operational-tab notes obey their corresponding menu grants. Product-page stock, BOM, production, transfers and Primary/Secondary Sales use already-authorised Planning caches and matching SKUs. There is no external Product Status page navigation. Existing name-only copies require one new admin sync to populate details. Editing remains in Product Status; Planning displays the saved copy with its sync time.
Product detail payloads load once per opened product/version into a bounded browser cache, with a bounded server cache reused across logins. Warm checks use only catalogue version metadata; an unchanged manual validation returns not-modified. Changed snapshot versions or access scope invalidate the relevant cached details. Updating product snapshots does not download the master workbook again. Product Name is included in worksheet, production, lead-time and Sales grouping menus, plus a saved per-table grouping control where no page grouping menu exists. Unmatched names form an Unmapped product group; shared mappings do not duplicate quantity rows. Grouping and period changes operate locally without source reads.

### PnL statement corrections and transfer COGS
A replacement cumulative master uses the administrator's newly entered inclusive statement dates, even when earlier coverage was entered incorrectly. Production details reconcile against the full saved workbook Grand Total before excluding dated production rows outside that period (reported in source notes). Revenue and R&D remain the uploaded cumulative totals because they have no row dates; upload totals for the selected coverage. Salary eligibility, dated transfers and lead-time observations use the same corrected dates.
For Stock Transfers × Std DP, sales are eligible net quantity × Std DP and Product cost is that same quantity × cached BOM Cost Grand Total for the FG code. Returns retain their signs; missing/conflicting BOM costs block profit until corrected or explicitly overridden by an admin. No pack conversion is invented. Other statement assumptions are retained. Product cost opens the BOM-transfer evidence table. Cost percentages appear immediately below each cost amount and use cost ÷ selected sales × 100; aggregate ratios use aggregate amounts, with zero sales unavailable. Calculation revision invalidates compact persisted summaries; unchanged navigation continues using cached data.

PnL sales choices are labeled Primary Sales (uploaded cumulative Revenue), Stock Transfers × Std DP, and Secondary Sales (reserved). For every segment, transfer Sales reads only Std DP columns from DP MRP or eligible pricing tables; BOM/BOM Cost tables are excluded from fallback selling-price lookup. SKU price joins normalize case/whitespace while preserving significant codes. A missing/conflicting selling price never substitutes BOM cost. Transfer COGS separately uses BOM Cost Grand Total.
Authorized download users can export the currently loaded PnL's visible columns to CSV without reloading source workbooks. The export contains captured values, period/basis/version and formula drivers, followed by formulas for totals, profit, percentages and ROI. Source-valued amounts and working capital reference captured inputs; the CSV is not an upload-source workbook. Unavailable values remain unavailable. Export checks the existing live download permission.
Manage Users includes an administrator-only Access log with user filtering, IST timestamps and 100-event pages. Existing recorded sign-ins, sign-outs, views and other access events are read on demand; no polling or workbook loads are added. Passwords, session identifiers and raw event details are excluded from this view.
Product PnL: choose one or more products with checkboxes beside the segment filter. The imported Product Status working segment and SKU catalogue control selection and allocation. Primary Sales and recorded production cost match selected SKU codes; Std DP sales and BOM transfer COGS retain their existing dated-transfer rules for those codes. Monthly prorated salary is first split across employee segment tags, then shared equally across all catalogue products in each working segment; R&D uses that same fixed product count. Shared manual OHD/SG&A/depreciation/capex use the selected-product share; segment product-cost overrides are ignored in product mode to preserve SKU costs. Lead-time days retain segment assumptions. The allocation table shows product names, segment counts and shares; current CSV exports preserve the selected names and values. Saved product filters preload across logins; catalogue version changes invalidate affected summaries. Sync products to Planning once after deployment to include products without SKU codes in the denominator.

Daily browser login remains valid through midnight IST on the same browser while its opaque token and live account permissions remain valid. Feature permission denials no longer revoke an otherwise valid daily session. Browser hydration validates both local-storage and cookie token candidates, so stale storage cannot mask a valid token. Password/account revocation, explicit logout and expiry still invalidate sessions. PnL summaries persist in the database and are reused after a process restart; fresh browser sessions receive a compact authorized saved summary, not the master/salary/planning source files. Within a mounted workspace, switching tabs reuses the statement. Filters, source/catalogue versions and manual Load PnL control recalculation.

### Appearance
The top-bar Light/Dark theme switch saves its preference in this browser across logins. Appearance changes do not query or write Neon. Dark styling covers forms, tables, filters, dialogs, charts and status badges with contrasting text and focus indicators. The administration header and native login/password screens also provide the theme control.


Connection recovery: temporary network/database failures preserve the daily browser token and retryable restoration state. Product Status retains its existing workspace during failed refreshes; only explicit authentication errors return it to sign-in. Its Reconnect button retries reads without replaying saved changes, uploads or email delivery. Request timeouts begin when sent, not while queued. Initial component handshakes can recover after delayed server startup. Fixed midnight IST expiry, browser/IP binding, live permissions and five-minute inactivity gating remain in force.


Startup and smooth rendering: after live authorization and workbook/override checks, unchanged lead-time, BOM-price and purchasing display transformations may be reused across logins with the same menu/segment scope. This per-store process cache holds at most four entries and 16 MB of serialized prepared data, returns independent copies, and invalidates on workbook version/upload time, ongoing override revisions or scope/menu changes. No database reads or new polling are added by the prepared cache. Worksheet UI arguments are acknowledged by a compact signature carried on existing requests, then omitted from routine responses while the browser retains its copy. Embedded model/source records load separately on the first drill-down and are reused for that authorized workbook scope. Source/availability, catalogue, portal or scope changes send a fresh payload; a missing browser copy requests authenticated recovery. Returning from account pages also gets a full bootstrap. PnL/Sales preload and hidden-table rendering run after the first stock-screen paint, with immediate rendering when selected and mounted state retained afterward. Stock data updates are event-driven; the redundant initial/minute local JSON serialization loop is removed. Segment choices are memoized and empty searches avoid a full row scan. Formulas, exports, saved filters, live rights and five-minute inactivity gating are unchanged. These are application/code optimizations, not a measured startup-time or billing guarantee.


Native browser-session handoff revision 5: session restoration sends one initial browser probe and at most three startup-only retries (0.5, 1.5 and 3.5 seconds) while the server still awaits hydration. Once acknowledged, retries stop; duplicate browser messages cannot repeat token validation or load workbooks. Retry browser restore restarts hydration and repeats a pending storage write using a new acknowledgement nonce without changing the session token or expiry. Cookie/local-storage writes are checked by reading back the expected token; if neither browser store accepts it, the portal explains that refresh persistence is blocked instead of silently claiming success. The account initializer resource key changes once so pre-session cached Store instances are reconstructed with the session schema. Same-day midnight IST expiry, browser/IP binding, explicit logout/password/access revocation and five-minute inactivity gating remain enforced. No permanent session or recurring restore polling is added.



PnL Std DP × transfer uses the authoritative per-SKU BOM Grand Total (including equivalent Total BOM Cost headers) for product cost. Explicit embedded BOM Cost totals fill missing saved-sheet SKUs only; conflicting totals remain unavailable with a warning. Selling price continues to come from Std DP. Material joins and segment filters normalize surrounding spaces, case, Unicode and numeric Excel `.0` suffixes while preserving leading zeros. This applies to production QC release and stock table segment selection and server segment boundaries. Revised cached summaries refresh once after deployment; no periodic database reads were added.



Segment source correction: row Source.Name, including qualified columns such as Unique Material.Source.Name, takes precedence over SKU fallback. Empty source values fall back to master material assignments. Unique Material/BOM/BOM Cost remain the primary SKU segment catalogue; semantic price-table Segment labels (for example GWC or Ostomy) do not authorize or exclude DP/MRP rows. Price rows follow their SKU's master segment when no Source.Name exists. Production carries per-row source segments for ongoing orders and QC receipts, with the same original date and movement rules. Source-free saved aggregates remain restricted where they mix permitted and non-permitted segments. Scope/cache revisions prevent reuse of pre-correction restricted results without new recurring database reads. Lead-time filters match each member of combined source names.

PnL Std DP mode uses the qualified transfer-row source when present and canonical Energy Device/Devices naming. Saved BOM FG totals are preferred; if absent, embedded component Total BOM Cost rows are summed once per distinct source row for that FG. Missing component prices do not become zero or a selling price. Regression checks cover qualified sources, independent DP business labels, scoped access, QC sources and component-cost totals.


Lead-time replacement verification: a new master content version or upload timestamp invalidates the prepared workspace, recalculates lead-time dates/averages and sends the new lead table through the existing bootstrap response. Reopening an unchanged workbook reuses prepared results. Browser view preferences remain independent of source versions.



Full embedded model views: saved Excel pivots may be restricted by an Excel slicer, even when the website filter is All segments. Stock overview, BOM Cost and Completed batches now rebuild from the already-authorized embedded source tables when their required schemas are present. Stock overview sums FG Current Stock and retains the minimum original BOM component-capacity columns per FG. BOM Cost sums original component extended costs by FG/source, using component quantity × Price List.Price only when the explicit line cost is blank. Unknown component prices remain unavailable. Completed batches are FG records with a positive 321 receiving-side release, grouped by posting year/material/batch/source, excluding numeric-start batches. Order quantities come from distinct matching production orders; rejection is confirmed minus order quantity for confirmed orders (zero for unconfirmed); QC adjustments preserve signed 331/332. FG 321 outflow legs are excluded. Missing source schemas retain saved worksheets. Existing permissions are applied before building these views, and full results reuse the master-version display cache without new polling.

Std DP PnL shares the complete model BOM totals and does not apply the Primary sales manual Product cost override. Missing BOM costs show unavailable Product cost, percentage and Total cost instead of a misleading zero. Confirmed zero cost remains zero. Saved cost overrides remain available for Primary sales.



Upcoming-plan combined availability: one top button checks every permitted saved upcoming plan, independent of the displayed segment/search/column filters. Requirements use the existing physical BOM formula (planned quantity / base quantity × consumption), deduplicate repeated BOM item joins, aggregate repeated FG demand, and combine shared component quantities by material/unit. Current unrestricted plus quality-inspection stock is counted once. Plans receive complete allocations in start-date, end-date, stable-plan-ID order. A shortage or unverifiable plan consumes no stock, allowing later feasible plans to run. Differing units and unknown stock/BOM values remain Cannot verify; no pack conversion, on-order stock, future production, recursive SFG explosion or actual stock reservation is implied. The combined component table shows demand for all plans, including blocked ones. Per-plan rows identify Ready, Material shortage or Cannot verify and affected components.

The check's full details persist per permission scope and master content/upload timestamp, keyed by all plan IDs, revisions, material codes, quantities and dates. New/edit/delete/archive plans or a new master upload invalidate it. Status summaries travel through the existing availability-metadata query; full component detail loads only on explicit button click and is reused locally. No background availability computation or new polling timer was added. This aggregate replaces single-plan buttons in the interface; the legacy single-plan endpoint remains compatible for integrations.

Ongoing Edit and upcoming Edit/Delete/View history controls render inside each corresponding grid row. They receive the original row identity through filtering, sorting, pagination, grouping and Product Name enrichment, then send the stored plan ID and optimistic revision. Date edits stay in the plan editor opened from that row. Viewers retain history/read access; edit/delete still require their existing permissions. Ask AI can call the same read-only upcoming_availability operation without changing any saved plan.



Ask AI query validation: generated queries resolve only unique formatting-equivalent column names (Unicode/case/spacing/punctuation), including input fields, filters and metric sort labels, against the already-authorized loaded schema. Ambiguous or unknown columns remain rejected. Null optional lists, a single requested column/group string, wildcard projection and aggregate output projections are normalized without dropping filters or changing arithmetic. The 3-query/10-filter/3-group/4-metric/20-preview-row limits remain enforced. A failed generated query gets one schema-guided repair request; if still unsupported, Ask AI returns a clarification with no evidence instead of exposing the internal validator error. Source-data numeric errors remain visible and are not retried or silently converted to zero. Repair uses the existing in-memory snapshot and introduces no database reads or polling. Successful first-pass queries do not add an AI request; failed plans can add one.



Ask AI multi-sheet calculations: production_value is a server-side join of the authorized live ongoing/Under-QC batch views to the same SKU Std DP price sets used by BOM Cost. Ongoing uses expected FG quantities/saved overrides by default; explicit order-quantity questions use order quantity and are labelled theoretical before yield loss. Under QC uses confirmed production quantity pending QC release. Distinct orders are counted once per material/batch; QC takes precedence over ongoing to prevent overlaps. Default SKU pricing follows the original workbook per-SKU price convention without pack conversion; quantity and price unit labels are shown and differences flagged. Strict matching can be requested. Conflicting/missing prices or quantities stay unvalued with a known subtotal and incomplete total. SFG is excluded from combined FG sales unless specifically requested. Both production and BOM-price access are required; no plan is edited or archived.

The reusable cross_sheet tool supports 2–4 permitted loaded sources, source filters and explicit pre-aggregation, 1–3 matching join keys, many-to-one left joins, up to8 arithmetic steps (multiply/add/subtract/divide/percent/date_diff/min/max), grouping and summary aggregates. It uses only server-held data and typed operations, never generated Python, SQL or arbitrary formulas. Identical lookup rows deduplicate; conflicting duplicate keys require explicit aggregation, preventing join multiplication. Missing matches/inputs and zero divisors stay unavailable. Known-value sums are labelled subtotals when incomplete. Preview is20 rows; detail evidence/export is capped at5000 and output at40 fields; computation aggregates all rows up to100000 per source. Price/production/sales/menu and segment permissions remain enforced. Primary/Secondary Sales are lazy authorized sources with their own version checks; raw employee salary is not exposed—use the PnL operation. One invalid join-plan repair is allowed before a relationship clarification. No new database polling or master-file reload is added. Dedicated PnL, availability, production-value and purchasing tools remain preferred for their specific business rules.



BOM Cost Pack Size: display the DP/MRP pack-quantity field (explicit Pack Size/Units per Pack/Pack Quantity, otherwise No. of Units) immediately after Grand Total, before Std DP and MRP. Match by normalized FG/SKU code; preserve leading-zero identifiers. Product Size/dimensions are not substituted for pack quantity. Duplicate equal values collapse; conflicting/missing values stay blank. This is display enrichment only—no cost, price, stock or unit conversion changes. It uses the current authorized cached master snapshot; replacing the master invalidates the prepared display. No extra database query or polling was added.


Email presentation: each section now starts with 2–3 short AI-assisted factual sentences, then bullets and exact saved detail tables. Only compact rule titles, counts and explanatory facts are supplied to AI. Invalid output or unavailable AI uses a deterministic introduction. No workbook reread or delivery-history reset is involved.

Background scheduling: a trusted server cron can invoke `python notification_worker.py` at `30 3 * * *` UTC (09:00 Asia/Kolkata). Configure the matching portal DATABASE_URL and sender/AI environment variables; Product Status also needs ADMIN_EMAIL. Workers share durable daily/upload markers, recipient permissions and submission uncertainty handling with login delivery. No browser or authenticated user session is required by the trusted worker. Source preparation does not activate hosting or alter saved enable/pause settings. A login earlier in the day can consume the same daily batch; use the background job as the primary trigger if exactly 09:00 is required.

Stock notification policy revision 3: Rule 1 description terms are authoritative when nonempty, so ZPAC/other packaging types cannot include an unlisted box. Explicit include codes override terms; exclude codes always win. Defaults use label, pouch, polybag, poly bag, blister, leaflet, insert and wrapper. Saved thresholds remain editable and labels no longer hard-code 3,000. Pending upload candidates recheck matching and thresholds against saved policy, without downloading workbooks. Rule 7 defaults to 7 days; legacy 14-day settings migrate once to 7 while other custom values remain. Rule 7 still evaluates only on new master upload using latest movement versus uploaded reference date. New matches after lowering a threshold require the next upload; already sent messages are not resent.

Assistant complete results: AI prose receives at most 20 preview rows, while query tables have lazy Previous/Next paging over every matching result. Full-result downloads include every page, preserve complete cell text, and are independent of the displayed page. Table filters/calculations on one loaded page remain page-local; use the query itself to filter/calculate across all data. Existing export permissions remain in force (admin only); server reads validate source versions and current access. Pages are cached in browser memory (up to 10 per open result), never polled or predownloaded. Result size limits produce an explicit error rather than a partial download. No scheduler or email activation is changed.
Stock Ask AI exposes server-owned result tokens to permitted readers, without granting export. Admin Excel export continues to include full result/matching records. Joined calculations now retain all detail rows within the existing 100,000-source-row bound instead of silently stopping at 5,000.

Appearance styles: the selector beside light/dark offers Existing UI, Glassmorphism, Spatial UI, Neomorphism and Liquid Glass. Colour mode and visual style are independent browser-local preferences, retained across logins. Existing UI is the default. Decorative effects apply to surrounding chrome; tables, overlays and dropdowns remain readable/opaque. No remote assets, fonts, new polling, database preference writes or source reloads are added by switching style. Blur is limited to header/sidebar, with a reduced-transparency fallback. Stock Planning's grid, PnL, production, product drawer, controls and native account forms use the Product Status dark palette.

02:30 IST scheduled notifications: `.github/workflows/daily-notifications.yml` runs `python notification_worker.py` at UTC `0 21 * * *` on the default branch, and also allows a manual workflow run. It checks required GitHub Actions secrets before installing/running; no secret values are printed. A login before 02:30 IST does not consume the daily batch. GitHub Actions is the primary trigger; a later authenticated visit is a fallback when the batch is still pending. Both paths use the same durable claims and live recipient/segment checks. Concurrent runs and subsequent logins cannot repeat a sent batch; uncertain transport outcomes stay uncertain rather than being blindly retried. Previous-day history cutoffs and 3/7/15-day policy intervals are unchanged. A failed job does not advance a delivery cursor unless the existing dispatcher has safely recorded the corresponding work. No GitHub-status polling is added.

GitHub configuration (separate from Streamlit Secrets): in this private repository Settings → Secrets and variables → Actions → New repository secret, add DATABASE_URL (this portal's existing database), RESET_FROM_EMAIL, and either RESEND_API_KEY or SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD. Optional AI wording uses GEMINI_API_KEY or GOOGLE_API_KEY and GEMINI_MODEL or ASK_AI_MODEL. Product Status additionally requires ADMIN_EMAIL. Keep delivery enabled in Email management. Never put credentials into workflow YAML. Workflow configuration alone cannot send until these secrets and GitHub Actions are enabled; scheduled start time may be delayed by GitHub capacity. The manual action sends due work, not a duplicate test message. Existing Streamlit first-login settings are superseded only for the start time: before 02:30 daily checks wait, afterwards pending work can catch up.
Stock upload-triggered rules keep their upload-based semantics, independent of the daily 02:30 gate. The worker drains queued jobs in bounded groups using existing claims without reevaluating a completed daily batch or downloading the workbook for built-in daily rules. An unchanged master/sales workbook is not reuploaded by the workflow.

Stock Planning scheduled email can now read a single GitHub Actions repository secret named PORTAL_SECRETS containing the same flat TOML format as Streamlit Secrets. Only notification/database/AI keys are accepted; administrator login passwords are ignored. Individual nonempty repository secrets override matching bundle fields, so old setups still work. Invalid TOML reports a generic format error without echoing its content. Gmail app-password grouping spaces are removed. Parsing is local and adds no network requests. The daily schedule, recipient access and duplicate protection are unchanged.

Daily notification target moved 5 hours 30 minutes earlier: 02:30 IST, using 21:00 UTC on the preceding UTC date. Worker and authenticated-visit eligibility use the same 02:30 IST boundary. Prior-day reporting cutoffs, duplicate claims, intervals, permissions, uploads and browser styling are unchanged. GitHub execution delays can still occur.

Daily email queue selection binds the daily batch wildcard as a query parameter for PostgreSQL and SQLite compatibility. Existing daily claims and duplicate prevention remain shared between scheduled and login delivery.

Ask Assistant is available in every shared table toolbar to users with tool access. It starts with table name and column metadata and uses existing permission-checked cross-table calculations. It queries saved data across pages; screen filters must be stated in the question. Tables never transfer their rows to the assistant on opening; Gemini is only invoked after a question with sharing consent. Metadata is an untrusted navigation hint, never evidence or a permission grant.

Table-launched Ask Assistant opens in a dedicated right sidebar, reserving desktop space so the table remains alongside it. The main Ask AI page retains its existing layout. On narrow phones the panel docks below the table.

Upcoming batch quantity displays the selected FG/SFG material’s workbook UoM beside the input, using the already loaded material catalogue. Missing units are labelled unavailable; selecting a product updates the unit immediately without extra database requests or quantity conversion.

Table Ask Assistant can be minimized to restore the table’s full width and reopened with Restore Ask Assistant. The hidden chat stays mounted, preserving the draft, answers and in-progress response without additional data or AI requests on minimize/restore.

The main Stock Planning UI switch offers Fiori · Admin preview only to authenticated administrators. Its launchpad and grouped navigation reuse the existing live workspace views and cached snapshot counts. No demo data, sample calculations, extra polling or secondary database connection is introduced. Administrators access user management, workbook management, workspace settings, email management, history/access logs, password and sign-out from the profile icon. Non-admin accounts cannot activate this shell even if the same browser retains an admin’s Fiori preference. Existing styles remain available and no new user permission is granted.

The administrator Fiori preview now provides My Home, workspace spaces, Favourites, Recently used, App Finder, local application search (Ctrl/Cmd+K), favourite pin/unpin and favourite ordering. Discovery uses only permitted app labels from the current workspace. Favourites and up to six recently visited app IDs are stored per username in browser localStorage; no workbook data or API calls are used for app discovery/personalisation. Access revocation still uses the existing server permissions and identity-based workspace remount. Dark-mode switching preserves the active workspace. The original calculations, exports, cached tables, admin profile actions and viewer UI remain unchanged. Design reference: SAP Fiori My Home, spaces and App Finder documentation.

Fiori application pages retain the existing functional components with list-report styling: compact tables, sticky headers, column filters, totals, blue record links, filter/tool bars and pagination. My Home breadcrumbs return to the launchpad. Product object pages keep their real SKU-scoped source records and documents while using Fiori-style header and section tabs. No SAP SDK, external fonts, sample data or new network queries are introduced by these visual refinements.

### Fiori navigation and controlled rollout
Administrators retain Fiori access. Manage users → Manage rights → Enable Fiori Launchpad UI grants the style switch to selected viewers; new and existing viewers default to disabled. This changes presentation only; segment, section, export and edit permissions remain authoritative. Rights changes follow existing session revocation.
Fiori Production opens QC Released, Under QC, Ongoing Order List and Upcoming Production Plan directly from its header dropdown. The existing layout retains its four expanded sections. Header dropdowns retain their text without decorative down arrows. Record and full-screen table controls sit below the measured shell; Home or app navigation dismisses drill-downs and restores the cached workspace without fetching the workbook.


### AI business dashboards and chart-value evidence

Insights & Graphs now presents an AI-designed dashboard for each permitted loaded section: two to four server-calculated KPI cards above the graphs, findings and suggested checks, section filters, and supporting records. KPI queries aggregate all matching rows, never the displayed top-ten chart sample. The AI selects measures and their basis; unsafe sums of rates, percentages and durations are rejected, and quantity sums require a single declared source unit/currency when those fields are present. Conservative record/material counts remain available if a business measure cannot be verified. Missing measures remain unavailable.

Analysis includes the existing planning, purchasing, forecast, lead-time and production views; authorized Primary/Secondary Sales snapshots; the latest uploaded financial year's cumulative PnL on the existing Primary Sales basis; and expected ongoing/under-QC potential value at the established per-SKU Std DP convention. PnL uses segment aggregates and never sends individual salary records. Missing uploads or unsupported calculations are reported rather than invented. Potential value is not guaranteed sales, and QC age alone is not an overdue release.

AI may propose up to three connected business comparisons. These use the registered read-only insight_comparison operation and the existing cross_sheet calculator: two to four scoped sources, explicit keys, right-side uniqueness, left joins, bounded arithmetic, preserved missing inputs and rejected many-to-many multiplication. Only permitted report source tables enter the join catalogue. The source grain, period/unit basis, unmatched counts and incomplete-calculation caveats are retained. No new PS, physical BOM, forecast purchasing or PnL formulas are duplicated in prompts.

Section filters apply to the complete saved section source before recalculating KPI cards and chart queries. Applying or resetting them does not call Gemini. Filtered findings are labelled as calculated; the original AI narrative is hidden for that section. The executive brief and priority board continue to describe the full saved snapshot, as labelled. Filters on ordinary workbook tabs do not silently change this report.

Clicking a bar, slice, point, or the accessible value selector opens the exact contributing evidence: a ranked raw mark resolves to its original row (even when labels repeat); a grouped mark resolves to every row matching its group keys and query filters. KPI cards open all matching records behind that KPI. Source records paginate; administrator downloads use the same selected scope. The complete graph data button remains available. Source tables retain the existing per-column controls.

Natural-language Add graph with AI remains available in every report section, including connected sections, and uses the currently filtered source. Added chart definitions are retained when filters reset; no workbook or plan values are edited. Fresh analysis resets section filters. Report evidence is bound to user permissions/segments, workbook, production, independent Sales/PnL versions, and deployed rule revisions. Consent is required before provider generation; filtering and drill-through are local server calculations. The application uses the existing Gemini API key.


### Resumable Insights generation

The Insights Run analysis workflow now uses a session-scoped job instead of one request spanning every business view. Source preparation, connected comparison selection, dashboard calculations (two sections at a time), and written reviews return separate progress replies. Each provider phase performs at most one Gemini request. Completed dashboards become visible before the full analysis finishes, with the same KPI cards, source records, filters and validated calculations.

Provider context retains the deployed rule text and relevant calculated evidence without repeatedly sending the complete source-implementation catalogue. AI-added graphs reuse the report's validated prepared snapshot and compact rules instead of repeating all production/material checks.

If a step fails or its reply is lost, Resume analysis continues the same job and step. The most recent step response is replayable without duplicate provider calls or duplicate sections. Changed data, permissions or rules invalidate the job and require fresh analysis. Jobs are session-scoped; a browser session reset may require a new analysis. Keep the page open during generation. Filters and adding graphs become available after the job completes; already completed sections can be inspected while later sections are running. The progress indicator reflects completed stages rather than elapsed time. The existing single-response server path remains compatible during deployment.


### Checkbox filters across tables

Data-value filters use searchable checkbox selections. Main stock/requirements status filters, Sales segments, Lead-time material types and PO/inward years, PnL segments/material types, Insights section fields and administrator access-log users support multiple selected values. Existing segment, Sales year/month and product checkbox controls remain available. Column filters in workspace and administration tables retain typed multi-value selection and now include Select shown values and Clear chosen values controls.

Selected values use OR within one field and AND between different fields. Selections do not duplicate source rows. Blank, empty text, numeric values, booleans and text codes retain their identities. All values removes that value restriction; None selected returns no matching rows in the new filters. PnL segment selection preserves the established empty-list-means-all-permitted-segments convention, and its Clear filter action restores that scope. Previously saved single-value filters still load. Table-level controls retain their existing account-scoped persistence.

Insights checkbox filters recalculate KPI cards, charts and click-through source evidence over the complete matching saved source. Large unique-value lists are searched and paged from the authorized report snapshot rather than the chart's top-ten sample. Value searches do not send another request to Gemini. Up to eight section filter fields and 500 explicit values per field are supported. Report permission, version and rule checks also protect value searches.

PnL lead-time material-type selections filter the existing observation calculation and aggregate each qualifying material/batch observation once. Financial years, statement bases, source/worksheet selection, grouping, sort direction, calculation operators and edit-form fields remain single-context controls so distinct cumulative statements, datasets or rules are not silently combined. Access-log user selections apply before server pagination and remain administrator-only.


## Saved Insights dashboards and same-day browser sessions

Completed Insights & Graphs reports are stored durably in the application database. Opening the tab after refresh, login or a server restart restores the latest completed report without a Gemini call, with fresh authenticated source-data/export tokens. Users share the saved report only when their role, permissions and allowed segments match exactly. Regenerate analysis replaces that scope's saved report when the new run completes; incomplete/failed runs leave the previous completed report intact. A changed master workbook, production/sales/PnL source revision, planning knowledge or access scope invalidates report reuse. Saved report status is fetched on opening/reloading the tab; no new background polling is added.

Each graph has Delete graph. Its server-validated comparison is removed from the saved report and suppressed in later runs. Manually added graphs retain their validated query, presentation and request in the same access scope. New runs recalculate these graphs against the current full section source without another AI planning request. Section display filters do not silently become permanent custom-graph filters; use the Add graph request to specify permanent conditions. Definitions survive master workbook updates. Missing/changed columns produce a visible warning and retain the definition for later correction; old quantities and old narrative are never reused for recalculated custom graphs. Deleting a custom graph also removes its saved definition. Limits: 30 graphs per view, 100 saved custom definitions, 1,000 removed comparison definitions. Concurrent edits update the saved layout atomically; an older report cannot overwrite a newer completed run. Graph changes do not alter workbook or production records.

Daily login storage uses one combined browser receipt for write success and acknowledgement, with bounded retransmission, so fragment/native-form handoffs cannot consume a partial acknowledgement. The server keeps a consistent browser binding through the login handshake. Both cookie and local-storage candidates remain supported. The opaque token is required in addition to that binding; an IP address alone never signs anyone in. Same-day restores expire at midnight Asia/Kolkata and still respect logout, password/account changes and revocation. Blocked browser storage is reported explicitly. This change applies to this Stock & Planning repository's shared daily-session helper.


## Insights navigation and interrupted-run recovery

Insights mounts on its first authorized visit and stays mounted while hidden during workspace tab switches and Fiori Home navigation. Switching tabs preserves report sections, selected planning view, filters, chart presentation and the same generation loop. Returning to Insights makes no new restore or Gemini request. Same-source workspace/branding notifications check metadata without clearing loaded results; actual workbook, planning-source, rules or access changes still invalidate them.

Each successfully delivered chart/review phase with sections saves a compressed, access-scoped checkpoint and continuation step in insight_checkpoints. Closing/reloading the page or signing in again restores those delivered sections and fresh source-data tokens without an AI call, even if the entire run had not finished. A saved interrupted run offers Resume analysis at its next phase; a new page must grant Gemini consent before resuming. Workspace switches can continue an already-consented run while the app stays open. No background worker continues after the app closes. Failed checkpoint publication retries without repeating a successful provider phase. Partial checkpoints are separate from the last completed report; completed generation saves the report and removes only its own checkpoint. Another access scope or a changed workbook/business-source/rules revision cannot load the old continuation.


## Faster first screen and isolated workspace requests

The loading flow follows Product Status's fragment-based host and compact-reply approach. Ordinary workspace RPCs run inside a Streamlit fragment rather than rerunning the outer login/navigation host. The iframe and its parent stale wrappers remain visible during work. Login expiry, permissions and current business-data metadata are still checked server-side. Logout revokes its daily token and hands browser-storage clearing to a full app rerun; account/admin navigation also explicitly hands back to the outer host. Connection failures retain the browser login and offer Reconnect.

The first component render sends the permitted worksheet views and a lightweight deferred-preload hint. It does not first read independent Sales snapshots or calculate PnL. After the first screen has painted, one authenticated workspace_preload RPC warms authorized Sales/PnL; received views remain mounted for instant tab switching. Changing a preload ID does not remount the whole Dashboard or discard Insights state. A small connection skeleton appears before the host handshake. A source change during preload discards a mixed-version result.

Embedded source/model tables are excluded from the first frame and routine compact replies. The first source-data drill-down loads the same segment-scoped records through workspace_model_tables, sharing an in-flight request and reusing the result on later openings. Workbook/access changes invalidate that copy; a late response cannot cross an account/scope change. Branding-only changes retain it. Segment/BOM lookup indexes are reused for immutable model snapshots. Calculations, quantities, availability rules, exports and Insights/checkpoint persistence are unchanged. Source records may take one initial request on their first opening; the normal worksheet screen no longer waits for their transfer. No new background polling is added.


### Checkbox grouping and Segment
Every table grouping control supports multiple checked categories. Selected fields form a combined group (for example Segment + Material + Batch); clearing the selection restores ungrouped records. Existing single-field preferences remain readable, and new selections are saved with the table/section preferences.

Segment is always a grouping option, including when the table has no Segment column. Workspace tables reuse the authorized workbook material/BOM segment map; administration workbook records receive per-row segment labels from the existing admin-only records operation. An explicit source/Segment value takes precedence. A material mapped to several segments stays in one combined segment group, so quantities and record counts are not duplicated. Rows without a reliable mapping are labeled Unmapped segment. Tables without material/source identifiers (such as account or event logs) keep that label rather than inventing business attribution. Grouping only changes presentation: row drill-downs, matched exports, filters, access boundaries and planning arithmetic retain their original source records. Admin workbook grouping applies to the displayed 200-row page, as before.

The grouped view includes a pivot output panel. Use Up/Down beside selected grouping fields to change their order, select numeric value columns and Sum/Average/Count numbers/Minimum/Maximum, and sort output by clicking its headings. Per-category checkbox filters and search narrow both pivot output and the grouped source records. Pivot settings and field order use the existing private view preferences. Record count is the default; numeric totals require explicit value selection, and users must keep units compatible.

Download pivot (Excel) produces a real .xlsx snapshot containing all filtered summary groups, the selected grouping columns, record counts and selected numeric aggregates in output sort order, regardless of screen pagination. It preserves numeric cells and treats imported text as literal text. This summary export requires the existing broad download permission and a fresh authorization check; administration uses its existing authorized table-export operation. Narrow matched-record exports retain their existing server validation and do not grant a new broad export right. This workbook is a summary snapshot, not an editable native Excel PivotTable object.

### Private added columns and original layout
The table assistant offers Add lookup / calculated column after explicit Gemini consent. Definitions are private view preferences and are reapplied with the shared read-only cross-sheet calculator against permitted current sources. Matching right-side keys must be unique; ambiguous matches require explicit aggregation. Missing matches and invalid arithmetic remain unavailable. Added columns participate in filters, calculations and grouping. Delete removes added definitions and dependent added columns; deleting an original column removes it from the personal layout. Reset to original layout restores original columns and removes added columns, filters, ordering, calculations and pivot settings. Master source data is unchanged. Save table layout waits for durable preference saves for future login.

### Sales BOM segments and pivot matching records
Primary and Secondary Sales include a derived BOM Segment grouping column built from the current BOM parent/FG code and Source.Name (or its Segment fallback), using the existing SKU key normalization. The uploaded Sales Segment and its access rules remain unchanged. Shared SKUs have one combined BOM segment label and never duplicate sales rows or totals. Restricted accounts see only permitted BOM segment names; missing mappings show Unmapped segment. A source-column name collision gets a distinct derived header. Both Sales snapshot versions and metadata change signals include the BOM/master version so the dimension refreshes after a master update.

Every pivot output value (including grouping labels, record counts and selected measures) opens the full matching group from the already-authorized, already-filtered input rows. Group lookup uses the original typed dimension tuple, so sorting, paging, nulls, numeric/string lookalikes and zero values cannot point to another group. The matching-record dialog uses the normal table tools and its own saved view. Numeric-measure results offer an optional numeric-input-only view; all matching rows are shown by default so missing values and original table calculation rules remain inspectable. Existing record drill-down handlers preserve source-row identity. Opening matching records makes no AI/model request or new data fetch. Data, grouping or source changes close stale dialogs. Exports continue to use the existing authorization and original matched-row projection rules.

Shared table toolbar styling keeps search fields at a compact fixed height and bounded width, with labels and filter controls aligned inline. Grouping-field order controls open in a separate Order dropdown so multiple grouping fields cannot stretch the toolbar or search input. Column quick filters and dropdown searches remain compact across Stock, Sales, PnL, production, Insights and administration; narrow screens wrap controls without forcing horizontal page overflow. This affects presentation only.


Date table filters and calendar pivots: every shared business/admin data grid offers Date is on/not on, before/after (including inclusive variants), inclusive between, blank/not blank and invalid/unrecognized date conditions. Date inputs compare calendar days, including all times written on the selected day; source cells are never changed. ISO dates/timestamps, day-first DD/MM/YYYY (also dash/dot separators), and full dates with English month names are recognized. Timestamps retain the written calendar date, without timezone conversion. Numeric workbook dates use Excel's 1900 system; serial 60 (the fictitious 1900-02-29) is invalid. Numeric strings and month-only periods are not guessed as full dates. Recognized dates cover 1900–9999. Invalid/blank dates do not pass comparison conditions; blank and invalid have separate conditions. Between applies when both bounds are entered; reversed bounds show a message and match no records. Checkbox value choices intersect conditions, and filter state (including range end) uses the existing per-user layout persistence.
Grouping offers derived Year, Quarter, Month, Date and Day of month for recognized date fields. Date hierarchy → Use Year → Month → Date replaces that field's existing date groupings while preserving other selected dimensions such as Segment. Calendar parts are view-only and retain original row identity. Months sort by calendar number; multiple years remain distinct when Year is selected. Month alone intentionally combines that month across years. Invalid dates group as Blank; filtering invalid dates separately remains available. Numeric columns are not inferred as dates unless their header identifies a date; other columns can be inferred from a bounded sample of parseable date strings. Saved valid derived fields remain usable when a filtered view becomes empty.
The existing pivot, date grouping, hierarchy and subtotal controls are retained. Subtotals stay closed on each pivot setup and are calculated only after the user clicks Show subtotals or selects a subtotal level. The open state is local and never saved; old saved subtotal/hierarchy/collapse preferences cannot auto-open subtotals on setup or reload. Changing the grouping fields or table closes subtotals again. Saved level choices remain available, and collapsed levels clear when subtotals are explicitly requested. Before that click, only leaf groups are shown/exported, with no parent subtotal calculation. Subtotals use the existing calculation on all matching original rows (averages exclude nonnumeric values), not sums/averages of child aggregates. Clicking a subtotal or detail value opens its exact original records after column and pivot filters. Hierarchy and collapse choices persist with the layout. Excel exports the current expanded/collapsed output over all pages, with Row type (Subtotal/Detail) and Level columns; summing subtotal and detail rows together would double-count. Flat export remains one row per leaf group. Existing download authorization, narrow matched exports, custom-column restoration and reset behavior apply. These changes affect table views only: no source workbook mutation, new AI call, multi-table operation, PS ordering, BOM availability, forecast purchasing arithmetic or production window changes.

Pivot subtotal controls are optional and off by default, including when date fields are grouped. Show subtotals explicitly adds/removes all parent totals, and checkbox Subtotal levels independently selects fields (for example Year only or Year plus Month). Detail groups remain visible when a subtotal level is removed, even if that hidden level was previously collapsed. Selected levels are saved with the layout; the open state is not saved. Excel follows the currently displayed output. Flat rows continue to contain leaf groups only.


Custom-column lookup planning accepts ordinary requests such as "add Std DP value column based on Material from the Std DP table". The current table remains server-owned s0/USER_VIEW. Harmless planner metadata (known-field projections, empty filter/group/metric/sort fields and preview-only limits) is normalized to the unchanged current-table source, retaining all original fields and the hidden row ID. Nonempty filters/aggregation/sorting, wrong aliases/tables and unknown fields are rejected; right-side permissions and unique-key validation remain unchanged. Direct lookups may output the joined price without arithmetic. Missing matches stay blank, leading zeros and original row order/grain are preserved, and saved columns restore without another AI request. Custom-column helper revision 2 is refreshed at app startup.


Custom-column lookup sources retain stable source identity rather than relying on display names or positional T1/T2 IDs. Worksheets, embedded model tables and derived views carry distinct provenance keys; permitted Sales/PnL sources also have stable identities. Two permitted sources may share a display name, and the AI catalogue identifies their origin and exact current ID. A new lookup saves that selected source's identity and name and rebinds it against the current authorized catalogue, even when another table changes positional IDs. Updated rows from that same source are used on restore. It never silently switches to a same-named table if the selected origin disappears or is no longer permitted. Duplicate identities and genuinely ambiguous legacy name-only definitions still require clarification. Legacy uniquely named definitions remain compatible. Right-side key uniqueness, scoped access and row-preserving arithmetic remain unchanged.

Custom-column requests may name only the desired field and matching key, for example "add Std DP against Material Code", without naming a sheet. The planner receives the complete permitted source catalogue plus lookup discovery hints with exact candidate table IDs, worksheet/model origins, requested value fields and semantic Material/Material Code/Material Number/SKU key pairs. Std DP aliases include Std. DP and Standard DP, but not unrelated Standard Price/standard cost. Hints do not execute or bypass source permissions, row/key validation or missing-match handling. When sources differ in business definition/period, the assistant must clarify instead of inventing a merge, first/latest price or aggregation rule.


### Faster Ask Assistant and remembered sharing
Ask Assistant accepts a draft immediately while a metadata-only status check runs. Opening it does not prepare source DataFrames or call Gemini. Sending remains disabled until workbook availability, Gemini configuration and sharing approval are known. The optional “Always allow Gemini” preference is private to the signed-in account, defaults off, survives future logins through durable view preferences, and can be revoked with either sharing checkbox. It covers Ask Assistant questions and added columns only; Insights retains its existing consent. No question or record is sent just by opening the window or saving permission. Every send still validates current source versions and permissions. Existing prepared source caches are reused; deployed rules and source descriptions are parsed once per file metadata signature and refreshed when an allowlisted file changes. Provider response time still depends on Gemini and the requested calculation.

Added-column values in worksheet, Sales, lead-time and production tables are calculated against the complete authorized table before screen Segment/search/date/status filters. Filter changes project existing results onto original row references, including duplicate materials and zero values, so switching from one Segment to All does not blank values or call the column resolver again. Source or permission changes still invalidate calculations; saved definitions reapply on the current authorized snapshot without another Gemini request. Explicit filters inside a saved lookup definition remain intentional.


### Added-column restoration across navigation and sign-in
Adding a column now saves its definition on the authenticated server before the request is acknowledged. Success no longer depends on a later browser preference timer; a failed database save fails the add request. Definitions remain private per user and table scope. Printable table-name punctuation is supported in preference scopes; control characters and oversized scopes remain rejected. On the next login, saved definitions calculate against current authorized data without calling Gemini. A bounded, account/access/workbook/definition/table-scoped in-memory value cache retains displayed values across tab remounts while the server revalidates them. Workbook/source events clear retained values; failed validation clears that result. No browser-disk copy of records is created. Retry added columns repeats restoration without another AI request. Source changes, revoked access and missing/ambiguous lookup sources never fall back to old values.

Added-column values open matching-record details on click, including zero or unavailable values. The server rebinds saved sources to the current authorized catalogue and validates the original row, source versions and permissions. Details show the selected current-table input, the actual permitted right-source records matching each normalized join key after the definition’s filters (including original contributing rows for grouped keys), and the calculated output. Same-table arithmetic shows the current input and result. Joins continue to use the shared read-only calculator; no Gemini call or new arithmetic implementation is used. Records are paged at 50 per source. Source/account/workbook changes close the detail window; source access errors do not reveal retained evidence. If a join key is itself an aggregate metric, only matching prepared inputs are shown rather than claiming raw-row lineage.


### Latest/earliest date lookup columns
The shared query engine supports explicit latest/earliest calendar-date metrics and ISO date output, including day-first and Excel date values via the shared server date parser. Blank inputs remain unavailable; invalid supplied dates are rejected. Numeric max/min remain numeric. For a requested Latest 101 date, the column planner must filter movement type 101 and group by all selected production join keys before joining; prefer Material plus Batch/Production Order available in both sources, never Batch alone across materials. Do not infer reversal/netting rules or choose an arbitrary transaction. One bounded repair request may correct duplicate-key or incorrect date-aggregation plans, using the original question and validation error; unspecified aggregation/grain or invalid source dates require clarification. The row-preserving join, permission checks, saved-source identities, private durable definitions and matching-record drill-through remain enforced.


### Assistant filter compatibility
The shared query engine canonicalizes unambiguous field/operator/values aliases and literal comparison spellings (=, equals, etc.). Null checks and blank checks remain distinct. in/not_in accept bounded literal lists; no SQL, expressions, nested filters or unknown extra keys are executed or discarded. Conflicting aliases and malformed values remain errors. The column planner explicitly receives the supported filter schema, and one existing bounded repair attempt now also handles malformed filter errors without dropping requested conditions. The same normalization applies to saved definitions and matching-record drill-through.


### Assistant aggregate-metric compatibility
Source metrics accept unambiguous field/function/aggregation/operator spellings and standard aggregate synonyms, including latest_date/max_date to chronological latest and earliest_date/min_date to earliest. An optional name/alias is presentation metadata: it maps to the canonical op(column) field in selected output, sorting and subsequent join/calculation references. Conflicting aliases, unknown extra fields and executable expressions remain rejected; no calculation is guessed or silently removed. Saved plans are not modified in place. The existing one-attempt column repair also handles unsupported metric shapes and states the exact source-metric and row-calculation schemas.


### Persistent added-column value cache
Calculated added-column values and warnings are stored compressed in a private per-user, per-table database cache after an add or restore. A fresh login loads an exact cached result without preparing source tables, running joins/calculations or calling Gemini. There is no daily/login expiry. Cache fingerprints include workbook/source/production revisions, current access scope and role, the complete base-row order/schema and exact definitions. Workbook updates, relevant source edits, changed definitions/rows or permissions therefore require one fresh calculation; stale or unauthorized values are never a fallback. Click-through details still use current permission-checked source records. Storage is bounded to 32 table entries and 16 MiB of encoded payload per user, with a 4 MiB compressed entry limit and 32 MiB decoded limit; oversized/evicted results can be recalculated from saved definitions. No workbook rows are stored on browser disk.


### Login loading percentage and prepared workspace
Login waits on a staged percentage screen before opening the dashboard. Percentages represent completed preparation stages, not estimated elapsed time: connection/workbook and preferences (0–20%), saved Sales/PnL (40%), permitted embedded source tables (55%), cached table readiness (65%), saved added-column values for available main/forecast/production/lead-time/Sales/PnL/order-summary tables (65–95%), and table interface modules (100%). Source detail tables and saved valid reports are reused when opened. Added columns use the persistent value cache when valid; missing entries calculate once without Gemini and are seeded into bounded browser memory so the first table mount does not repeat the request. Tables requiring a user-selected record or a newly entered scenario are prepared when that selection exists. Browser preparation is bounded to 32 column results/128 MB, with a 32 MB per-result limit.
Failures retain the actual completed percentage and offer Retry loading or Open available workspace; failed stages never silently report 100%. Finance preload errors are retried from their sources rather than retained as a successful preload. Account/workbook changes cancel pending startup results before cache seeding. Routine server replies and preload acknowledgements do not restart or remount a ready workspace. No AI analysis is generated and no data is sent to Gemini by startup.

AI Insights/report/graph restoration is excluded from the blocking login stages. It begins after the home/table workspace paints, shares one pending restore request if the user opens Insights early, and uses only valid saved reports without Gemini. A report restoration error cannot block the home page; the Insights tab can retry through its normal status flow. Eager embedded source preloading applies the existing source-table permission checks before sending records to the browser.

Full-screen pivot tables in the workspace and admin console include a keyboard-focusable output scroll region, visible horizontal/vertical scrollbars with reserved gutter, sticky table headers and reachable full-screen controls. The full-screen container also scrolls vertically so long pivot output, source tables and pagination remain reachable. Pivot calculations, default closed subtotals, click-through and downloads are unchanged.

### Production navigation
Click Production in the workspace sidebar to choose QC Released, Under QC, Ongoing Production, or Upcoming Production. Each choice opens only its corresponding table. The same four controls are available inside Production and existing Fiori shortcuts continue to work. Table filters, saved layouts, source permissions, calculations and matching-record details retain their existing behavior.

### Browser workspace cache restoration
After a successful full startup, Stock Planning retains one bounded prepared workspace in IndexedDB on that browser (up to 96 MiB of serialized text). A refresh, new tab, admin-page return, or later login may restore prepared financial/source tables and saved added-column values without fetching those full results again. Authentication and live source-version checks still run first. The cache key includes the current user/access scope, full authorised workbook display/upload stamp, production/plan/availability/catalogue/lead-time metadata, saved column definitions and PnL filters, and Sales/PnL source versions. An account/permission/source/layout mismatch loads fresh data. No passwords, tokens or identity used for authorization are stored in this data cache. Browser storage errors, corruption, quota limits and oversized snapshots fall back to normal startup. Only the last successfully prepared snapshot is retained; AI Insights/Graphs continue their separate background restore. Server authentication remains same-day and revocable. Browser data never bypasses login or permissions.

### Upcoming plan issue-slip requirements
The all-plan Material Availability dialog shows three tables: plan readiness, combined component demand, and batch-wise material requirements. The third table retains each saved Plan Reference, product code/description and batch, planned quantity/start date, component code/description, unit, full required quantity, readiness and verification. It uses the same server-calculated per-plan requirements as the existing combined check; shortage does not reduce the full BOM requirement. Missing/invalid BOMs remain visible as unverified rows with blank quantities. Plans without assigned SAP orders have a blank SAP Order field: saved plan IDs are not SAP order numbers. Plans with matching SAP orders leave the Upcoming list under the existing archive rule.

The third table supports existing filters, grouping, full screen and filtered CSV download. Download-authorised users can copy all filtered rows across pages, with original requirement headers and unrounded numeric values, as tab-separated text for Excel; if clipboard access is blocked, a selectable text area provides manual copying. Copy uses the same live export authorization as download. Formula-like text cells are escaped for spreadsheet pasting. This is a planning snapshot, not an issue posting, reservation, lot-selection instruction or recursively exploded SFG requirement. Existing current-stock/QI, on-order exclusion, allocation order, blocked-plan stock handling and segment permissions are unchanged. A calculation signature revision invalidates older combined checks once so all three tables are saved together and restored on later logins. Ask Assistant's existing upcoming_availability operation exposes the same third evidence table without changing plans.

### Daily two-way Product Status / Planning refresh
One coordinator in Product Status refreshes both directions at **02:30 AM Asia/Kolkata (21:00 UTC on the previous day)**: Planning workbook/production/Sales snapshots into Product Status, and current product dossiers/SKU catalogue into Stock & Planning. Source workbooks, production plans, and product master records are not edited by the connector. All server-owned commercial and enabled SFG mappings are used, independent of browser filters. Existing SKU bounds/export permissions apply.

Product Status administrators open **Auto refresh** from the sidebar or Fiori profile menu. Stock Planning administrators have an Auto refresh shortcut to the same protected menu, using the published Product Status catalogue URL; publish the catalogue once if that shortcut has no connection yet. Saving/enabling/pausing needs the current Product Status admin password. First authorization or renewal additionally checks Planning admin username/password. The stored approval contains only account identifiers, authorization versions and a hash of the source connection, never passwords. Live account/admin/export checks apply on every run; password/permission/account changes invalidate approval. The schedule defaults paused until authorized. Manual **Authorize & refresh now** needs the current Product Status admin password and works while the daily schedule is paused; it does not cancel that day's daily run.

Deploy the Product Status workflow `.github/workflows/planning-refresh.yml`. In that repository's Actions secrets, supply `DATABASE_URL` (Product Status), `ADMIN_EMAIL` (Product Status owner), and `PLANNING_DATABASE_URL` (existing Planning database). They may alternatively be supplied in the existing TOML `PORTAL_SECRETS` secret. `PRODUCT_STATUS_URL` is optional when the saved approval already contains the canonical portal URL. Do not add user/admin passwords to the worker. Product Status Streamlit already needs its normal `DATABASE_URL`, admin login secrets, and `PLANNING_DATABASE_URL`. No reverse database connection secret is required in Stock Planning. Secrets must be configured by the repository owner; changing code does not copy Streamlit secrets to GitHub.

The Actions runner can start after the target time. A first authenticated visit after 02:30 catches up a missed enabled run without polling. A durable daily success marker and leased run claim prevent duplicate/concurrent scheduled runs. Expired claims are marked interrupted, failed/partial runs remain retryable, and source/admin changes are rechecked before publishing. The two databases are separate transactions: history records completion timestamps for each direction and reports partial failures honestly. Reload refresh status to see history. Manual runs remain available for later updates. Existing email schedules are unchanged.

Missed-run catch-up executes in a background thread after live login validation, so it does not hold the cached workspace opening. Failed scheduled attempts wait five minutes before another automatic catch-up; an administrator can explicitly retry immediately. Source approval and the leased claim are revalidated before each direction is published.

### Complete Insight comparisons and editable KPI cards
Insights uses the deployed Ask AI planning knowledge, calculation definitions, cross-sheet protocol and server-computed attention evidence. Existing connected-comparison preparation uses the shared read-only calculation tools; single-view graph/KPI requests stay within their selected report view and clarify unsupported measures. Shared PS/physical availability/forecast-date distinctions, permissions, source grains and units remain authoritative. No model-generated arithmetic or arbitrary formulas execute.

Graphs now retain all supported comparison rows by default, including 300-material comparisons. The old ten-point display cap is removed. AI query limit fields do not truncate chart output; an explicit user request such as “top 10” retains that requested count. Long comparisons support native scrolling, zoom controls, full-value selection and exact source drill-through. Rendering windows of at most 300 marks allow larger results to stay responsive; previous/next and a start-position slider expose every comparison value. Zoom/window changes never recalculate or discard data. Over 100,000 comparison categories is rejected with a filter/group instruction, never silently sampled. Donuts with more than 30 categories become readable bars. Model interpretation receives a labelled bounded sample plus full-result counts/extrema; the interactive graph and supporting records keep the complete evidence.

Each section has Add KPI with AI. Cards use one validated whole-scope aggregate, with a unit/period/basis and clickable matching records. Unsafe rate/price/day sums, repeated forecast/BOM stock sums, mixed source units/currencies and mixed PnL measure totals are rejected or clarified. Cards can be deleted; custom KPI definitions and deletions persist with the existing permission-scoped report layout, survive tab switches/login and recalculate from current data on regeneration. Section filters recalculate cards/graphs without calling the model again. There are up to 20 cards per section and 100 saved custom KPI definitions per report; existing graph limits apply. Existing report sharing is unchanged: identical access scopes share their saved report/layout.

The updated cache/schema revisions invalidate old report snapshots once, while retaining saved graph/KPI definitions and deletions. Regenerate analysis once to enable full-comparison rendering for an older report. No live provider, database or deployment verification is implied by local checks.

### Table and pivot display
Every shared table provides Table View / Pivot View controls beside grouping. Table View shows individual filtered records; Pivot View shows the selected grouping and prompts for a field when none is selected. Switching preserves filters, grouping, calculations and pivot settings, and saves the display choice with the table layout. Pivot values still open matching records and pivot Excel downloads retain the displayed aggregation. Subtotals remain closed until requested. Reset to original layout restores automatic display selection.

### Automatic updates for saved Insight data
Saved production plan additions, edits, deletions and expected production outcomes trigger automatic Insight restore and numeric recalculation without a Gemini call or a manual Regenerate action. PnL assumption/source notifications also check for updated data. Unchanged authorized source tables retain their saved KPI and graph results; changed sections reuse their validated definitions and stable IDs, retain custom additions/deletions, and mint new source evidence. Updated snapshots are saved for later logins. Changed-section AI narratives and the old overall business brief are replaced by calculated notices so previous claims are not presented as current. Workbook changes (including identical reuploads with a new upload stamp) still invalidate the report.
Connected comparisons retain their validated join definitions and use the shared read-only comparison tool on changes. Older connected snapshots without a saved recipe display an unavailable notice after a dependency changes and require one regeneration to capture the recipe. Invalid/missing sources keep definitions but suppress values and source links. Access checks and optimistic saved-layout revision checks prevent overwriting concurrent edits; no automatic AI requests, permission grants or workbook/plan writes are introduced.

### Full-screen graphs and saved dashboard items
Every Insight graph has its own Full screen control, retaining zoom, scrolling, comparison navigation, style selection, value selection and source drill-through. Escape closes source records first, then the full-screen graph; Exit full screen and workspace navigation restore the normal layout.
Save KPI / Save graph pins the existing canonical full-section server-validated definition for future analysis runs. Saving needs no provider consent or Gemini call and never accepts browser-supplied queries or calculated values. Graph style is validated and saved with the definition. Saved cards/graphs are recalculated against current authorized sources on rerun, while AI may add other comparisons. Saved items take priority within existing per-view limits; repeated saves are idempotent. Custom additions remain automatically saved. Deleted graphs and KPIs are removed from saved definitions and retained in deletion history so equivalent items do not return on subsequent runs.
Saving from a filtered screen preserves the canonical full-section calculation. Connected saved views retain their join recipe and can be rebuilt by the shared read-only comparison tool even when a later AI run proposes different comparisons; missing/ambiguous source mappings produce a notice and retain definitions. Existing manual-data automatic updates, workbook invalidation and same-access-scope sharing remain in force. No source workbook, production plan, access rights or email is changed.

### Insight cache loading status
The Insights & Graphs tab displays its saved-cache restore status and percentage independently from AI analysis progress. The percentage counts completed restore stages: checking/retrieving the saved response, restoring the dashboard, and completing its browser display. It is not an estimated timer or byte-transfer measurement; the display reaches 100% only after the report is committed and has had a browser paint opportunity. Completed restores retain a cache badge with current view/KPI/graph counts. No saved report produces an explicit cache-miss message rather than 100%; interrupted analysis sections are identified separately from a completed report.
A failed restore displays Retry loading saved report, retains any previously visible dashboard and does not claim completion. Restoring cache starts no AI generation, grants no access and adds no restore RPC on tab switches. Existing authenticated preloading and source/access/version checks remain in force; late responses and display callbacks are cancelled on departure or a newer restore. New analysis shows its existing separate progress, and the cache-save label is shown only when the server confirms a saved cache generation. Editing/generation controls wait until cache restoration completes.

The cache-loading indicator also shows elapsed time and an approximate remaining time based on the median of up to five successful loads on the same browser, scoped by authenticated user/access/workbook and preloaded/remote/refresh path. Only numeric durations are retained locally; no report data or credentials are stored for timing. First-time loads display Calculating estimate until usable history exists. If a load exceeds the estimate, the indicator reports that it is taking longer rather than falsely displaying zero remaining. Failures and cancelled loads do not train the estimate. Timing never advances the percentage, and storage restrictions fall back to in-memory timing without blocking the report.

AI generation also displays elapsed time and an approximate remaining time, using separate successful-run history for new and resumed analysis. Its elapsed clock pauses with a paused analysis; resuming starts timing the resumed attempt. These estimates do not trigger AI or alter the server's analysis percentage. Successful completed attempts supply timing samples; failed/paused attempts do not.

### Fast saved-Insight edits and filters
Save/Delete now use compact, commit-confirmed layout edits instead of decoding the workbook, recompressing the full report, re-registering every graph and returning a new report session. The canonical report token and existing evidence remain stable. Small acknowledgements update only the matching UI item; success/error feedback is visible inside a full-screen graph. Delete retries are idempotent, failed transactions change neither the durable layout nor the active report, and concurrent regeneration cannot overwrite a newer report's layout. Saved definitions and deletion history are overlaid on immutable report snapshots during restore and before later updates. Older clients retain the full-response path.
Filter application and filter-value searches read registered report sources before any workbook catalogue construction. Only the filtered section is recalculated; unrelated graph rendering is memoized while event handlers remain current. Source/permission/workbook revision checks remain live and use metadata; production change fingerprints are conservative opaque hashes, not exposed plan identifiers. Registering filtered evidence checks the administrator role once per section. Successful Insight replies may reuse the prepared workspace only when authenticated session, permissions, segments and workbook metadata still match; failures, cache misses and mismatches use normal preparation. No source workbook or production plan is written by these changes.

### Calendar-month sales requests
Ask AI and manual/automatic Insight graphs now support a validated date_group={column: exact date header, grain: month, alias: Month} query dimension. Explicit requests such as Month against Invoice value or monthly sales total invoices by calendar month rather than plotting each invoice date. Shared server query arithmetic calculates all monthly totals; the AI selects definitions and explains results. Jun 2026 / Jul 2026 labels sort chronologically and retain their calendar years. Invoice/billing dates are preferred when unambiguous; an explicitly named date basis is respected. Multiple equally plausible date bases require clarification. Month-only fields need an explicit calendar Year field; fiscal-year-only values do not establish a calendar year. Explicit daily/date-wise requests retain their requested grain.
Recorded invoice signs, existing filters, permissions and source rows are preserved. Missing or invalid dates remain in an Unknown month category with a scoped note; they are not silently dropped or assigned an invented year. Source drill-through and Excel evidence use the same month dimension and retain original dates. Saved monthly query definitions survive reruns and recalculate against current authorized data. Existing saved date-wise definitions remain unchanged; replace/regenerate an older date-wise graph to use the new monthly request. No model training, source workbook writes, net-sales sign adjustment, calendar/fiscal inference, unit/currency conversion or new table access is introduced.

Insights dashboard conditions support numeric comparisons/inclusive ranges and calendar-date on/before/after/between, blank and invalid-date conditions. Conditions intersect checkbox selections and update only on Apply; Reset restores the full section. The full-screen view shares applied conditions.
Current-month sales KPIs can show the previous calendar month and percentage growth. Both sums use the same authorized sales source, units/currency and dashboard filters. Growth is (current minus previous) / previous × 100; missing months and zero/negative prior baselines show unavailable. Current and previous records have separate drilldowns. Saving stores the relative monthly definition, so cached restoration recalculates at the next calendar-month boundary without Gemini.

Daily-session reconnect correction (revision 7): the opaque daily token is bound to the browser user-agent fingerprint, not the connection IP. Streamlit reverse-proxy/mobile connection IP changes must not request the password again. The random token, live account/session version, explicit sign-out, password/access revocation and fixed midnight IST expiry remain required. Existing IP-bound tokens are migrated when their original connection fingerprint is still valid; older tokens whose original IP already changed require one sign-in to issue the corrected token. Browser storage acknowledgement and cookie/local-storage fallback remain unchanged.

The opt-in `session_check=1` diagnostic view reports the deployed session-helper revision, token-presence booleans, storage-write acknowledgement and validation outcome. It exposes no password, opaque token, hash, IP, user-agent or account identifier and does not grant access or bypass validation. It is intended for diagnosing a reproduced refresh/login failure, not proof that restoration succeeded.

Imported account session versions are compared as validated numeric revisions, so a text account value such as "1" matches the integer 1 returned by the remembered-session table. This corrects password-login success followed by refresh rejection on migrated schemas without changing account data, passwords, permissions, expiry or revocation. Invalid/nonpositive/fractional revisions cannot authorize. The account resource revision is advanced so a warm server reconstructs cached Store instances with the corrected validation.

Live-verified restore failure: Streamlit can retain an account Store resource while evicting and reimporting its Python module. Constructing a restored Actor through that new module fails the cached Store's strict identity-class check despite a valid account, token, version and session row. Restoration and scheduled server identities now use the Store-owned actor factory (with a compatible old-Store constructor fallback), sharing the same identity type as its login and require methods. Strict identity checks and SQL authorization remain enforced; no data or passwords are changed.

Prepared data survives calendar-day changes, browser refreshes and later logins while its source/access/definition keys remain unchanged. The server retains bounded full display/model snapshots independently of the Streamlit session. Browser cache writes finish before startup is marked ready. Revalidation uses small live metadata checks; matching parts are reused independently. A Primary/Secondary Sales or PnL change requests only missing/changed financial parts; unchanged model tables and same-table/calculated-column results remain cached. Lookup columns invalidate according to saved source identity, with conservative invalidation for ambiguous legacy dependencies. Workbook/production/access/layout edits refresh affected views/results; PnL metadata includes its Sales dependencies. Source changes are checked before/after preparation. There is no midnight data-cache expiry; the separate daily login security policy remains unchanged. Blocked/evicted/oversized storage or cold server resources can require preparation again. Cache data never authorizes requests.

Fresh browser frames receive an authenticated content fingerprint before display rows. If it matches a prepared browser snapshot in the same access scope, the bridge restores display rows locally instead of requesting the full workspace bootstrap. Missing/changed/corrupt snapshots request the live permitted bootstrap. Changed-data replies to an existing browser still deliver updated data; this cache never restores identity or skips server authorization.

Insights & Graphs persist their display data in a bounded, per-account/access-scope browser cache after a durable report loads. Refreshes and later-day logins validate small report/source/layout stamps and reuse unchanged graphs, KPI values, findings and saved/deleted-item state without preparing source tables or calling Gemini. Fresh opaque lazy references rebind to the server-owned saved report only on drill-through/export/filter/edit; old session evidence tokens and trusted queries are not persisted in the browser. Workbook replacement now re-evaluates saved definitions against current authorized sources, updating affected sections and hiding stale values when sources/fields disappear. Unchanged sections can be delivered as stamp-matched patches. Manual reruns regenerate AI; source changes recalculate saved numeric definitions without AI. Monthly relative KPI periods remain relevant invalidators, with no whole-dashboard daily expiry. Committed graph/KPI saves, additions and deletions update the browser display cache; temporary filters or unsaved styles do not overwrite the durable baseline. Account/access changes, cache corruption/quota limits and changed definitions use validated server fallbacks.

Saved dashboard opening: restore the complete cached report, but initially display the first nonempty planning view, matching new analysis behavior. Other section tabs and All views remain available. This avoids mounting every section and its graphs simultaneously on login or refresh. No report data or comparisons are removed.

Cold saved report display also defers registering raw evidence for all graph/KPI items. It restores the display report and binds lazy server-owned references; a later evidence, filter or edit request materializes and revalidates source evidence. Live source/access validation remains mandatory before display or evidence use.

Insights Gemini consent: users may grant once for the current page or select Always allow for Insights analysis, graphs and KPIs. This is a separate account preference (ai-insights-sharing), with no inheritance from the narrower Ask Assistant consent. Users can revoke either checkbox to stop further requests; selecting consent never starts analysis. Saved consent restores with account preferences after login. Unchanged chart graphics are memoized so consent changes do not redraw their marks. Cached report metadata supplies workbook readiness without loading source tables, enabling regeneration after cache validation.

Run analysis continuity: routine same-workbook cache, source-status and manual-data refresh signals do not load an older saved report over a running or paused job. A real workbook-version change still cancels stale results, and the server revalidates access and all business-source revisions at each generation phase. Temporary transport failures retry the identical request/job/step up to twice with bounded backoff, then retain partial results for explicit Resume. Validation/authentication/provider errors are not automatically retried. No new analysis is started by a background refresh.

### Workspace navigation and Floor Level
Production contains QC Released, Under QC, Ongoing Production, Upcoming Production and Transfer Details (the existing transfer worksheet). Forecast contains Forecast Planning, Purchasing and Lead time. Floor Level contains Issue Slip and Order Requirement (the original PS ordering view, with its existing calculations). Child views retain their existing tab permissions; a parent is shown only when at least one child is permitted.
Issue Slip uses Production access and the existing server material-availability check for all permitted upcoming plans. It restores the current saved batch-wise, plan-wise issue requirement table when available; otherwise it calculates using the same operation as the third table in Upcoming Production material availability. Filters, paging, fullscreen, copy for Excel and authorized downloads use the existing issue table. Quantities are full BOM requirements, not physical issues or stock deductions; SAP Order remains blank until assigned. Refresh revalidates plans; no business arithmetic is duplicated in the browser.
All administrator tools (users, workbook, settings, email, history and auto-refresh) open from the user-name profile menu. Sidebar and Fiori navigation expose the same groups, and Issue Slip inherits Production rights without adding a new server permission.

AI-assisted column values and source-record clicks match refreshed/copied display rows against the complete authorized source row when object references differ. Material code alone and display position are never used as a fallback key. Existing table storage keys, saved definitions, source-version invalidation, permissions and server-owned calculations are unchanged.

Issue Slip keeps a bounded persistent browser display cache across logins and days. Each restore validates its stamp against current Production access, workbook and upcoming-plan revisions. An unchanged stamp transfers no production report or issue rows and performs no material recalculation. Changed sources return only the refreshed third table via existing authorized availability calculations. The page labels cached restores; Refresh issue slips bypasses the browser cache. Storage failure falls back to the server. No cached entry authorizes a login or download.

Issue Slip is prepared during workspace startup for users with Production access, including the fast browser-cache restoration path. Opening the prepared page or returning to it makes no additional issue-data request. Source/account changes invalidate the prepared snapshot, while explicit Refresh updates current upcoming-plan entries. The screen uses a concise heading, cache/check status, plan/component/row counts, and a scrollable table with the existing saved layout and full-row copy/export controls.

Issue Slip transfer control: unchanged validation reads only current workbook version/upload time and upcoming-plan ID/revision/update-time metadata, plus current access and calculation revisions. It does not load the production payload or material tables. Explicit Refresh bypasses prepared memory but still sends the saved stamp, so unchanged rows are not retransferred. Tab switching uses already prepared memory without a request. Source changes return only the refreshed issue table. No background issue polling is added.

Additional transfer controls: Production refresh, Order Requirement material reload and PnL report/filter results use bounded account-scoped persistent display caches. Refresh validates live permissions and source metadata; unchanged responses transfer no table rows and skip full source/report calculation. PnL keys include financial year, basis, segments, products and material type, with master/finance/sales/catalogue versions. Production no longer polls full reports every minute; Refresh shared plans loads current edits. Cross-tab Sales updates pass known versions and retain unchanged rows. Stock, BOM, Transfers, Forecast and Lead Time continue using the existing authenticated workspace snapshot; startup already reuses unchanged Sales/PnL/model/column portions. No business calculations or export permissions are changed.

Unchanged Sales validation checks the master workbook version before constructing a BOM index, so a matching saved sales version avoids reading either sales rows or the master payload. Changed BOM versions still rebuild and validate eligible sales rows through the existing BOM mapping.

Unique upcoming-batch KPI requests use the existing full-scope distinct_count aggregate over the exact saved Batch column, excluding null/empty/whitespace-only batches. Repeated batch identifiers count once, not once per product/order/plan. Leading-zero identifiers remain text. Simple unfiltered requests on the current Upcoming Production view are computed directly without Gemini. Filtered, ambiguous and other-view questions still use the validated planner. KPI display fields resolve the query engine’s declared aliases and normalized output names; unrelated or conflicting measures remain rejected. Existing source evidence, user scope, persistence and export permissions are unchanged.

## Insights report layout and retained performance

Insights & Graphs uses the earlier section report layout and cached-views component route. Executive overview and template controls are removed. KPI and graph saves/deletions still update the screen immediately, use compact background acknowledgements with a bounded retry, and restore the item if confirmation fails. Saved/deleted item definitions, workbook caches, evidence and unrelated portal workflows are retained.

### Self-contained component startup

Stock Planning serves its UI JavaScript and styles inside the component HTML, without separate startup asset or dynamic-module downloads. The early Streamlit handshake buffers only parent render events and hands the latest event to the authenticated bridge once it is ready. Normal RPCs, authentication, report caching and fast KPI/graph edits continue through that bridge. Startup errors expose a retry control; the app does not automatically reload the page. Previously published assets are retained for open tabs. This addresses asset-load dependency failures; deployment availability and network failures still require live diagnosis.

Workspace component events use the stable `exact_website_ui` key consistently for rendering, bootstrap/RPC dispatch, account navigation, activity and logout. Changing only the rendered widget key leaves browser requests unread and can stall startup at 0%. The self-contained startup file and saved caches remain in use.

Notification setup obtains its transaction advisory lock before creating notification tables/indexes. Login-triggered dispatch skips an already-busy notification worker, with short transaction-local lock and statement timeouts; unfinished due batches remain eligible for a later visit or scheduled worker. Concurrent visits and RPC reruns share a 55-second process throttle. Recipient authorization, idempotent delivery claims and uncertain-send handling remain unchanged.

A server-validated saved login opens the portal without waiting for the browser storage/activity probe. That probe remains mounted and updates activity in its fragment without rebuilding an already authenticated workspace. Users without a validated session still complete browser-token validation or normal sign-in; pending cookie/token writes still require acknowledgement. This avoids a redundant startup wait without changing expiry, access checks or cached-data freshness.

### Workspace component route compatibility

Register both `stock_planning_web_ui_cached_views_v56` and `stock_planning_web_ui_session_recovery_v57` against the same frontend directory. v57 remains active while older v56 iframe requests can resolve during rollout. Keep the `exact_website_ui` widget key consistent across rendering, request dispatch, navigation and logout. Preserve the existing self-contained startup page and all previously published frontend assets. This route compatibility change does not invalidate workbook/report caches or change production, PnL, insight calculations or permissions.


### Automatic workspace entry and completed report rendering

After normal sign-in or restoration of an authenticated browser session, open the full workspace automatically. There is no Open full workspace landing gate, floating Home / Recovery button or Safe Home recovery route; older safe bookmarks open the normal authenticated workspace.

Assemble the self-contained dashboard HTML only after Vite finalizes lazy-load preload markers. Reject unresolved runtime markers during builds. This prevents lazy financial views and Insights & Graphs from failing after loading reaches 100%. A render error shows an inline retry message instead of clearing the root. Preserve existing workbook/report caches, saved/deleted items, permissions and calculations.


### Open-order demand and Floor Level production requirements

Administrators open **Uploads** from their profile. This page groups master workbook (including stock, BOM, forecast, production and lead time), open sales orders, Primary Sales, Secondary Sales, PnL master and salary uploads. Each source displays its filename and last upload date/time in IST. Existing source validators and replacement/version-conflict checks remain in force. Open sales orders require exactly one visible worksheet with Material, Pending Qty, Remarks and Sales unit in row 1. Preserve all source columns, including uniquely labelled duplicate Description headers, and reject duplicate sales-document/item/material rows.

Stock Overview displays **Pending Sales Quantity** immediately before Current FG Stock. It sums Pending Qty for Credit Hold_No Stock and Release_No Stock plus positive permitted forecast pending quantity by exact normalized material code and compatible unit. Credit Hold_Available and Release_Pricing Issue do not contribute. Keep the original stock worksheet schema and indices intact: insert this field at the display boundary, shared with custom-column startup preparation. A missing report or multiple sales units for one SKU displays a blank instead of an invented zero.

Floor Level → **New Production Batch Required** shows positive quantity requirements, product code, description, unit and reason. Apply current FG stock once per product/unit to eligible sales demand, giving released orders priority before credit-hold orders. Missing/ambiguous FG stock or a sales/workbook base-unit mismatch blocks that sales shortage and appears in review warnings; never invent pack conversions. Quantities represent production requirements, not a number of batches.

Use the established forecast summary (total forecast minus total transfer minus current stock once per material). The latest requested behavior combines positive sales shortages and forecast pending in one product/unit row. Do not subtract FG stock from forecast pending again. Show the contributing categories in Suggestions and the detailed pending/required breakup on click. Retain the existing filter, pivot, fullscreen and Excel controls. The SKU review includes all visible eligible order materials, unit/stock checks and BOM-match status, including codes needing future BOM setup.

Click a pending-sales value or requirement row to inspect matching no-stock orders, forecast rows, stock records and BOM SKU lines. Detail pages contain 200 rows and provide a full matching Excel export when download access is granted. Live authorization, inherited Stock Overview access, Forecast/BOM menu permissions, segment scoping and source-stamp validation apply to reads and exports. Shared multi-segment totals are hidden from users who cannot see the full contributing scope.

Store the open-order report in durable database storage, not in the repository. Persist calculated demand snapshots keyed by master-workbook version, open-order version/upload metadata, calculation revision and access scope. Reuse them across logins/days until relevant inputs or permissions change. Normal cache checks transfer only metadata. Include the demand stamp in bootstrap/browser-cache identifiers so a changed source cannot restore stale pending values. Keep old published frontend assets during rollout.

Ask Assistant exposes read-only `pending_batch_requirements` through the shared calculation module; it returns the same tables, notes and warnings. Repository knowledge includes the demand module and display helpers, with no uploaded business records or credentials.


### Add demand rows to Upcoming Production

Floor Level → New Production Batch Required includes per-row **Add to upcoming plan** for users with Production menu access and edit_upcoming permission. Open an editable form with the requirement’s exact material, quantity, segment and planning reason. Users enter the batch and dates and may change quantity, material, segment or reason before saving. The selected workbook material supplies the canonical description/unit. A unit mismatch requires explicit review; no automatic conversion occurs. Saving uses the existing production_save authorization, master-version, positive-quantity/date, batch, material and segment validation, shared plan history and notifications. Include the demand stamp so changed demand cannot silently create an outdated plan. Reuse a stable client-generated plan ID for retries; duplicate submissions cannot create a second plan.

Planning reason is stored with the Upcoming plan, shown with its row actions, and editable from the normal Production form. Preserve it when an older client edits a plan without submitting that field. Keep the established nine-column Upcoming row schema and final Segment position unchanged.

For every requirement, display exact-SKU totals for **Ongoing Expected FG Qty**, **Under QC Order Qty** and **Upcoming Planned Qty**. Under QC order quantity is not the same as its confirmed quantity; both remain visible in the batch-detail table. An unknown matching quantity stays blank, and no matched batches means zero. Never sum these categories together or automatically deduct them from demand. Their purpose is to let the user review existing supply and decide the new plan quantity. Clicking a quantity or View batches opens all matching permitted batch rows with their dates and quantity fields.

Use the prepared authorized Production snapshot when opening Floor Level, with an explicit metadata-validated batch refresh for newer shared edits. On save, apply the returned Production report immediately in Floor Level and the parent workspace. Do not reload the full workbook or regenerate demand/Insights for this action.


### Combined demand and website-style Uploads

The latest user instruction supersedes the earlier separate-demand choice. New Production Batch Required has one main table per product/unit, not three category tables. Quantity is the sum of positive credit-release sales shortage, positive credit-hold sales shortage and positive forecast pending. Suggestions names each contributing category and its quantity. Existing batch quantities and Add to upcoming plan remain available on the combined row. Stock Overview Pending Sales Quantity now includes gross eligible sales Pending Qty plus forecast pending, before FG stock is applied to the sales portion. Do not mix incompatible units or include forecast outside the user's permitted menu/segment scope.

Clicking a total opens Quantity breakup first, with Category, Unit, Pending Quantity, Production Required and FG Stock Applied to Sales. Clicking a category row opens its matching orders or forecast records; category buttons, stock/BOM evidence, pagination and full matching Excel exports remain available. A calculation-revision bump invalidates old separated snapshots and the demand stamp prevents stale browser restoration.

Uploads is a React workspace inside the existing website sidebar/header/theme and panel layout. Admin profile → Uploads navigates locally, with no native Streamlit upload page or full-page handoff. Include master workbook, open orders, Primary Sales, Secondary Sales, PnL master and salary controls with IST timestamps, sales worksheet/header/segment preview and PnL period inputs. Reuse existing validated upload APIs and the website master-workbook comparison modal. The admin-only uploads_status API returns source metadata only, with optional source-version fingerprints after saving. Refresh the affected caches after a saved upload, not while previewing columns. Legacy native upload routes return to the workspace.


### Startup-ready batch cache and separate Floor Level rights

Seed the conditional Production/batch cache from the already authorized startup report before showing the workspace. Startup sends a small productionStamp even when table data restores from the browser snapshot. The stamp uses the same workbook revision, scoped shared-plan revisions, availability revision, calculation revision and live access scope as production_status validation. Seeding requires no extra row request or full browser-cache invalidation. Opening Floor Level and batch details uses these prepared rows. First and later explicit checks send a known stamp and return metadata only when unchanged; browser storage persists the display across refreshes, logins and day changes. Workbook uploads, shared plan additions/edits/deletions, availability changes and permission changes invalidate the appropriate result. Cached identity never authorizes access. Retain the existing SQL transfer cache for shared-plan payloads and the normal source-checked update path.

Manage rights now lists independent **Open Floor Level · Issue Slip** (menu_12) and **Open Floor Level · New Production Batch Required** (menu_13) switches. Existing accounts retain their prior inherited availability unless a switch is disabled. Issue Slip additionally requires Production access; New Production Batch Required additionally requires Stock Overview access. Uploads remains admin-only. Upcoming-plan editing still requires the existing Production/edit_upcoming rights, and creating a plan from a demand row also checks menu_13. Disabled options disappear from sidebar/Fiori navigation and their APIs reject requests before returning cached results. The Stock Overview pending column continues to follow Stock Overview rights. Do not preload Issue Slip when its own switch is disabled. Invalidate the admin console's cached permission catalog so both controls appear immediately after deployment.


Forecast Purchasing live quantities: deduct transfers and the combined released/under-QC FG worksheet stock once per product across chronological forecast months, clamping uncovered FG demand at zero. Respect dated ongoing FG/SFG production and QC double-count protection. Expand uncovered FG through the standard BOM, after SFG coverage, for Total Required Quantity. Need to Order Quantity is max(Total Required Quantity - Current Stock - Still To be Deliver Quantity, 0). Valid linked BOM rows replace saved Excel totals; missing/ambiguous BOM links retain saved values with review notices. Suggested dates use the same dated requirements and component coverage; zero need has no suggested date. Average Lead Time remains the numeric non-negative material/batch mean PO-to-inward interval; suggested dates subtract its ceiling, never QC or consumption time. Source workbook rows remain unchanged.

Stock Overview appends Expected Meril India Stock and Last uploaded Secondary sales data. Per FG code, sum Billed Qty from the current Primary upload minus sum Billed Qty from the current Secondary upload, retaining signed quantities. Exclude Energy Device; show its estimate/date blank. The date is the Secondary upload timestamp in IST, not a billing date. Missing uploads, required columns, invalid quantities or Sales access leave the estimate unavailable. Authorized segment scope applies before aggregation; absent SKUs in a valid upload contribute zero. Values refresh on workspace reload using current sales versions, without changing source uploads.

Click Expected Meril India Stock in Stock Overview to verify exact FG-code matching Primary and Secondary Sales tables, full billed-quantity totals, their difference and current upload timestamps. Evidence uses current live Sales and Stock Overview rights and permitted segments; Energy Device is excluded. Both sources page independently at 200 records. Changed source totals are flagged against the clicked value; refresh Overview to update it. This is read-only and does not change uploads.

New Production Batch Required material readiness: Actions includes a cached BOM status beside View batches and Add to upcoming plan. Ready means direct BOM component requirements are covered by Current Stock (including under-QC stock once). Material Shortage means current stock is insufficient but quantities still to be delivered cover the gap. Material Need to Be Ordered means a positive shortage remains after both current stock and expected deliveries. Unknown/ambiguous BOMs, stock, units or required on-order data show Cannot verify, never a false Ready. Required component quantity uses the shared physical availability calculation (FG quantity / BOM base quantity × component consumption, grouped per component/unit, de-duplicating identified BOM items); this does not change PS ordering or forecast purchasing rules. Prefer raw Order List delivery quantities; identified duplicate PO/item lines count once and conflicting duplicates remain unknown. Without a raw delivery schema, use the minimum joined BOM on-order value per component, never sum repeated joins. Each FG is checked independently against its direct components; stock is not reserved between requirements and SFG BOMs/future production are not expanded.

Click the status for the cached component table (required, stock including QC, QC subset when supplied, to-be-delivered and remaining need to order). The status filter changes display only. Existing production/segment rights apply. Store all statuses/details in the versioned durable demand cache; opening, filtering, batch refresh and saving plans do not recalculate these checks. Workbook content/upload replacement invalidates the snapshot. Replacing demand sources or changing access also invalidates the matching cached demand result so required quantities/permissions cannot become stale; stock and delivery inputs still come exclusively from the master workbook. No timers or new polling are added.

Source file date labels: Uploads and the sections using the sources display Uploaded on (date/time in IST) separately from Data up to. Data up to is the latest usable observed billing/posting/document/creation date in the uploaded records, with its source field shown. Master-workbook dates exclude Calendar, forecast horizons, planned production dates and validity/deadline fields. The master file reference appears across workbook sections, with Primary/Secondary file references beside dependent Overview/Stock/Insights views; Sales, New Production Batch Required, PnL and verification tables show their own source references. PnL Data up to retains month precision when only production months are supplied; a selected statement end is not substituted for a file-content date. Annual salary CTC references and undated files show Data up to: Not available in file, rather than using employee join/leave dates or upload time. These are observed source dates, not a promise that every metric is complete through that date.

Persist small source-date summaries by content version, using permission-scoped view keys for Sales. Unchanged metadata reads restore summaries without payload rescans. Workbook replacement invalidates prepared payloads; same-content Sales reuploads still refresh Uploaded on through timestamp-aware view/preload versions while keeping the content date unchanged. Source access and existing filters/calculations remain enforced. No source records are modified and no new polling is added.
