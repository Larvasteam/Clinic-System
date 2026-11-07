# Clinic System: roadmap

Status key: DONE = built and tested. NEXT = the next thing to do. LATER = planned.

## Phase 0. Requirements: DONE
- Requirements sheet turned into rules: patient details, contraceptive restriction, stock tracking and expiry,
  colour-coded levels, consultation fees kept separate from medicine sales, client history, daily to yearly
  reports, rank-based access, EcoCash / cash / bank payments.
- Stack chosen: Python, Django, SQLite in development, PostgreSQL in production.

## Phase 1. Foundation: DONE
- Project and five apps (accounts, patients, pharmacy, billing, reports).
- Settings read from environment variables. No secrets in the code.
- Login and logout, 8-hour sessions, minimum 10-character passwords.
- Roles: Admin, Pharmacist, Receptionist (`setup_roles`).

## Phase 2. Patients: DONE
- Register, search and edit patients (name, surname, date of birth, gender, phone). Age is worked out from the date of birth.
- Client history page: visits, purchases and totals.

## Phase 3. Medicines and stock: DONE
- Medicines with price, low and high stock levels, expiry date and a contraceptive flag.
- Stock changes only through stock movements, with an audit trail (who, when, why).
- Green, yellow and red levels, Stock Management page with chart, Expiry Alerts, CSV export.

## Phase 4. Billing: DONE
- New Visit (consultation fee) and New Sale (several medicines in one sale), with a printable receipt.
- Rules: contraceptive restriction, 0.50 USD minimum payment, no overselling, no expired sales, EcoCash and bank references.

## Phase 5. Dashboard and reports: DONE
- Dashboard: stock overview, expiring medicines, money earned (admins only).
- Daily, weekly, monthly, quarterly and yearly sheets with totals by payment method, medicines sold, consultations and sales. Print or save as PDF.
- Search across medicines and patients.

## Phase 5b. Two currencies (USD and ZiG): DONE
- Exchange rate table, fetched from the RBZ official rate (AllRatesToday) with a market-rate fallback, or set by hand.
- Each visit and sale records the currency paid in and locks the rate used.
- USD balance, ZiG balance and a combined USD-value total on the dashboard, report sheets, patient history and receipts.
- Rate chip on every page, stale-rate warning, typing-mistake and sudden-jump protection.

## Phase 6. Look and feel: DONE
- LSU branding, SIS red and slate colours, sidebar layout, amounts shown as `0.00 USD`, mobile-friendly menu.

## Phase 7. Quality: DONE
- 79 automated tests, including every business rule, every role's access and the currency logic.
- README with setup, roles, rules and data model.

## Phase 8. Go live: NEXT
1. Make the GitHub repository private. Make sure `.env` and `db.sqlite3` are not in it.
2. Pick a host: Render (simplest from GitHub) or PythonAnywhere (free tier, no card).
3. Create a PostgreSQL database and set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`,
   `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` on the host.
4. Run `migrate`, `setup_roles` and `createsuperuser` on the server.
5. Confirm HTTPS works, then raise `SECURE_HSTS_SECONDS` to one year.
6. Schedule `python manage.py update_rate` every weekday morning (a cron job on the host) and set `ALLRATES_API_KEY`.
6b. Set up automatic database backups and test a restore once.
7. Create the real staff accounts, change every demo password, and replace the estimated prices with the clinic's price list.

## Phase 9. Hardening: LATER
- Audit log of who changed what (medicine prices, patient edits).
- Login lockout after repeated failures, and a password-change page inside the app.
- Void or refund a sale (as a reversing record, never a deletion).
- Cash-drawer reconciliation per currency (opening and closing balance for USD and ZiG).
- Decide how change is given when a payment is in one currency and change is returned in another.
- Confirm the contraceptive age limit with the clinic, and add a minimum age if required.

## Phase 10. Enhancements: LATER
- Medicine categories and manufacturers.
- Stock batches with a separate expiry date for each delivery.
- Suppliers and purchase orders, with a "reorder now" list.
- Appointments and reminders by SMS or WhatsApp.
- PDF receipts and CSV or PDF export of the report sheets.
- EcoCash payment confirmation through a payment API.
- Several clinic branches.

## Dissertation track (in parallel)
| Chapter | What to use from the system |
|---|---|
| 1. Introduction | Written. Matches the problem, objectives and scope above. |
| 2. Literature and frameworks | Clinic management systems, inventory control, Django and role-based access control. |
| 3. Methodology | Iterative development, the requirements in Phase 0, the tools used. |
| 4. Analysis and design | Data model diagram in the README, role table, business rules, screen layouts. |
| 5. Implementation and testing | Screenshots of each page, the 79 automated tests and their results, rule-by-rule test cases. |
| 6. Conclusions | What was achieved against each objective, limitations, and Phases 9 and 10 as future work. |
