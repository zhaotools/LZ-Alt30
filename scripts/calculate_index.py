"""LZ-Alt30: fixed current basket reference history and forward price index.
Run: python calculate_index.py --prices daily_prices.csv --output index_values.csv
Input dates are sampling dates, not exchange OHLC candle dates.
"""
import argparse,csv,datetime,json,math,pathlib
BASE_DATE='2026-10-13'
BASE_VALUE=1000.0

def calculate(rows,ids,base_date=BASE_DATE):
    if not rows: raise ValueError('No price rows')
    dates=[r['date'] for r in rows]
    if dates!=sorted(set(dates)):raise ValueError('Dates must be unique and increasing')
    if any((datetime.date.fromisoformat(b)-datetime.date.fromisoformat(a)).days!=1 for a,b in zip(dates,dates[1:])):
        raise ValueError('Missing daily sampling date')
    for r in rows:
        datetime.date.fromisoformat(r['date'])
        for cid in ids+['bitcoin']:
            if cid not in r or not math.isfinite(float(r[cid])) or float(r[cid])<=0:
                raise ValueError('Missing or invalid price: '+r['date']+' '+cid)
    if base_date not in dates:raise ValueError('Missing base date '+base_date)
    n=len(ids); q=None; live_q=None; output=[]
    first=rows[0]
    for r in rows:
        d=datetime.date.fromisoformat(r['date'])
        if q is None:q={cid:BASE_VALUE/n/float(r[cid]) for cid in ids}
        reference=sum(q[cid]*float(r[cid]) for cid in ids)
        # Value old holdings first, then set new holdings: no rebalance jump.
        if d.day==1 and d.month in (1,4,7,10):
            q={cid:reference/n/float(r[cid]) for cid in ids}
        live=None
        if r['date']==base_date:
            live_q={cid:BASE_VALUE/n/float(r[cid]) for cid in ids}
            live=BASE_VALUE
        elif r['date']>base_date:
            if live_q is None:raise ValueError('Missing live index initialization')
            live=sum(live_q[cid]*float(r[cid]) for cid in ids)
            if d.day==1 and d.month in (1,4,7,10):
                live_q={cid:live/n/float(r[cid]) for cid in ids}
        output.append({'date':r['date'],'LZ_Alt30_live':live,
            'Alt30_current_basket_reference':reference,
            'BTC_reference':BASE_VALUE*float(r['bitcoin'])/float(first['bitcoin']),
            'ETH_reference':BASE_VALUE*float(r['ethereum'])/float(first['ethereum'])})
    return output

def main():
    p=argparse.ArgumentParser();p.add_argument('--prices',default='daily_prices.csv');p.add_argument('--output',default='index_values.csv');a=p.parse_args()
    root=pathlib.Path(__file__).resolve().parent
    members=json.load(open(root/'constituents.json',encoding='utf-8'))
    with open(a.prices,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    output=calculate(rows,[r[0] for r in members])
    with open(a.output,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    print(json.dumps({'rows':len(output),'base_date':BASE_DATE,'latest':output[-1]},ensure_ascii=False))
if __name__=='__main__':main()
