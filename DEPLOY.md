# Deploy Little Marvels on Render

These files must be committed and pushed to the connected GitHub branch before Render can use them. The cloud development workspace is not automatically synced to GitHub. Do not deploy the old placeholder repository.

| Render field | Value |
| --- | --- |
| Name | lil-marvels (subject to availability) |
| Language | Python 3 |
| Branch | main |
| Region | Frankfurt if available |
| Root Directory | Leave blank |
| Build Command | pip install -r requirements.txt |
| Start Command | bash start-production.sh |
| Compute | Paid instance supporting persistent disks |
| Health Check Path | /api/products |

Add a persistent disk with mount path `/var/data` and initial capacity 1 GB. Confirm Render's current disk price separately from compute.

Set environment variables:

| Name | Value |
| --- | --- |
| DATA_DIR | /var/data |
| COOKIE_SECURE | 1 |
| ADMIN_PASSWORD | A unique strong password entered privately in Render |
| PYTHON_VERSION | 3.12.14 |

Let Render supply PORT; do not set it manually. Use a single instance and a single Gunicorn worker because sessions are in memory and the database is SQLite. A process restart requires admin login again. TLS terminates at Render; secure cookies are required for the public service.

Render does not receive `/workspace/ahmed-business-data` automatically. A fresh database imports the 343 bundled Dar Heba products at zero stock and unknown cost, hides untouched demos, and has no bank/WhatsApp settings. Before accepting real orders, transfer the existing database securely or enter the receiving-account and WhatsApp settings through the admin UI; replace demo products with the actual catalog, stock, costs and prices. Do not commit databases, passwords, customer details or order data to Git. The Dar Heba import is partial: 343 priced records from the corrected uploaded export, with 31 source requests still failing. The 17 previous products are preserved and 326 are added. Set shipping charges and policies before launch. Back up the persistent database regularly using SQLite's backup API, and back up DATA_DIR/uploads as well; keep backups private. Both the database and upload files are needed to restore device-uploaded product photos.

After deployment, use the actual HTTPS address Render issues; `lil-marvels.onrender.com` is a proposed name, not a confirmed deployment. Verify storefront, admin login, settings persistence across a restart, and an end-to-end unpaid test order. Do not open WhatsApp or send a real message during automated tests. Cancel test orders to restore stock. The current WhatsApp flow is a customer-sent message draft, not an automatic WhatsApp Business API message.
