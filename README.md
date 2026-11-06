# Little Marvels · lil.Marvels

Arabic / English shop for children's books and toys, with OMR pricing and a password-protected inventory dashboard. Python 3.12+, SQLite and Pillow; Gunicorn serves production. No external services are required for local development.

## Run

```bash
cd /workspace/Ahmed_2024
python3 -m pip install -r requirements.txt
bash start.sh
```

The server listens locally on port 8000 by default. `HOST`, `PORT`, `DATA_DIR`, and `ADMIN_PASSWORD` are supported overrides. `start.sh` uses an existing `ADMIN_PASSWORD`, or creates a random password in `/workspace/ahmed-business-data/admin-password` with owner-only permissions. The shop owner can retrieve this local password in their private terminal; do not commit it or share it in chat. Database and generated credentials live outside the checkout. Live processes must be restarted after environment restoration.

Use the existing checkout; tasks are already isolated and don't need Git worktrees.

Age categories: Manage shop → Inventory → Edit → Age ranges. Tick any combination of 0–1, 1–2, 2–3, 3–5 and 5–8 years, then Save product. A product appears under each selected storefront age filter. Leave all unchecked for age not specified. Existing assignments are preserved: legacy 0–2 maps to 0–1 and 1–2; legacy 6–8 maps to 5–8. Multiple assignments remain selectable.

## Manage the shop

Choose Manage shop / إدارة المتجر and sign in. Add Arabic and optional English product names/descriptions, prices, cost, stock and up to ten photos. Upload JPG/PNG/WebP files from the device or add HTTPS image links. Choose a main photo, remove unwanted photos and save the product. File limits are 8 MB/photo, 20 MB/upload batch and 20 megapixels/photo. Hide keeps a product in inventory while removing it from the public catalog. Unhide makes it visible again; photos, options, quantities and order history remain intact. Existing sample products are illustrative; replace all sample products, costs, stock, descriptions, and safety claims before accepting real orders. Symbols are placeholders until real product photographs are added.

Payment settings lets the owner edit the shop WhatsApp number (with country code), the transfer phone number, bank name, account holder, account number, IBAN and SWIFT code. Phone transfer is shown first with a copy button; bank details are in an expandable alternative. The customer preview updates after saving. Current receiving details are saved in the persistent SQLite database, not hardcoded in the application. These are public receiving-account details, never bank credentials. Checkout stays closed until a transfer phone number, account number or IBAN is configured. Customers submit an unpaid order, then choose Continue payment on WhatsApp. This opens the shop chat with a prepared message containing the order reference, customer name, product subtotal, phone-transfer number first, and all bank details. The customer must tap Send. The message includes the ordered product names, quantities and prices. Clicking Continue payment on WhatsApp records the first click time using an order-specific token; this is not proof the message was sent or delivered. All checkout orders remain visible in Customer orders, with filters for WhatsApp clicks, pending, processed and cancelled orders. Nothing is automatically sent to the customer or merchant by the website. No WhatsApp Business API is connected. The shop confirms delivery and the final amount in the chat; the customer transfers using the order reference and shares the receipt there. A missing WhatsApp number shows an Instagram-contact fallback. The editable WhatsApp number is separate from the phone-transfer number. Changing one does not change the other. After verifying receipt and processing the order, choose Paid & processed and confirm payment verification. Transfer verified is also available as an intermediate state. Only Paid & processed orders count as sales. Cancelling removes them from sales/profit and restores stock once. No bank API, card payment, automatic confirmation, email/SMS notification, or automatic refund is connected. Cancellation restores inventory once; refunds must be handled separately.

Supplier purchase orders can remain awaiting delivery. Receiving an order increases stock exactly once and recalculates the weighted average unit cost. Customer orders reserve stock immediately; cancellation releases it. The gross profit metric counts paid-and-processed orders using costs captured when the order was placed. Leave product cost blank when unknown. Unknown-cost orders are excluded from gross profit and marked for attention, while their completed sales still count as revenue. Cost updates apply to future orders; historical snapshots are preserved. This excludes delivery, payment fees, taxes and other operating expenses; it is not net accounting profit. Unpaid orders need manual cancellation if abandoned.

## Validate

```bash
cd /workspace/Ahmed_2024
python3 -m unittest -v test_shop.py
node --check app.js
```

The integration test starts a temporary server on port 18080 with an isolated database. It checks access control, hidden cost data, order totals, stock reservation, payment verification before completion, repeat cancellation, overselling, purchase receipt, repeat receipt protection, bilingual product fields and logout. It uses test bank data only in its temporary database. Browser validation additionally exercised the language switch, filters, bag, checkout gating, admin login/settings, and mobile layout.

## Before public launch

