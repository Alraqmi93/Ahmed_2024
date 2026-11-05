#!/usr/bin/env python3
"""Export a public product catalog and its images. Python 3.10+; no packages needed."""
import argparse, csv, hashlib, io, json, re, time, zipfile
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

AGENT = 'LittleMarvelsCatalogExport/1.0'
MAX_IMAGE = 20 * 1024 * 1024
SKIP = re.compile(r'/(cart|checkout|account|login|register|wishlist|search|blog|blogs|privacy|terms)(/|\?|$)', re.I)

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links=[]; self.meta={}; self.schemas=[]; self.gallery=[]
        self.title=''; self.in_title=False; self.in_json=False; self.script=[]; self.stack=[]
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='meta':
            key=a.get('property',a.get('name','')).lower()
            if key and a.get('content'): self.meta.setdefault(key,[]).append(a['content'])
        if tag=='title': self.in_title=True
        if tag=='script' and a.get('type','').split(';')[0]=='application/ld+json': self.in_json=True; self.script=[]
        context=' '.join(self.stack[-6:])+ ' '+a.get('class','')+' '+a.get('id','')
        if tag=='img' and re.search(r'product.gallery|product.media|product.image|product__media|gallery',context,re.I):
            src=a.get('data-src') or a.get('src')
            srcset=a.get('data-srcset') or a.get('srcset')
            if srcset: src=srcset.split(',')[-1].strip().split(' ')[0]
            if src: self.gallery.append(src)
        if tag not in ('meta','link','img','br','hr','input','source','area','base','embed','param','wbr'):
            self.stack.append(a.get('class','')+' '+a.get('id',''))
    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
        if tag=='script' and self.in_json:
            try: self.schemas.append(json.loads(''.join(self.script)))
            except (ValueError,TypeError): pass
            self.in_json=False
        if self.stack: self.stack.pop()
    def handle_data(self, data):
        if self.in_title: self.title+=data
        if self.in_json: self.script.append(data)
    def first(self,*keys):
        for key in keys:
            if self.meta.get(key):return self.meta[key][0]
        return ''

def nodes(obj):
    if isinstance(obj,dict):
        yield obj
        for value in obj.values():yield from nodes(value)
    elif isinstance(obj,list):
        for value in obj:yield from nodes(value)

def image_urls(obj):
    if isinstance(obj,str):return [obj]
    if isinstance(obj,list):return [url for item in obj for url in image_urls(item)]
    if isinstance(obj,dict):return image_urls(obj.get('contentUrl') or obj.get('url') or '')
    return []

def extract(page,url):
    product=next((x for schema in page.schemas for x in nodes(schema) if 'Product' in (x.get('@type') if isinstance(x.get('@type'),list) else [x.get('@type')])),None)
    probable=bool(re.search(r'/(products?|p)/',urlsplit(url).path,re.I)) or 'product' in page.first('og:type').lower()
    if not product and not probable:return None
    if re.search(r'/reviews?(/|$)',urlsplit(url).path):return None
    product=product or {}
    offers=product.get('offers',[])
    if isinstance(offers,dict):offers=[offers]
    prices=[]
    for offer in offers:
        if not isinstance(offer,dict):continue
        children=offer.get('offers')
        candidates=children if isinstance(children,list) else [offer]
        for x in candidates:
            if not isinstance(x,dict):continue
            amount=x.get('price',x.get('lowPrice',''))
            spec=x.get('priceSpecification',{})
            if isinstance(spec,list):spec=spec[0] if spec else {}
            if amount=='':amount=spec.get('price','') if isinstance(spec,dict) else ''
            currency=x.get('priceCurrency') or offer.get('priceCurrency') or (spec.get('priceCurrency','') if isinstance(spec,dict) else '')
            if amount!='':prices.append({'amount':str(amount),'currency':str(currency),'url':x.get('url',''),'availability':x.get('availability','')})
    if not prices:
        amount=page.first('product:price:amount','og:price:amount','price')
        currency=page.first('product:price:currency','og:price:currency','pricecurrency')
        if amount:prices=[{'amount':amount,'currency':currency}]
    images=image_urls(product.get('image',[]))+page.meta.get('og:image',[])
    images=list(dict.fromkeys(urljoin(url,x) for x in images if x and not x.startswith('data:')))
    name=product.get('name') or page.first('og:title') or page.title
    if not name or not images:return None
    return {'source_url':url,'name':str(name),'description':str(product.get('description') or page.first('og:description','description')),'sku':str(product.get('sku','')),'prices':prices,'image_urls':images,'images':[],'captured_at':datetime.now(timezone.utc).isoformat()}

