#!/usr/bin/env python3
"""Lê URLs configuradas, extrai Product/Offer de JSON-LD e gera precos.json."""
from __future__ import annotations
import json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'fontes.json'
OUTPUT=ROOT/'precos.json'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; GPUPriceMonitor/1.0; +uso-pessoal)'}

def objects(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from objects(v)
    elif isinstance(x,list):
        for v in x: yield from objects(v)

def parse_price(v):
    if isinstance(v,(int,float)): return float(v)
    if v is None: return None
    s=re.sub(r'[^0-9,\.]','',str(v))
    if ',' in s and '.' in s: s=s.replace('.','').replace(',','.')
    elif ',' in s: s=s.replace(',','.')
    try: return float(s)
    except ValueError: return None

def scrape(item,session):
    url=item['url']; r=session.get(url,headers=HEADERS,timeout=25); r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser'); candidates=[]
    for tag in soup.select('script[type="application/ld+json"]'):
        try: data=json.loads(tag.get_text(strip=True))
        except Exception: continue
        for obj in objects(data):
            typ=obj.get('@type',[]); typ=[typ] if isinstance(typ,str) else typ
            if 'Product' in typ:
                offers=obj.get('offers',{}); offers=offers if isinstance(offers,list) else [offers]
                for offer in offers:
                    if isinstance(offer,dict):
                        p=parse_price(offer.get('price') or offer.get('lowPrice'))
                        if p: candidates.append((p,offer.get('url') or url))
    if not candidates: raise ValueError('Preço não encontrado em JSON-LD')
    price,offer_url=min(candidates,key=lambda x:x[0])
    return {'id':item.get('id') or re.sub(r'\W+','-',item['modelo'].lower()).strip('-'),'modelo':item['modelo'],'preco':round(price,2),'loja':item.get('loja') or urlparse(url).netloc,'url':offer_url}

def main():
    cfg=json.loads(CONFIG.read_text(encoding='utf-8')); previous={}
    if OUTPUT.exists():
        try: previous={x['id']:x for x in json.loads(OUTPUT.read_text(encoding='utf-8')).get('ofertas',[])}
        except Exception: pass
    out=[]; errors=[]
    with requests.Session() as session:
        for item in cfg.get('fontes',[]):
            if not item.get('ativo',True): continue
            try: out.append(scrape(item,session))
            except Exception as e:
                errors.append({'modelo':item.get('modelo'),'erro':str(e)[:180]})
                if item.get('id') in previous: out.append(previous[item['id']])
            time.sleep(float(cfg.get('intervalo_segundos',2)))
    payload={'atualizado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'),'ofertas':out,'erros':errors}
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(out)} ofertas; {len(errors)} erros')
if __name__=='__main__': main()
