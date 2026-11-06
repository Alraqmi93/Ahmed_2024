#!/usr/bin/env python3
"""Batch public-product photo/description export for Little Marvels (Windows-friendly)."""
import argparse, hashlib, json, re, sys, time, unicodedata, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, parse_qsl, urlencode, unquote
from urllib.robotparser import RobotFileParser
try:
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit('Run START-PRODUCT-DOWNLOADER.bat, or install: py -3 -m pip install -r download-products-requirements.txt')

FOLDER_NAME='littlerMarvels products'
MAX_PHOTO=20*1024*1024
GALLERIES='.woocommerce-product-gallery, .product-gallery, .product__media-wrapper, .product-single__photos, .product-images, #product-images, [data-product-gallery], [class*="product-gallery"], [class*="product_gallery"], [class*="product-images"], [id*="product-gallery"], main [class*="gallery"]'
DESCRIPTIONS='[itemprop="description"], #tab-description, #product-description, .product-description, .product__description, .product-single__description, .woocommerce-Tabs-panel--description, .product-details__description, [class*="product_description"]'
RELATED=re.compile(r'recommend|related|upsell|cross.sell|recently.viewed',re.I)


def normalize_url(url):
    p=urlsplit(url.strip())
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:
        raise ValueError('Use a public http/https product link without login details.')
    host=p.hostname.encode('idna').decode('ascii')
    if ':' in host:host='['+host+']'
    if p.port:host+=':'+str(p.port)
    query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.startswith('utm_') and k not in ('fbclid','gclid')])
    return urlunsplit((p.scheme,host,quote(p.path,safe="/%:@!$&'()*+,;=-._~"),query,''))


def read_links(path):
    raw=Path(path).read_bytes();text=None
    for encoding in ('utf-8-sig','utf-16','cp1256','cp1252'):
        try:text=raw.decode(encoding);break
        except UnicodeError:pass
    if text is None:raise ValueError('Save the links file as UTF-8 text.')
    links=[]
    for line in text.splitlines():
        if line.lstrip().startswith('#'):continue
        for url in re.findall(r'https?://[^\s<>"\']+',line):
            url=url.rstrip('.,;،')
            while url.endswith(')') and url.count(')')>url.count('('):url=url[:-1]
            try:url=normalize_url(url)
            except ValueError:continue
            if url not in links:links.append(url)
    return links


def safe_name(name):
    value=unicodedata.normalize('NFC',str(name))
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]',' ',value)
    value=re.sub(r'\s+',' ',value).strip(' .')[:90].rstrip(' .') or 'Product'
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?',value,re.I):value='Product '+value
    return value


def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk(child)
    elif isinstance(value,list):
        for child in value:yield from walk(child)


def text_of(value):
    soup=BeautifulSoup(str(value),'html.parser')
    for tag in soup(['script','style','noscript','svg']):tag.decompose()
    return '\n'.join(line.strip() for line in soup.get_text('\n',strip=True).splitlines() if line.strip())


def image_values(value):
    if isinstance(value,str):return [value]
    if isinstance(value,list):return [url for item in value for url in image_values(item)]
    if isinstance(value,dict):
        if value.get('media_type') in ('video','external_video'):return []
        return image_values(value.get('contentUrl') or value.get('originalSrc') or value.get('original_src') or value.get('src') or value.get('url') or value.get('image') or value.get('preview_image') or [])
    return []


def asset_key(url):
    # Collapse declared thumbnail/resize URLs for the same photo; never invent an image URL.
    value=url
    if '/cdn-cgi/image/' in value:
        match=re.search(r'/https?://',value.split('/cdn-cgi/image/',1)[1])
        if match:value=value.split('/cdn-cgi/image/',1)[1][match.start()+1:]
    p=urlsplit(value)
    path=re.sub(r'_\d+x\d*(?=\.[a-zA-Z]+$)','',p.path)
    query=urlencode([(k,v) for k,v in parse_qsl(p.query) if k.lower() not in ('w','h','width','height','q','quality','fit','format','fm','auto')])
    return urlunsplit((p.scheme,p.netloc,path,query,''))


