LITTLE MARVELS: DOWNLOAD PRODUCTS FROM A LINKS FILE

1. Download these files into ONE folder on your Windows PC:
   download_products.py
   download-products-requirements.txt
   START-PRODUCT-DOWNLOADER.bat
   ZIP-EXISTING-DOWNLOADS.bat
2. Install Python 3.10+ if needed and enable Add Python to PATH.
3. In Notepad, paste ONE product link per line. Save as links.txt (UTF-8).
4. Double-click START-PRODUCT-DOWNLOADER.bat.
   The first run installs the parser, browser automation package and Chromium.
   This can take a few minutes. Certificate/TLS checks remain enabled.
5. When the file-selection window opens, choose links.txt.
6. Keep the PC awake. The program processes links sequentially and prints DONE
   for each saved product, then ALL LINKS FINISHED.
7. Product folders appear beside the script under:
   littlerMarvels products\Product name\
      product.json
      description.txt
      photos\...
8. At the end, upload ALL ZIP files in the newest folder under:
   UPLOAD THESE ZIP FILES\DATE-TIME\
   This folder opens automatically. Upload EVERY numbered ZIP directly.
   Do NOT zip this folder again. Each ZIP is independently readable and at most
   25 MiB (26.3 MB), below the 32 MB transfer limit. Do not upload only the pictures;
   the JSON files are needed to match products, images and original prices.

The program collects ALL exposed primary-product image URLs found in structured
product data, embedded store JSON and product galleries, including lazy image
attributes and high-resolution gallery links. It avoids known recommendations
and unrelated galleries. It does not stop after the first photo. Duplicate image
content/resize URLs are reduced where possible. Photos are not edited or upscaled.

Some sites block automation, require login, omit full descriptions or keep photos
behind unsupported interactions. No universal script can guarantee every photo
from every store. Blocked pages and missing images/descriptions/prices are recorded
in batch_report.json or product.json. No access restrictions are bypassed and no
orders, payments or messages are submitted. This script is for public product links.

Original prices and currencies are preserved. It does NOT assume OMR or guess an
exchange rate. Product names are made safe for Windows folder names; matching names
from different links get a short suffix to keep products separate. Repeating a link
can refresh that product's saved metadata and photos; old files are not deleted.

Manual setup if you prefer Command Prompt:
  py -3 -m pip install -r download-products-requirements.txt
  py -3 -m playwright install chromium
  py -3 download_products.py

Optional: py -3 download_products.py --links "C:\path\links.txt"
Optional: add --show-browser to watch page loading.

ALREADY DOWNLOADED YOUR PRODUCTS?
Double-click ZIP-EXISTING-DOWNLOADS.bat and select your existing, extracted
littlerMarvels products folder. It creates upload-ready ZIP parts without
downloading anything again. Keep product.json files beside their photos.