class Export:
    def __init__(self,args):
        self.args=args;self.base=args.url.rstrip('/')+'/';self.host=urlsplit(self.base).netloc.lower()
        self.out=Path(args.output);self.out.mkdir(parents=True,exist_ok=True)
        (self.out/'images').mkdir(exist_ok=True)
        self.errors=[];self.products=[];self.last=0;self.delay=args.delay;self.robots={};self.denied=False
    def request(self,url,limit):
        time.sleep(max(0,self.delay-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        parts=urlsplit(url)
        path=parts.path
        if parts.netloc.lower()=='darheba.com' and path.startswith('/products/'):
            path='/ar-om'+path
        url=urlunsplit((parts.scheme,parts.netloc,quote(path,safe="/%:@!$&'()*+,;=-._~"),quote(parts.query,safe="%=&?/:@!$'()*+,;~-._"),''))
        req=Request(url,headers={'User-Agent':AGENT,'Accept-Language':'ar-OM,ar;q=0.9,en;q=0.8'})
        with urlopen(req,timeout=40) as r:
            data=r.read(limit+1)
            if len(data)>limit:raise ValueError('Response exceeds download size limit')
            return data,r.headers.get('Content-Type',''),r.geturl()
    def permitted(self,url):
        p=urlsplit(url);root=p.scheme+'://'+p.netloc
        if root not in self.robots:
            robot=RobotFileParser(root+'/robots.txt')
            try:
                data,_,_=self.request(root+'/robots.txt',1024*1024)
                robot.parse(data.decode('utf-8','replace').splitlines())
            except HTTPError as e:
                if e.code in (401,403):robot.disallow_all=True
                elif e.code==404:robot.allow_all=True
                else:raise
            self.robots[root]=robot
            interval=robot.crawl_delay(AGENT) or robot.crawl_delay('*')
            if interval:self.delay=max(self.delay,interval)
        return self.robots[root].can_fetch(AGENT,url)
    def fetch(self,url,limit=8*1024*1024):
        if not self.permitted(url):raise ValueError('robots.txt disallows this URL')
        return self.request(url,limit)
    def error(self,url,error):
        self.errors.append({'url':url,'error':str(error)})
        print('  Could not retrieve:',url,'—',error)
    def normalize(self,url):
        p=urlsplit(urljoin(self.base,url))
        if p.scheme not in ('https','http') or p.netloc.lower()!=self.host or SKIP.search(p.path):return None
        locale=re.match(r'^/([a-z]{2}-[a-z]{2})/',p.path,re.I)
        wanted=re.match(r'^/([a-z]{2}-[a-z]{2})/',urlsplit(self.base).path,re.I)
        if locale and wanted and locale[1].lower()!=wanted[1].lower():return None
        if re.search(r'\.(jpg|jpeg|png|webp|svg|gif|pdf|zip|js|css|mp4)$',p.path,re.I):return None
        query=urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('fbclid','gclid','sort','sort_by')])
        return urlunsplit((p.scheme,p.netloc,p.path,query,''))
    def run(self):
        queue=deque([self.base]);queued={self.base};visited=set();product_ids=set()
        # Sitemaps help discover products absent from the visible navigation.
        sitemaps=deque([urljoin(self.base,'/sitemap.xml')]);seen_maps=set()
        while sitemaps and len(seen_maps)<100:
            url=sitemaps.popleft()
            if url in seen_maps:continue
            seen_maps.add(url)
            try:
                data,_,_=self.fetch(url);root=ET.fromstring(data)
                locations=[x.text for x in root.iter() if x.tag.split('}')[-1]=='loc' and x.text]
                for loc in locations:
                    if urlsplit(loc).netloc.lower()!=self.host:continue
                    if root.tag.split('}')[-1]=='sitemapindex':sitemaps.append(loc)
                    else:
                        u=self.normalize(loc)
                        if u and u not in queued:queue.append(u);queued.add(u)
            except Exception as e:self.error(url,e)
        while queue and len(visited)<self.args.max_pages:
            url=queue.popleft()
            if url in visited:continue
            visited.add(url)
            print(f'Page {len(visited)} | products {len(self.products)} | {url}',flush=True)
            try:
                data,content,final=self.fetch(url)
                if 'html' not in content:continue
                page=Page(data.decode('utf-8','replace'))
                product=extract(page,final)
                if product:
                    identity=product['sku'] or product['source_url'].split('?')[0].rstrip('/')
                    if identity not in product_ids:self.products.append(product);product_ids.add(identity)
                for link in page.links:
                    u=self.normalize(urljoin(final,link))
                    if u and u not in queued:queue.append(u);queued.add(u)
            except Exception as e:
                self.error(url,e)
                if isinstance(e,HTTPError) and e.code in (401,403,429):
                    print('Access restricted or rate limited. Stopping catalog crawl; no bypass attempted.')
                    self.denied=True;break
        cache={}
        for index,product in enumerate(self.products,1):
            print(f'Downloading photos: product {index}/{len(self.products)}',flush=True)
            for url in product['image_urls']:
                if url in cache:
                    if cache[url]:product['images'].append(cache[url])
                    continue
                try:
                    data,content,_=self.fetch(url,MAX_IMAGE)
                    mime=content.split(';')[0].lower()
                    suffix={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif','image/avif':'.avif'}.get(mime)
                    if not suffix:raise ValueError('Not a supported raster image: '+content)
                    name=hashlib.sha256(data).hexdigest()[:24]+suffix
                    rel='images/'+name;(self.out/rel).write_bytes(data)
                    cache[url]=rel;product['images'].append(rel)
                except Exception as e:cache[url]=None;self.error(url,e)
        report={'source':self.base,'products_found':len(self.products),'pages_visited':len(visited),'pages_not_visited':len(queue),'page_limit_reached':bool(queue and len(visited)>=self.args.max_pages),'access_restricted':self.denied,'products_without_prices':sum(not p['prices'] for p in self.products),'products_without_currency':sum(not p['prices'] or any(not x.get('currency') for x in p['prices']) for p in self.products),'products_without_downloaded_images':sum(not p['images'] for p in self.products),'downloaded_images':len(set(v for v in cache.values() if v)),'errors':self.errors,'note':'This is a best-effort public HTML/sitemap export. JavaScript-only or unlinked products may be missing. Original prices are preserved; no currency conversion is guessed.'}
        (self.out/'products.json').write_text(json.dumps(self.products,ensure_ascii=False,indent=2),encoding='utf-8')
        (self.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        with (self.out/'products.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['name','source_url','sku','original_price','currency','images'])
            writer.writeheader()
            for p in self.products:
                offer=p['prices'][0] if p['prices'] else {}
                writer.writerow({'name':p['name'],'source_url':p['source_url'],'sku':p['sku'],'original_price':offer.get('amount',''),'currency':offer.get('currency',''),'images':';'.join(p['images'])})
        self.package()
        print('\nFinished:',report['products_found'],'products,',report['downloaded_images'],'photos.')
        if not self.products:print('NO PRODUCTS FOUND. The site may require browser rendering or deny automated requests. Upload report.json; do not assume the catalog was downloaded.')
        elif self.errors or queue:print('Some URLs failed or remain unvisited. See report.json; this is not a verified complete catalog.')
        print('Upload every darheba-part-*.zip from:',self.out.resolve())
    def package(self):
        # Separate normal ZIPs, not a split-archive format. Every part has the manifests.
        files=sorted((self.out/'images').glob('*'));part=0;used=0;archive=None
        def new_archive():
            nonlocal part,used
            part+=1;used=0
            z=zipfile.ZipFile(self.out/f'darheba-part-{part:03d}.zip','w',zipfile.ZIP_DEFLATED)
            for name in ('products.json','products.csv','report.json'):z.write(self.out/name,name)
            used=sum((self.out/name).stat().st_size for name in ('products.json','products.csv','report.json'))
            return z
        archive=new_archive()
        try:
            for f in files:
                size=f.stat().st_size
                if used+size>25*1024*1024 and used>0:archive.close();archive=new_archive()
                archive.write(f,'images/'+f.name);used+=size
        finally:archive.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='https://darheba.com/ar-om/')
    parser.add_argument('--output',default='darheba-export-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    parser.add_argument('--max-pages',type=int,default=1500)
    parser.add_argument('--delay',type=float,default=0.7,help='Minimum delay between requests in seconds')
    args=parser.parse_args()
    if args.max_pages<1 or args.delay<0.2:parser.error('Use at least 1 page and at least 0.2 seconds delay')
    try:Export(args).run()
    except KeyboardInterrupt:print('\nStopped by user. Run again to create a new export.')
    except Exception as e:print('Export failed:',e);raise SystemExit(1)