def resolution_score(url):
    p=urlsplit(url);query=dict(parse_qsl(p.query))
    for key in ('width','w'):
        if str(query.get(key,'')).isdigit():return int(query[key])
    match=re.search(r'(?:width=|/w=|_)(\d{2,5})(?:x|,|&|/|$)',url)
    return int(match[1]) if match else 10000


def parse_product(html,url):
    soup=BeautifulSoup(html,'html.parser')
    def meta(*names):
        for name in names:
            tag=soup.find('meta',attrs={'property':name}) or soup.find('meta',attrs={'name':name})
            if tag and tag.get('content'):return tag['content']
        return ''
    blobs=[];candidates=[]
    for script in soup.find_all('script'):
        if script.get('type','').split(';')[0] not in ('application/ld+json','application/json'):continue
        try:blob=json.loads(script.string or script.get_text());blobs.append(blob)
        except (ValueError,TypeError):continue
        for node in walk(blob):
            types=node.get('@type',[]);types=types if isinstance(types,list) else [types]
            if any(t in ('Product','ProductGroup') for t in types):candidates.append(node)
    def score(product):
        source=str(product.get('url',''))
        return int(bool(source) and unquote(urlsplit(urljoin(url,source)).path).rstrip('/')==unquote(urlsplit(url).path).rstrip('/'))*10
    product=max(candidates,key=score) if candidates else {}
    h1=soup.find('h1')
    name=product.get('name') or (h1.get_text(' ',strip=True) if h1 else '') or meta('og:title') or (soup.title.get_text(' ',strip=True) if soup.title else '')
    if not name:raise ValueError('No product name found; this page may require login or block automated access.')
    description_candidates=[]
    for node in soup.select(DESCRIPTIONS):
        if any(RELATED.search(' '.join(parent.get('class',[]))+' '+str(parent.get('id',''))) for parent in node.parents if getattr(parent,'attrs',None)):continue
        value=text_of(str(node))
        if value:description_candidates.append(value)
    description=max(description_candidates,key=len) if description_candidates else text_of(product.get('description') or meta('og:description','description'))
    price_records=[]
    offers=product.get('offers',[])
    for offer in walk(offers):
        amount=offer.get('price',offer.get('lowPrice'))
        if amount is not None:
            record={'amount':str(amount),'currency':str(offer.get('priceCurrency','')),'availability':str(offer.get('availability',''))}
            if record not in price_records:price_records.append(record)
    for variant in product.get('hasVariant',[]) if isinstance(product.get('hasVariant'),list) else []:
        for offer in walk(variant.get('offers',[])):
            if offer.get('price') is not None:
                price_records.append({'amount':str(offer['price']),'currency':str(offer.get('priceCurrency','')),'option':str(variant.get('name',''))})
    if not price_records and meta('product:price:amount','og:price:amount'):
        price_records=[{'amount':meta('product:price:amount','og:price:amount'),'currency':meta('product:price:currency','og:price:currency')}]
    pictures=[]
    def add(value):
        for source in image_values(value):
            if source and not source.startswith(('data:','blob:')):
                try:pictures.append(normalize_url(urljoin(url,source)))
                except ValueError:pass
    add(product.get('image',[]))
    for variant in product.get('hasVariant',[]) if isinstance(product.get('hasVariant'),list) else []:add(variant.get('image',[]))
    # Embedded store JSON can contain the full product gallery and variant images.
    for blob in blobs:
        for node in walk(blob):
            title=str(node.get('title') or node.get('name') or '')
            if title and title.strip().casefold()==str(name).strip().casefold():
                add(node.get('images',[]));add(node.get('media',[]))
                for variant in node.get('variants',[]) if isinstance(node.get('variants'),list) else []:add(variant.get('featured_image',[]))
    for gallery in soup.select(GALLERIES):
        ancestors=[gallery,*gallery.parents]
        if any(RELATED.search(' '.join(node.get('class',[]))+' '+str(node.get('id',''))) for node in ancestors if getattr(node,'attrs',None)):continue
        for image in gallery.select('img, source'):
            for key in ('data-zoom-image','data-large_image','data-original','data-src','src'):
                if image.get(key):add(image[key]);break
            srcset=image.get('data-srcset') or image.get('srcset') or ''
            candidates=re.findall(r'(.*?)\s+(\d+(?:\.\d+)?[wx])(?:\s*,\s*|$)',srcset)
            if candidates:
                for source,_ in candidates:add(source.strip())
            elif srcset.strip():add(srcset.strip())
        for link in gallery.select('a[href]'):
            if re.search(r'\.(?:jpe?g|png|webp|avif|gif)(?:\?|$)',link['href'],re.I):add(link['href'])
    if not pictures:add(meta('og:image'))
    dedup={}
    for image in pictures:
        key=asset_key(image)
        if key not in dedup or resolution_score(image)>resolution_score(dedup[key]):dedup[key]=image
    pictures=list(dedup.values())
    if not pictures:raise ValueError('No product photos found. The site may hide the gallery behind login or block downloads.')
    if not candidates and not soup.select(GALLERIES) and 'product' not in meta('og:type').lower():
        raise ValueError('This page was not recognized as a product page; no generic site/logo images were saved.')
    return {'name':str(name).strip(),'description':description,'sku':str(product.get('sku','')),
        'prices':price_records,'image_urls':pictures,'images':[],'source_url':url,
        'captured_at':datetime.now(timezone.utc).isoformat(),'description_source':'page product-description section' if description_candidates else 'structured data / page metadata'}


