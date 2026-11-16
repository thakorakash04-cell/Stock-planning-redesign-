"""Public login appearance, with bounded uploaded images and stable cached stores."""
import base64,io,importlib
REVISION=5

def defaults(title):
    regulatory='regulatory' in title.lower()
    return {'title':title,'subtitle':'REGULATORY RESEARCH WORKSPACE' if regulatory else 'OPERATIONS WORKSPACE','login_text':('Explore FDA clearances and CDSCO classifications.\nReview registration details and regulatory evidence.\nOne workspace for informed product decisions.' if regulatory else 'Track stock, production and material requirements.\nConnect forecasts, purchasing and sales planning.\nOne shared workbook for clearer decisions.'),'signin_heading':'Sign in to continue','signin_text':'Your administrator controls your account, segment access and available sections.'}

def validate_logo(value):
    if value=='':return
    if not isinstance(value,str) or len(value)>350000:raise ValueError('Choose a PNG, JPEG or WebP logo below 250 KB.')
    prefix,sep,encoded=value.partition(',')
    if not sep or prefix not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'):raise ValueError('Use a PNG, JPEG or WebP image.')
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>250*1024:raise ValueError()
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as picture:
            expected={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}
            if expected.get(picture.format)!=prefix[5:-7] or picture.width>2000 or picture.height>2000:raise ValueError()
            picture.verify()
    except Exception:raise ValueError('Choose a valid logo below 250 KB and 2000 × 2000 pixels.') from None

def install(store):
    from . import portal_features
    if getattr(portal_features,'BRANDING_REVISION',0)!=5:portal_features=importlib.reload(portal_features)
    # Cached stores retain their class; update only the two settings methods.
    for name in ('portal_read','portal_save'):setattr(type(store),name,getattr(portal_features.PortalFeatures,name))

def default_logo(title):
    regulatory='regulatory' in title.lower()
    paths=('<path d="M48 12 77 24v22c0 20-14 33-29 40C33 79 19 66 19 46V24Z"/><path d="m33 47 10 10 22-24"/>' if regulatory else '<path d="m18 32 30-17 30 17v34L48 83 18 66Z"/><path d="m18 32 30 17 30-17M48 49v34M33 24l30 17"/>')
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'+paths+'</svg>'
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()

