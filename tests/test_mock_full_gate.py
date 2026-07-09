#!/usr/bin/env python3
from __future__ import annotations
import csv,subprocess,sys,tempfile,threading,os
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]

def write_csv(path, rows, fields=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if fields is None: fields=list(rows[0])
 with path.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
 with tempfile.TemporaryDirectory() as td:
  td=Path(td);site=td/'site';site.mkdir();pkg=td/'pkg';store=td/'store'
  for d in ('data/source_catalogues','output/staging','scripts'):(pkg/d).mkdir(parents=True,exist_ok=True)
  for p in (ROOT/'scripts').glob('*.py'):(pkg/'scripts'/p.name).write_bytes(p.read_bytes())
  im=Image.new('RGB',(600,600),'white');d=ImageDraw.Draw(im);d.rectangle((180,40,420,570),fill=(210,210,210),outline='black',width=5)
  for y in range(50,560,7):d.line((185,y,415,y+2),fill=(y%255,100,170),width=2)
  d.rectangle((200,220,400,420),fill='white',outline='black');d.multiline_text((225,250),'TEST BRAND\nEXACT PRODUCT\n60 CAPS',fill='black');im.save(site/'exact.png')
  (site/'logo.png').write_bytes((site/'exact.png').read_bytes())
  (site/'product.html').write_text('<title>Test Brand Exact Product 60 caps</title><script type="application/ld+json">{"@type":"Product","name":"Exact Product 60 caps","brand":{"name":"Test Brand"},"image":"/exact.png"}</script><meta property="og:image" content="/logo.png"><h1>Test Brand Exact Product 60 caps</h1>')
  class Q(SimpleHTTPRequestHandler):
   def log_message(self,*a):pass
  old=Path.cwd();os.chdir(site);srv=ThreadingHTTPServer(('127.0.0.1',0),Q);threading.Thread(target=srv.serve_forever,daemon=True).start();port=srv.server_address[1]
  row={'batchIndex':'1','region':'ca','catalogueRow':'1','sourceCatalogue':'catalogue_ca_with_product_images_v24_final_208_completion.csv','immutableKey':'ca:test:0','productId':'test','variantIndex':'0','brand':'Test Brand','productName':'Exact Product','variantProduct':'Exact Product','format':'Capsules','size':'60 caps','rawSize':'60 capsules','sku':'','priceNow':'1','currentImageKind':'product','priorTrustedClaim':'False','currentImageReference':f'http://127.0.0.1:{port}/product.html','sourcePage':f'http://127.0.0.1:{port}/product.html','sourceDomain':'127.0.0.1','sourceClass':'official-manufacturer-product-page','imageResolutionMethod':'','priorMatchStatus':'','priorFrontFacingClaim':'','priorNotes':'','isMicrolinkResolver':'False','isLegacyLocalReference':'False','isBarcodeDatabaseSource':'False','isSharedSourceConflict':'False','sourceMetadataDomainInvalid':'False','explicitPriorVisualVerification':'False','includedImageFileExists':'False','includedImageDecodes':'False','includedImageIsJpeg':'False','bottleOrOfficialProductImageConfirmed':'False','productionReady':'False','auditDecision':'','auditReason':'','targetJpgPath':'assets/product-images/test.jpg','imageAlt':'Test Brand Exact Product 60 caps'}
  write_csv(pkg/'data/all_20076_strict_image_audit.csv',[row])
  write_csv(pkg/'data/brand_official_domain_map.csv',[{'brand':'Test Brand','officialDomain':'127.0.0.1','evidenceWeight':'1'}])
  source_fields=['region','productId','variantIndex','imageSrc','imageKind','imageTrusted','imageResolutionMethod','imageMatchStatus','imageNotes']
  write_csv(pkg/'data/source_catalogues/catalogue_ca_with_product_images_v24_final_208_completion.csv',[{'region':'ca','productId':'test','variantIndex':'0','imageSrc':'old','imageKind':'product','imageTrusted':'False','imageResolutionMethod':'old','imageMatchStatus':'old','imageNotes':''}],source_fields)
  for reg in ['eu','uk','us']: write_csv(pkg/f'data/source_catalogues/catalogue_{reg}_with_product_images_v24_final_208_completion.csv',[],source_fields)
  subprocess.run([sys.executable,str(pkg/'scripts/acquire_all_20076_real_images.py'),'--package-root',str(pkg),'--store-root',str(store),'--limit','1','--workers','1'],check=True)
  res=list(csv.DictReader((pkg/'output/all_20076_acquisition_results.csv').open(encoding='utf-8-sig')))[0]
  assert res['status'].startswith('STAGED'),res
  assert res['origin']=='jsonld-product-image',res
  assert res['resolvedImageUrl'].endswith('/exact.png'),res
  rp=pkg/'output/manual_visual_review.csv';reviews=list(csv.DictReader(rp.open(encoding='utf-8-sig')));reviews[0]['manualVisualDecision']='APPROVED_EXACT_PRODUCT_PACKAGE';reviews[0]['reviewer']='mock-test';reviews[0]['evidenceNote']='Exact label and package visible.'
  for field in ['brandExact','productNameExact','sizeQuantityExact','strengthExactOrNotApplicable','formExactOrNotApplicable','flavourAudienceBundleExactOrNotApplicable','officialProductImageOrBottle','noLogoPlaceholderLifestyle']: reviews[0][field]='true'
  reviews[0]['reviewedBrand']='Test Brand';reviews[0]['reviewedProductName']='Exact Product';reviews[0]['reviewedSizeQuantity']='60 caps';write_csv(rp,reviews,list(reviews[0]))
  subprocess.run([sys.executable,str(pkg/'scripts/validate_all_20076_real_images.py'),'--package-root',str(pkg),'--store-root',str(store),'--materialize-approved','--expected-count','1'],check=True)
  assert (store/'assets/product-images/test.jpg').exists()
  assert len(list(csv.DictReader((pkg/'output/catalogue_ca_V28_PRODUCTION_READY.csv').open(encoding='utf-8-sig'))))==1
  srv.shutdown();os.chdir(old)
 print('mock full gate PASS')
if __name__=='__main__':main()