def collect_rendered_product(page):
    product=parse_product(page.content(),page.url)
    galleries=page.locator(GALLERIES)
    if not galleries.count():return product
    gallery=galleries.first
    thumbnails=gallery.locator("button[data-media-id], button[data-thumbnail], button[class*='thumb'], button[aria-label^='View image' i], button[aria-label^='Show image' i], button[aria-label^='Show photo' i], .flex-control-thumbs img, .fotorama__nav__frame")
    pictures=list(product['image_urls']);interaction_errors=[]
    for index in range(thumbnails.count()):
        try:
            thumbnails.nth(index).click(timeout=2000)
            page.wait_for_timeout(300)
            pictures.extend(parse_product(page.content(),page.url)['image_urls'])
        except Exception:
            interaction_errors.append('Could not inspect gallery thumbnail '+str(index+1))
    if not thumbnails.count():
        next_buttons=gallery.locator(".swiper-button-next, button[aria-label^='Next image' i], button[aria-label^='Next photo' i]")
        if next_buttons.count():
            unchanged=0
            for _ in range(50):
                try:
                    before=set(pictures);next_buttons.first.click(timeout=1500);page.wait_for_timeout(300)
                    pictures.extend(parse_product(page.content(),page.url)['image_urls'])
                    unchanged=unchanged+1 if set(pictures)==before else 0
                    if unchanged>=3:break
                except Exception:
                    interaction_errors.append('Could not inspect the next gallery image');break
    best={}
    for url in pictures:
        key=asset_key(url)
        if key not in best or resolution_score(url)>resolution_score(best[key]):best[key]=url
    product['image_urls']=list(best.values())
    product['gallery_review_notes']=interaction_errors
    if len(product['image_urls'])==1:product['gallery_review_notes'].append('Only one photo was exposed. Check whether the source gallery has unsupported interactions.')
    return product


