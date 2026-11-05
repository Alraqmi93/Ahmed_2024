# Little Marvels · lil.Marvels

Arabic / English shop for children's books and toys, with OMR pricing and a password-protected inventory dashboard. Python 3.12+ and SQLite; no runtime packages or external services required for local development.

## Run

```bash
cd /workspace/Ahmed_2024
bash start.sh
```

The server listens locally on port 8000 by default. `HOST`, `PORT`, `DATA_DIR`, and `ADMIN_PASSWORD` are supported overrides. `start.sh` uses an existing `ADMIN_PASSWORD`, or creates a random password in `/workspace/ahmed-business-data/admin-password` with owner-only permissions. The shop owner can retrieve this local password in their private terminal; do not commit it or share it in chat. Database and generated credentials live outside the checkout. Live processes must be restarted after environment restoration.

Use the existing checkout; tasks are already isolated and don't need Git worktrees.

## Manage the shop

Choose Manage shop / إدارة المتجر and sign in. Add Arabic and English product names and descriptions, prices, cost, stock, and an optional HTTPS product photo URL. Remove from shop hides a product without deleting order history; Restore makes it visible again. Existing sample products are illustrative; replace all sample products, costs, stock, descriptions, and safety claims before accepting real orders. Symbols are placeholders until real product photographs are added.

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

## Pending Dar Heba catalog import

The owner requested all products and images from https://darheba.com/ar-om/, with prices in OMR. No catalog has been imported yet: the running environment denies access to darheba.com. An additive network-domain change is saved in the environment draft and awaits the user settings workflow. After access is applied, inspect the complete catalog and actual displayed price currency before choosing a documented conversion. Do not guess rates or treat the /ar-om/ URL alone as proof of OMR pricing. Start imported stock at zero and cost as unknown unless the owner supplies them, preserve source identities and image provenance, and do not overwrite later owner edits during repeat imports.

## Brand and public address

Business: Little Marvels, styled lil.Marvels. Instagram: https://www.instagram.com/lil.marvels.com/ (@lil.marvels.com). Preferred Render service name: `lil-marvels`, giving `lil-marvels.onrender.com` only if available and successfully deployed. This address is not reserved, published or verified. Use the actual hostname issued by Render at deployment. Instagram handle ownership does not establish ownership of the separate domain lil.marvels.com. The repository and existing data-directory names are unchanged to preserve startup and saved data.
