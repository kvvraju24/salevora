# Verification — 27 October 2026

The user flow is: React dashboard control → FastAPI endpoint → Rossmann CSV/model artifacts → JSON or CSV response → interactive visualization.

| Boundary | Result | Evidence |
| --- | --- | --- |
| Data → API | Passed | 17 pytest integration checks |
| API → dashboard | Passed | All six pages rendered, no page errors in browser traversal |
| Forecast controls | Passed | Store 1, Ridge, 14 days, cumulative view, CSV download |
| CSV export | Passed | Export filename, row count, dates, nonnegative predictions and totals reconciled to API |
| History and search | Passed | Store and 28-day filters, Store 1115 search, empty results state |
| Mobile | Passed | 390px viewport, navigation, explanation page, dialog, no document overflow |
| Production build | Passed | TypeScript compilation and Vite bundle |
| Local startup | Passed | `./start.sh` rebuilt and served UI + API at port 8000; health endpoint returned ready |
| Visual QA | Passed | Desktop overview, forecasts, model comparison, SHAP and quality pages; mobile overview |

The four browser test scenarios passed (three in the initial completed run, forecast after making its horizon selector label explicit). Source-CSV totals, customer counts, closed-day behavior, model metric arithmetic, SHAP additivity, and target-feature isolation were independently checked by the backend tests.

A visual check revealed that Recharts' daily-to-cumulative interpolation briefly displays the previous shape against the new axis. Forecast series interpolation was disabled so the new curve appears immediately; the completed cumulative curve was then verified in the Codex browser against the production build. Page-entry transitions remain enabled and respect reduced-motion preferences.

Screenshots in this folder document the locally rendered dashboard. The server is bound to the loopback interface; the project has not been published externally. Screenshots show a 2015 historical dataset, not current trading activity.
