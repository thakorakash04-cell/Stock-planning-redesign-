"""Allowlisted, literal trigger checks; never executes AI code or expressions."""
from datetime import datetime
from zoneinfo import ZoneInfo
import math,re

def matches(cell,operator,value,today=None):
    if operator=='is_blank':return cell is None or str(cell).strip() in ('','—')
    if operator=='not_blank':return not matches(cell,'is_blank','')
    if operator=='contains':return str(value).casefold() in str(cell or '').casefold()
    if operator=='=':return str(cell if cell is not None else '').strip().casefold()==str(value).strip().casefold()
    if operator in ('>','>=','<','<='):
        try:a=float(str(cell).replace(',',''));b=float(value)
        except (TypeError,ValueError):return False
        if not math.isfinite(a) or not math.isfinite(b):return False
        return {'>':a>b,'>=':a>=b,'<':a<b,'<=':a<=b}[operator]
    if operator in ('date_before_today','due_within_days'):
        try:
            if isinstance(cell,(int,float)):return False
            import pandas as pd
            date=pd.to_datetime(cell,errors='coerce')
            if pd.isna(date):return False
            day=date.date();today=today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
            return day<today if operator=='date_before_today' else 0<=(day-today).days<=float(value)
        except (ValueError,TypeError,OverflowError):return False
    raise ValueError('Unsupported trigger condition.')

def points(rules,sheets,include_disabled=False):
    by_name={s['name']:s for s in sheets};reports={}
    for rule in rules:
        if not include_disabled and not rule.get('enabled'):continue
        email=str(rule.get('recipient','')).strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Invalid recipient email.')
        sheet=by_name.get(rule.get('section'))
        if not sheet:raise ValueError('Unknown saved section: '+str(rule.get('section')))
        filters=[{'column':rule.get('column'),'operator':rule.get('operator'),'value':rule.get('value','')}]+rule.get('filters',[])
        if len(filters)>9 or any(f.get('column') not in sheet['headers'] for f in filters):raise ValueError('Unknown trigger column. Review the saved workbook and rule.')
        found=[row for row in sheet['rows'] if all(matches(row[sheet['headers'].index(f['column'])],f['operator'],f.get('value','')) for f in filters)]
        report=reports.setdefault(email,{'recipient':email,'points':[],'matched':0})
        report['points'].append({'id':rule.get('id',str(len(report['points']))),'title':rule.get('name') or rule.get('message') or rule.get('column'),'count':len(found),'table':{'name':sheet['name'],'headers':sheet['headers'],'rows':found[:100]}});report['matched']+=len(found)
    return list(reports.values())