class Downloader:
    def __init__(self,context,root):self.context=context;self.root=Path(root);self.robots={};self.last_request={}
    def permitted(self,url):
        p=urlsplit(url);origin=p.scheme+'://'+p.netloc
        if origin not in self.robots:
            robot=RobotFileParser(origin+'/robots.txt')
            response=self.context.request.get(origin+'/robots.txt',timeout=30000)
            try:
                if response.status==404:robot.allow_all=True
                elif response.status in (401,403):robot.disallow_all=True
                elif response.ok:robot.parse(response.text().splitlines())
                else:raise ValueError('Could not check robots.txt: HTTP '+str(response.status))
            finally:response.dispose()
            self.robots[origin]=robot
        allowed=self.robots[origin].can_fetch('LittleMarvelsProductDownloader',url)
        if allowed:
            delay=max(.5,self.robots[origin].crawl_delay('LittleMarvelsProductDownloader') or self.robots[origin].crawl_delay('*') or 0)
            time.sleep(max(0,delay-(time.monotonic()-self.last_request.get(origin,0))))
            self.last_request[origin]=time.monotonic()
        return allowed
    def folder_for(self,product):
        base=self.root/safe_name(product['name']);folder=base
        if folder.exists():
            try:existing=json.loads((folder/'product.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):existing={}
            if existing.get('source_url')!=product['source_url']:
                folder=self.root/(safe_name(product['name'])+' - '+hashlib.sha256(product['source_url'].encode()).hexdigest()[:8])
        folder.mkdir(parents=True,exist_ok=True);(folder/'photos').mkdir(exist_ok=True)
        return folder
    def download(self,url):
        if not self.permitted(url):raise ValueError('robots.txt disallows this product URL.')
        page=self.context.new_page()
        try:
            response=page.goto(url,wait_until='domcontentloaded',timeout=60000)
            if response and response.status>=400:raise ValueError('Product page returned HTTP '+str(response.status))
            try:page.wait_for_load_state('networkidle',timeout=8000)
            except Exception:pass
            # Trigger lazy gallery loading; no cart, payment or account controls are clicked.
            for position in (600,1200,0):page.evaluate('(y)=>window.scrollTo(0,y)',position);page.wait_for_timeout(350)
            product=collect_rendered_product(page)
        finally:page.close()
        folder=self.folder_for(product);failures=[];hashes=set()
        for index,image_url in enumerate(product['image_urls'],1):
            print('   Photo '+str(index)+'/'+str(len(product['image_urls'])),flush=True)
            try:
                if not self.permitted(image_url):raise ValueError('Image is disallowed by robots.txt')
                response=self.context.request.get(image_url,timeout=45000)
                try:
                    if not response.ok:raise ValueError('Image HTTP '+str(response.status))
                    mime=response.headers.get('content-type','').split(';')[0].lower()
                    suffix={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/avif':'.avif','image/gif':'.gif'}.get(mime)
                    if not suffix:raise ValueError('Not a supported photo: '+mime)
                    if int(response.headers.get('content-length','0') or 0)>MAX_PHOTO:raise ValueError('Photo exceeds 20 MB')
                    body=response.body()
                    if len(body)>MAX_PHOTO:raise ValueError('Photo exceeds 20 MB')
                finally:response.dispose()
                digest=hashlib.sha256(body).hexdigest()
                if digest not in hashes:
                    path='photos/'+digest[:24]+suffix;(folder/path).write_bytes(body);product['images'].append(path);hashes.add(digest)
            except Exception as error:failures.append({'url':image_url,'error':str(error)});print('   Failed photo:',error)
            time.sleep(.5)
        product['photo_errors']=failures
        product['status']='complete' if product['images'] and not failures and product['description'] else 'partial'
        (folder/'product.json').write_text(json.dumps(product,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'description.txt').write_text(product['description'],encoding='utf-8')
        print('   DONE:',product['name'],'|',len(product['images']),'photos |',folder,flush=True)
        if not product['description']:print('   Description was not found; this is recorded in product.json.')
        if not product['prices']:print('   Price was not found; no price or currency was guessed.')
        return product


def package(root,report):
    records=[];files=[]
    for manifest in sorted(root.glob('*/product.json')):
        try:product=json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        folder=manifest.parent;product['folder']=folder.name;records.append(product)
        files.extend([manifest,folder/'description.txt'])
        for path in product.get('images',[]):
            if re.fullmatch(r'photos/[a-f0-9]{24}\.(jpg|png|webp|avif|gif)',path):files.append(folder/path)
    (root/'batch_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'batch_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    out=root/'upload-zips'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True,exist_ok=True)
    part=0;used=0
    def create():
        nonlocal part,used
        part+=1;archive=zipfile.ZipFile(out/f'littlerMarvels-products-part-{part:03d}.zip','w',zipfile.ZIP_DEFLATED)
        used=0
        for name in ('batch_manifest.json','batch_report.json'):
            archive.write(root/name,name);used+=(root/name).stat().st_size
        return archive
    archive=create()
    try:
        for path in dict.fromkeys(files):
            if not path.is_file():continue
            size=path.stat().st_size
            if used+size>25*1024*1024:archive.close();archive=create()
            archive.write(path,str(path.relative_to(root)));used+=size
    finally:archive.close()
    return out


def choose_file():
    try:
        import tkinter as tk
        from tkinter.filedialog import askopenfilename
        window=tk.Tk();window.withdraw();window.attributes('-topmost',True)
        path=askopenfilename(title='Choose the Notepad file with product links',filetypes=[('Text files','*.txt'),('All files','*.*')]);window.destroy();return path
    except Exception:return input('Paste the full path to your links .txt file: ').strip().strip('"')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--links',help='Optional path to the links text file; otherwise a file picker opens')
    parser.add_argument('--output',default=str(Path(__file__).resolve().parent/FOLDER_NAME))
    parser.add_argument('--show-browser',action='store_true')
    parser.add_argument('--browser-executable',help='Optional installed Chromium/Chrome executable')
    args=parser.parse_args();source=args.links or choose_file()
    if not source:print('No file selected.');return
    links=read_links(source)
    if not links:raise SystemExit('No valid http/https links found in the text file.')
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    report={'links_requested':len(links),'successful':0,'partial':0,'failed':[],'note':'Only publicly available product/gallery data was collected. No login or access restrictions were bypassed. Prices/currencies were preserved, not converted. Some sites may not expose every photo or full description.'}
    print('Found',len(links),'unique links. Output:',root,flush=True)
    with sync_playwright() as playwright:
        try:browser=playwright.chromium.launch(headless=not args.show_browser,**({'executable_path':args.browser_executable} if args.browser_executable else {}))
        except Exception as error:raise SystemExit('Browser could not start. Run: py -3 -m playwright install chromium\n'+str(error))
        context=browser.new_context(locale='ar-OM',viewport={'width':1440,'height':1000})
        worker=Downloader(context,root)
        try:
            for index,url in enumerate(links,1):
                print('\nPRODUCT',index,'OF',len(links),':',url,flush=True)
                try:
                    result=worker.download(url);report['successful' if result['status']=='complete' else 'partial']+=1
                except KeyboardInterrupt:report['interrupted']=True;print('Stopped. Packaging products already saved.');break
                except Exception as error:report['failed'].append({'url':url,'error':str(error)});print('   FAILED:',error,flush=True)
                time.sleep(1)
        finally:context.close();browser.close()
    out=package(root,report)
    print('\nALL LINKS FINISHED. Complete:',report['successful'],'Partial:',report['partial'],'Failed:',len(report['failed']))
    print('Product folders:',root)
    print('UPLOAD every ZIP part from:',out)
    print('Keep the original folders. Check batch_report.json for missing content; completion is not a guarantee that a site exposed every photo.')


if __name__=='__main__':
    try:main()
    except Exception as error:print('ERROR:',error);raise SystemExit(1)