This is a working development version, not a published store. GitHub Pages cannot run the Python API or persistent SQLite database. Deploy behind an HTTPS reverse proxy on a Python host with a persistent disk, configure a strong `ADMIN_PASSWORD`, set `COOKIE_SECURE=1`, and back up the database securely (SQLite backup API). Do not run multiple independent instances against separate copies of the data. The standard-library server is for development; use a production-serving setup and review rate limits, customer-data retention, and recovery before launch.

Confirm the saved phone number is registered for incoming bank-app transfers and verify the receiving-bank details; configure real catalog/photos, shipping prices and service area, tax treatment, customer contact details, and store/privacy/returns policies before opening checkout publicly. Delivery and taxes are currently confirmed manually and excluded from product subtotals. Connecting card payments requires the owner's merchant account and a provider integration with signed payment webhooks; never mark an order paid from a browser redirect alone.

## Dar Heba catalog import

The corrected export has 344 product records and 2,908 image files across 11 uploaded ZIPs. Exactly 343 records have a single explicit OMR price and a primary photo. The remaining record is an unpriced listing page and is excluded. The export reports 31 failed requests, so this is not verified complete coverage of the source website. The first export had only 17 priced records because of Arabic URL errors; those 17 entries are retained unchanged and 326 new products are added.

catalog.json bundles 343 products and catalog-images/ bundles their optimized primary photos. All source prices are already OMR and are preserved to three-decimal precision without an exchange conversion. Extra recommendation/gallery pictures are not assigned to products. All new stock is zero, product cost unknown and age unspecified until the owner enters them. Language defaults to Arabic and may be edited to English. Simple explicitly named games are classified as toys; the owner can change categories.

On startup, catalog_import.py inserts absent source URLs/SKUs and records the manifest version. It preserves owner edits to existing prices, quantities, costs, translations, age ranges, visibility and payment settings, plus all orders. Demo cleanup runs only on the first import and hides only untouched unused demo rows; later imports preserve restored demos too. The incremental test simulates a 17-product shop upgraded to 343 products with edited prices, stock, visibility, a changed source slug and existing order history.

Tests: `TEST_PRODUCTION=1 python3 -m unittest -v test_shop.py test_catalog.py test_stats.py`. The business-flow fixture disables bundled loading only for its isolated demo database. Leave LOAD_BUNDLED_CATALOG unset in production. The PC exporter is tools/download_catalog.py; source failures still need another capture or usable direct access. Do not invent missing source prices, stock, costs or age suitability.

## Brand and public address

Business: Little Marvels, styled lil.Marvels. Instagram: https://www.instagram.com/lil.marvels.om/ (@lil.marvels.om). Preferred Render service name: `lil-marvels`, giving `lil-marvels.onrender.com` only if available and successfully deployed. The owner has deployed the shop at https://lil-marvels.onrender.com/. Subsequent Git pushes trigger Render auto-deployment; verify each new deployment separately. The Instagram handle is separate from the website hostname. The repository and existing data-directory names are unchanged to preserve startup and saved data.

## Statistics periods and product controls

The admin statistics default to Cumulative / all time. Choose Daily, Weekly, Monthly or Yearly and select the desired date, month or year. Periods use Asia/Muscat; weeks run Sunday–Saturday. Sales, captured cost of sold products, gross profit, completed order count and unknown-cost order count use the same completion-date window. Received supplier purchases use the receipt-date window and are shown separately; they are not deducted again from gross profit. Pending and cancelled orders do not count as sales. Current open orders and low-stock counts remain an explicitly separate snapshot across all dates.

New completions and purchase receipts store UTC timestamps. Historical records without those timestamps retain their original data and use creation dates, with a notice in the statistics. Unknown-cost completed orders count as sales but are excluded from cost/profit sums. This remains gross profit before delivery, taxes, fees and overhead.

Product stock and supplier quantities use integer steps of one; fractional quantities are rejected by the API. Price and cost retain three-decimal OMR precision. The product-language selector offers Arabic and English; new products default to Arabic. Existing unsupported language labels remain stored until edited, when one of the two choices is selected.

Validation: `TEST_PRODUCTION=1 python3 -m unittest -v test_shop.py test_catalog.py test_stats.py`. Browser checks cover period selectors and exact totals, both interface languages, mobile layout, whole-number steppers and saved product-language selection.

Inventory rows show the product photo beside its name, or a cover-symbol placeholder if no photo is set. WhatsApp checkout provides a numbered packing list using the saved order snapshot: every product name and ID, quantity, unit price and line total, total units and subtotal, customer name/phone, Geenakum delivery preference/address, and payment details. Customers still tap Send in WhatsApp. A Copy full order message option is available if the prepared message needs to be pasted manually.

