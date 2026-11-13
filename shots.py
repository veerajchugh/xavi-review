import sys
from playwright.sync_api import sync_playwright
B=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8787'; O='/workspace/xavi-review/shots/'
PW=open('/workspace/xavi-review/.site_password').read().strip()
pref=sys.argv[2] if len(sys.argv)>2 else ''
with sync_playwright() as p:
    br=p.chromium.launch(channel='chrome',args=['--no-sandbox'])
    for name,vp,mob,hashes in [('desktop',(1440,1000),False,['week','approved','passed','pipeline','all']),('mobile',(390,844),True,['week'])]:
        ctx=br.new_context(viewport={'width':vp[0],'height':vp[1]},device_scale_factor=2,is_mobile=mob)
        pg=ctx.new_page(); pg.goto(B+'/',wait_until='networkidle')
        if mob or name=='desktop':
            if pg.locator('input[type=password]').count():
                if name=='desktop': pg.screenshot(path=O+pref+'login.png')
                pg.fill('input[type=password]',PW); pg.click('button'); pg.wait_for_load_state('networkidle')
        for h in hashes:
            pg.evaluate(f"location.hash='{h}'"); pg.wait_for_timeout(900)
            pg.screenshot(path=O+f'{pref}{name}-{h}.png',full_page=(h!='week')); print(name,h)
        ctx.close()
    br.close()
