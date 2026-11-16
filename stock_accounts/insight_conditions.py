"""Typed dashboard conditions over the existing authorized source snapshot."""
import math,re
from datetime import date,datetime,timedelta
MONTHS=('january','february','march','april','may','june','july','august','september','october','november','december')
REVISION=1
DATE_OPS={'date_on','date_not_on','date_before','date_on_or_before','date_after','date_on_or_after','date_between','date_blank','date_not_blank','date_invalid'}
def calendar_date(value):
 if isinstance(value,bool) or value is None:return None
 if isinstance(value,(date,datetime)):
  try:return date(value.year,value.month,value.day) if 1900<=value.year<=9999 else None
  except (TypeError,ValueError):return None
 if isinstance(value,(int,float)):
  if not math.isfinite(value) or not 1<=value<2958466 or math.floor(value)==60:return None
  try:return date(1899,12,31 if value<60 else 30)+timedelta(days=math.floor(value))
  except (ValueError,OverflowError):return None
 if not isinstance(value,str) or not value.strip():return None
 text=re.sub(r' (IST|UTC|GMT)$','',value.strip(),flags=re.I)
 time=re.search(r'[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$',text,re.I)
 if time:
  if int(time[1])>23 or int(time[2])>59 or int(time[3] or 0)>59:return None
  text=text[:time.start()]
 match=re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',text)
 if match:parts=(int(match[1]),int(match[2]),int(match[3]))
 else:
  match=re.fullmatch(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})',text)
  if match:parts=(int(match[3]),int(match[2]),int(match[1]))
  else:
   match=re.fullmatch(r'(\d{1,2})[- /]([a-z]+)[- /](\d{4})',text,re.I)
   reverse=False
   if not match:match=re.fullmatch(r'([a-z]+) (\d{1,2}),? (\d{4})',text,re.I);reverse=True
   if not match:return None
   name=match[1 if reverse else 2].casefold();month=next((i for i,m in enumerate(MONTHS,1) if name in (m,m[:3])),0)
   parts=(int(match[3]),month,int(match[2 if reverse else 1]))
 try:return date(*parts) if 1900<=parts[0]<=9999 else None
 except (ValueError,TypeError):return None

def facet_kind(header,values):
 if re.search(r'date|timestamp|created.?at|updated.?at',str(header),re.I):return 'date'
 sample=[v for v in values if v is not None and v!=''][:64]
 if sample and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in sample):return 'number'
 if sample and all(isinstance(v,str) and calendar_date(v) is not None for v in sample):return 'date'
 return 'text'

def narrow(table,filters):
 """Validate special conditions first; apply them without changing source rows."""
 rows=table['rows']
 for rule in filters:
  op=rule['op'];value=rule['value'];index=table['headers'].index(rule['column'])
  if op=='number_between':
   if not isinstance(value,list) or len(value)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value) or value[0]>value[1]:raise ValueError('Enter a finite numeric minimum and maximum in ascending order.')
   import pandas as pd
   from grounded_ai import numeric_values
   raw=pd.Series([r[index] for r in rows],dtype=object);numbers=numeric_values(raw);mask=numbers.ge(value[0])&numbers.le(value[1])&~raw.map(lambda v:isinstance(v,bool))
   rows=[row for row,keep in zip(rows,mask) if keep];continue
  if op not in DATE_OPS:raise ValueError('Unsupported date/number condition.')
  unary=op in ('date_blank','date_not_blank','date_invalid');start=end=None
  if unary:
   if value is not None:raise ValueError('Blank/invalid-date conditions do not take a value.')
  elif op=='date_between':
   if not isinstance(value,list) or len(value)!=2 or any(not isinstance(v,str) for v in value):raise ValueError('Choose both start and end dates.')
   start,end=map(calendar_date,value)
   if start is None or end is None or start>end:raise ValueError('Choose valid start and end dates in ascending order.')
  else:
   if not isinstance(value,str):raise ValueError('Choose a valid calendar date.')
   start=calendar_date(value)
   if start is None:raise ValueError('Choose a valid calendar date.')
  cache={}
  def matches(row):
   raw=row[index];blank=raw is None or raw=='';key=(type(raw).__name__,str(raw))
   if key not in cache:cache[key]=calendar_date(raw)
   actual=cache[key]
   if op=='date_blank':return blank
   if op=='date_not_blank':return not blank
   if op=='date_invalid':return not blank and actual is None
   if actual is None:return False
   return {'date_on':lambda:actual==start,'date_not_on':lambda:actual!=start,'date_before':lambda:actual<start,'date_on_or_before':lambda:actual<=start,'date_after':lambda:actual>start,'date_on_or_after':lambda:actual>=start,'date_between':lambda:start<=actual<=end}[op]()
  rows=[row for row in rows if matches(row)]
 return {**table,'rows':rows}