The approved koala logo is served locally as brand-logo.png and used in the header, hero, footer and browser icon. The visual theme follows its purple ribbon, lime polka dots, blue and pink accents with dark readable text. Both Arabic/English layouts and mobile sizes were checked; catalog photographs keep their aspect ratio.

## Additional costs and net profit

Manage shop → Additional costs allows dated shipping costs, money-transfer fees, packaging and other expenses. Records can optionally link to an order or apply to the whole business. Delivery money collected from customers and other extra income can be recorded separately. Each record can be edited or removed (soft-voided, not deleted from the database). Entries and totals follow the selected statistics period, defaulting to all time, using the entered local Oman date. Costs remain recorded even if a linked order is later cancelled; remove or adjust a record if it was not actually incurred.

Net profit (recorded costs) = gross profit on known-cost completed orders + recorded extra income − recorded additional expenses. Supplier purchases are displayed separately and not deducted twice, and product costs must not be recorded again as additional expenses. Unknown-cost orders are flagged and excluded from profit, so the figure is incomplete until product costs are known. Unrecorded fees, taxes and overhead are not magically included. Historical records without completion/receipt timestamps use creation dates as documented above.

## Product photos and dedicated pages

Product clicks open /products/<id>, including direct links and reloads. The page shows all saved photos with thumbnail and previous/next controls, the full stored description (up to 10,000 characters per language), age groups, language, stock, quantity and Add to bag. The cart persists across pages. Inactive or missing products show an unavailable message.

Admin device uploads are authenticated and same-origin, validated as actual JPG/PNG/WebP files, stored under DATA_DIR/uploads with content-hash filenames, and served as raster images with nosniff. SVG and unsupported image types are rejected. Original raster bytes are retained without generative edits. Removing a gallery photo removes its product reference; physical files remain so shared references are not broken. The first photo is the main one. Existing URL-only photos remain compatible. Never commit uploads or the database to Git.

Back up the uploads directory alongside a consistent SQLite database backup. Both must be restored together. The persistent Render disk retains photos across deployments. Production dependencies now include pinned Pillow for file validation. Tests: `TEST_PRODUCTION=1 python3 -m unittest -v test_shop.py test_catalog.py test_stats.py test_photos.py`. Browser tests additionally covered the 343-product catalog, five age filters, cost/income entry and date-filtered net profit, upload/main-photo/remove controls, direct product URLs, full descriptions, cross-page cart and photo persistence after restart.

## Forgotten admin password

Choose Forgot password? on the management login screen for bilingual recovery instructions. The owner changes ADMIN_PASSWORD in Render → lil-marvels → Environment, saves and waits for the service restart, then signs in with the new password. The Render account authenticates the owner; no unauthenticated reset endpoint or email-reset delivery is configured. A password change/restart invalidates in-memory sessions and preserves the persistent database and uploads. Never ask the owner to share the password in chat.

## Shopping shortcuts, recovery contacts and product options

A floating cart bar shows item count, product subtotal, View cart and Checkout while browsing with a nonempty cart. It works on product pages, hides in management and when the cart is empty, and follows the interface language.

Forgot password? includes the owner-provided contact addresses ahmedalraqmi1993@gmail.com and ahmedalraqmi93@gmail.com as mailto links. These do not send automated reset emails. Recovery still uses the owner's authenticated Render account to change ADMIN_PASSWORD, save and restart the service; no email sender is configured.

Manage shop → Inventory → Edit → Product options → Add option creates named choices such as Boys, Girls or colors. There is no small fixed set of choices; the backend accepts up to 1,000 entries within request-size limits. Each active choice has stable identity and whole-number available stock, plus an optional OMR price override; blank means the main product price. The product unit cost applies to all choices. The parent stock total is calculated from active options. Customers must select an available choice before adding it to the cart. Distinct choices of the same product remain separate cart/order lines, with authoritative price and option-label snapshots in orders and WhatsApp packing lists.

Supplier purchases and receipts select a choice when appropriate. Cancelling an order restocks its chosen options once. Removing an option with an open order is blocked; finish or cancel the order first. Removed options and their hidden stock remain in Previous options / hidden stock and may be restored. Removing every option sets public available stock to zero. Late returns of legacy unconfigured orders to a now-configured product are retained as unassigned hidden stock for explicit owner allocation. Product Hide/Unhide never deletes choices or quantities.

Validation: `TEST_PRODUCTION=1 python3 -m unittest -v test_shop.py test_catalog.py test_stats.py test_photos.py test_options.py`. Browser checks exercised recovery contacts, dynamic option editing, required customer selection, separate option stock/prices, floating checkout, WhatsApp choice labels, cancellation, supplier receipt and mobile layout. No external messages or emails are sent by these tests.
