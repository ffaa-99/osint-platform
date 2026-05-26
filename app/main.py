from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import subprocess
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
from app.database import save_search, get_all_searches, get_search_by_id, delete_search, get_stats
from app.auth import (
    login, logout, require_auth, require_admin,
    create_user, delete_user, change_password,
    list_users, active_sessions, COOKIE_NAME,
    get_current_user
)

# ─────────────────────────────────────────
# PDF GENERATOR
# ─────────────────────────────────────────
def generate_pdf_report(target, search_type, results):
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER

    W, H       = A4
    GENERATED  = datetime.now().strftime("%d %B %Y")
    TIME_UTC   = datetime.now().strftime("%H:%M UTC")
    CASE_ID    = f"OS-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    ANALYST    = "OSINT Intelligence Unit"
    N_FOUND    = sum(1 for r in results if r["status"] == "FOUND")
    N_TOTAL    = len(results)
    SCORE      = min(95, 50 + N_FOUND * 8)
    RISK       = "HIGH" if N_FOUND >= 7 else ("MEDIUM" if N_FOUND >= 4 else "LOW")
    pdf_path   = REPORTS_DIR / f"report_{search_type}_{target}.pdf"

    BLACK=colors.HexColor("#000000"); DARK=colors.HexColor("#1a1a1a")
    MID=colors.HexColor("#555555"); LIGHT=colors.HexColor("#888888")
    LIGHT_GREY=colors.HexColor("#f4f4f4"); LINE=colors.HexColor("#cccccc")
    LINE_DARK=colors.HexColor("#999999"); WHITE=colors.white

    def draw_page(canv, doc):
        canv.saveState()
        canv.setFillColor(WHITE); canv.rect(0,0,W,H,fill=1,stroke=0)
        canv.setFillColor(colors.HexColor("#f4f4f4")); canv.rect(0,H-42,W,42,fill=1,stroke=0)
        canv.setFont("Helvetica-Bold",10); canv.setFillColor(BLACK)
        canv.drawString(20,H-16,"OSINT PLATFORM")
        canv.setFont("Helvetica",7); canv.setFillColor(LIGHT)
        canv.drawString(20,H-28,"Digital Intelligence Division")
        canv.setFont("Helvetica-Bold",7.5); canv.setFillColor(BLACK)
        canv.drawRightString(W-20,H-14,f"CASE NO: {CASE_ID}")
        canv.setFont("Helvetica",7); canv.setFillColor(LIGHT)
        canv.drawRightString(W-20,H-24,"CLASSIFICATION: CONFIDENTIAL")
        canv.drawRightString(W-20,H-33,"FOR OFFICIAL USE ONLY")
        canv.setFillColor(BLACK); canv.rect(0,H-44,W,2,fill=1,stroke=0)
        canv.setFillColor(colors.HexColor("#f4f4f4")); canv.rect(0,0,W,34,fill=1,stroke=0)
        canv.setFillColor(BLACK); canv.rect(0,34,W,2,fill=1,stroke=0)
        canv.setFont("Helvetica",7); canv.setFillColor(MID)
        canv.drawString(20,20,f"Generated: {GENERATED}  |  {TIME_UTC}  |  {ANALYST}")
        canv.setFont("Helvetica-Bold",7); canv.drawRightString(W-20,20,f"Page {doc.page}")
        canv.setFont("Helvetica",6.5); canv.setFillColor(LIGHT)
        canv.drawCentredString(W/2,8,"OSINT Platform — For Authorized Personnel Only")
        canv.restoreState()

    base=getSampleStyleSheet()
    def S(name,**kw):
        s=base["Normal"].clone(name)
        for k,v in kw.items(): setattr(s,k,v)
        return s
    s_title=S("t",fontName="Helvetica-Bold",fontSize=20,textColor=BLACK,alignment=TA_CENTER,spaceAfter=16)
    s_sub=S("st",fontName="Helvetica",fontSize=9,textColor=MID,alignment=TA_CENTER,spaceAfter=0)
    s_section=S("sc",fontName="Helvetica-Bold",fontSize=9.5,textColor=BLACK,spaceBefore=0,spaceAfter=4)
    s_label=S("lb",fontName="Helvetica-Bold",fontSize=8,textColor=MID)
    s_value=S("vl",fontName="Helvetica",fontSize=9,textColor=DARK,leading=16)
    s_body=S("bd",fontName="Helvetica",fontSize=9,textColor=DARK,leading=20)
    s_small=S("sm",fontName="Helvetica",fontSize=7.5,textColor=MID)

    def hr(thick=0.5,before=4,after=8,color=None):
        c=color or (LINE_DARK if thick>=1 else LINE)
        return HRFlowable(width="100%",thickness=thick,color=c,spaceBefore=before,spaceAfter=after)

    def section(number,title):
        t=Table([[Paragraph(f"{number}.  {title.upper()}",s_section)]],colWidths=[W-3.8*cm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),LIGHT_GREY),("LEFTPADDING",(0,0),(0,0),12),
            ("TOPPADDING",(0,0),(0,0),10),("BOTTOMPADDING",(0,0),(0,0),10),
            ("LINEBEFORE",(0,0),(0,0),3,BLACK),("LINEBELOW",(0,0),(0,0),0.4,LINE)]))
        return [Spacer(1,18),t,Spacer(1,12)]

    doc=SimpleDocTemplate(str(pdf_path),pagesize=A4,rightMargin=1.8*cm,leftMargin=1.8*cm,
        topMargin=2.8*cm,bottomMargin=1.8*cm,title=f"OSINT Report - {target}",author="OSINT Platform")
    story=[]
    story.append(Spacer(1,10))
    story.append(Paragraph("OPEN SOURCE INTELLIGENCE REPORT",s_title))
    story.append(Paragraph(f"Digital Footprint Assessment  —  {search_type.title()} Analysis",s_sub))
    story.append(Spacer(1,26)); story.append(hr(1.5,0,18,BLACK))
    meta_rows=[
        [Paragraph("CASE NUMBER",s_label),Paragraph(CASE_ID,s_value),Paragraph("SEARCH TYPE",s_label),Paragraph(search_type.upper(),s_value)],
        [Paragraph("TARGET",s_label),Paragraph(target,s_value),Paragraph("RISK LEVEL",s_label),Paragraph(RISK,S("rk",fontName="Helvetica-Bold",fontSize=9,textColor=BLACK))],
        [Paragraph("DATE GENERATED",s_label),Paragraph(GENERATED,s_value),Paragraph("ANALYST",s_label),Paragraph(ANALYST,s_value)],
    ]
    meta_t=Table(meta_rows,colWidths=[3.6*cm,6.2*cm,3.2*cm,5.2*cm])
    meta_t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),1,BLACK),("LINEAFTER",(1,0),(1,-1),0.5,LINE_DARK),
        ("LINEBELOW",(0,0),(-1,-2),0.3,LINE),("TOPPADDING",(0,0),(-1,-1),14),
        ("BOTTOMPADDING",(0,0),(-1,-1),14),("LEFTPADDING",(0,0),(-1,-1),12),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ROWBACKGROUNDS",(0,0),(-1,-1),[WHITE,LIGHT_GREY,WHITE])]))
    story.append(meta_t)
    story+=section("1","Executive Summary")
    confirmed_platforms=", ".join(r["site"] for r in results if r["status"]=="FOUND")
    story.append(Paragraph(
        f"OSINT assessment on <b>{target}</b>. Covered <b>{N_TOTAL}</b> sources. "
        f"<b>{N_FOUND} confirmed indicators</b>. Risk: <b>{RISK}</b>. Confidence: <b>{SCORE}%</b>.",s_body))
    story+=section("2","Full Results")
    res_rows=[["NO.","SOURCE","STATUS","CONF.","DETAILS"]]
    for i,r in enumerate(results,1):
        res_rows.append([str(i),r["site"],"CONFIRMED" if r["status"]=="FOUND" else "NOT FOUND",
            f'{r["confidence"]}%' if r["confidence"]>0 else "N/A",r.get("label","")])
    res_t=Table(res_rows,colWidths=[1*cm,3.2*cm,3.0*cm,2.0*cm,8.5*cm])
    res_ts=TableStyle([("BACKGROUND",(0,0),(-1,0),BLACK),("TEXTCOLOR",(0,0),(-1,0),WHITE),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
        ("TEXTCOLOR",(0,1),(-1,-1),DARK),("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT_GREY]),("GRID",(0,0),(-1,-1),0.4,LINE),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),8),("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(3,0),(3,-1),"CENTER")])
    for i,r in enumerate(results,1):
        if r["status"]=="FOUND": res_ts.add("FONTNAME",(2,i),(2,i),"Helvetica-Bold")
        else:
            res_ts.add("TEXTCOLOR",(2,i),(2,i),LIGHT)
            res_ts.add("TEXTCOLOR",(3,i),(3,i),LIGHT)
    res_t.setStyle(res_ts); story.append(res_t)
    story+=section("3","Conclusion")
    story.append(Paragraph(
        f"<b>{N_FOUND}</b> confirmed indicators for <b>{target}</b>. "
        f"Exposure: <b>{SCORE}%</b>. Risk: <b>{RISK}</b>. All OSINT data — requires independent verification.",s_body))
    story.append(Spacer(1,16)); story.append(hr(0.4,2,8,LINE_DARK))
    story.append(Paragraph("DISCLAIMER: OSINT only. Publicly available sources. CONFIDENTIAL.",s_small))
    doc.build(story,onFirstPage=draw_page,onLaterPages=draw_page)
    return pdf_path


# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
app=FastAPI()
BASE_DIR=Path(__file__).resolve().parent.parent
APP_DIR=Path(__file__).resolve().parent
templates=Jinja2Templates(directory=str(APP_DIR/"templates"))
app.mount("/static",StaticFiles(directory=str(APP_DIR/"static")),name="static")
REPORTS_DIR=BASE_DIR/"reports"
REPORTS_DIR.mkdir(exist_ok=True)

def cleanup_reports():
    now=datetime.now()
    for file in REPORTS_DIR.glob("*"):
        try:
            if now-datetime.fromtimestamp(file.stat().st_mtime)>timedelta(hours=24): file.unlink()
        except Exception: pass
cleanup_reports()

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language":"en-US,en;q=0.9",
}

SOCIAL_PLATFORMS=[
    {"site":"Instagram","url":"https://www.instagram.com/{}/"},
    {"site":"Twitter","url":"https://x.com/{}"},
    {"site":"Snapchat","url":"https://www.snapchat.com/add/{}"},
    {"site":"Facebook","url":"https://www.facebook.com/{}"},
    {"site":"GitHub","url":"https://github.com/{}"},
    {"site":"YouTube","url":"https://www.youtube.com/@{}"},
    {"site":"LinkedIn","url":"https://www.linkedin.com/in/{}/"},
    {"site":"Telegram","url":"https://t.me/{}"},
    {"site":"TikTok","url":"https://www.tiktok.com/@{}"},
    {"site":"Reddit","url":"https://www.reddit.com/user/{}"},
]
DIRECT_CHECK_SITES={"Twitter","Snapchat","Facebook","Instagram","TikTok","Reddit"}
NOT_FOUND_SIGNALS=["page not found","user not found","sorry, this page","doesn't exist",
    "account suspended","isn't available","this account doesn't exist","no results",
    "profile not found","sorry, this","page does not exist"]


# ═══════════════════════════════════════════════════════
# أدوات مجانية
# ═══════════════════════════════════════════════════════
def lookup_ip(ip):
    try:
        r=requests.get(f"https://ipapi.co/{ip}/json/",headers={"User-Agent":"OSINT-Platform"},timeout=10)
        if r.status_code==200:
            d=r.json()
            if "error" not in d:
                return {"ip":d.get("ip",ip),"country":d.get("country_name","Unknown"),
                    "city":d.get("city","Unknown"),"region":d.get("region","Unknown"),
                    "org":d.get("org","Unknown"),"timezone":d.get("timezone","Unknown"),
                    "latitude":d.get("latitude",0),"longitude":d.get("longitude",0)}
    except Exception: pass
    return {}

def get_subdomains(domain):
    subdomains=set()
    try:
        r=requests.get(f"https://crt.sh/?q=%.{domain}&output=json",headers={"User-Agent":"OSINT-Platform"},timeout=15)
        if r.status_code==200:
            for entry in r.json()[:50]:
                for sub in entry.get("name_value","").split("\n"):
                    sub=sub.strip().lower()
                    if sub.endswith(f".{domain}") and "*" not in sub: subdomains.add(sub)
    except Exception: pass
    return sorted(list(subdomains))[:20]

def check_wayback(domain):
    try:
        r=requests.get(f"http://archive.org/wayback/available?url={domain}",headers={"User-Agent":"OSINT-Platform"},timeout=10)
        if r.status_code==200:
            snap=r.json().get("archived_snapshots",{}).get("closest",{})
            if snap.get("available"):
                ts=snap.get("timestamp","")
                return {"available":True,"url":snap.get("url",""),
                    "date":f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts)>=8 else ts}
    except Exception: pass
    return {"available":False}

def dns_lookup(domain):
    results={}
    for rtype in ["A","MX","TXT","NS","AAAA"]:
        try:
            r=requests.get(f"https://dns.google/resolve?name={domain}&type={rtype}",headers={"User-Agent":"OSINT-Platform"},timeout=8)
            if r.status_code==200:
                answers=r.json().get("Answer",[])
                if answers: results[rtype]=[a.get("data","") for a in answers[:5]]
        except Exception: pass
    return results

def search_urlscan(domain):
    try:
        r=requests.get(f"https://urlscan.io/api/v1/search/?q=domain:{domain}&size=5",headers={"User-Agent":"OSINT-Platform"},timeout=10)
        if r.status_code==200:
            rl=r.json().get("results",[])
            if rl:
                latest=rl[0]
                return {"found":True,"total":r.json().get("total",0),
                    "last_scan":latest.get("task",{}).get("time",""),
                    "scan_url":f"https://urlscan.io/result/{latest.get('task',{}).get('uuid','')}/",
                    "country":latest.get("page",{}).get("country",""),
                    "server":latest.get("page",{}).get("server",""),
                    "ip":latest.get("page",{}).get("ip","")}
    except Exception: pass
    return {"found":False}

def get_github_info(username):
    try:
        r=requests.get(f"https://api.github.com/users/{username}",
            headers={"User-Agent":"OSINT-Platform","Accept":"application/vnd.github.v3+json"},timeout=10)
        if r.status_code==200:
            d=r.json()
            repos_info=[]
            try:
                rr=requests.get(f"https://api.github.com/users/{username}/repos?sort=stars&per_page=5",
                    headers={"User-Agent":"OSINT-Platform"},timeout=8)
                if rr.status_code==200:
                    repos_info=[{"name":x["name"],"stars":x["stargazers_count"],"lang":x.get("language","")} for x in rr.json()[:5]]
            except Exception: pass
            return {"found":True,"name":d.get("name",""),"bio":d.get("bio",""),
                "location":d.get("location",""),"company":d.get("company",""),
                "repos":d.get("public_repos",0),"followers":d.get("followers",0),
                "following":d.get("following",0),"created_at":d.get("created_at","")[:10],
                "blog":d.get("blog",""),"email":d.get("email",""),
                "avatar":d.get("avatar_url",""),"top_repos":repos_info}
    except Exception: pass
    return {"found":False}

def get_reddit_info(username):
    try:
        r=requests.get(f"https://www.reddit.com/user/{username}/about.json",
            headers={"User-Agent":"OSINT-Platform/1.0"},timeout=10)
        if r.status_code==200:
            d=r.json().get("data",{})
            created=datetime.fromtimestamp(d.get("created_utc",0)).strftime("%Y-%m-%d")
            posts=[]
            try:
                pr=requests.get(f"https://www.reddit.com/user/{username}/submitted.json?limit=5",
                    headers={"User-Agent":"OSINT-Platform/1.0"},timeout=8)
                if pr.status_code==200:
                    for p in pr.json().get("data",{}).get("children",[])[:3]:
                        pd=p.get("data",{})
                        posts.append({"title":pd.get("title","")[:60],"subreddit":pd.get("subreddit","")})
            except Exception: pass
            return {"found":True,"karma":d.get("total_karma",0),"link_karma":d.get("link_karma",0),
                "comment_karma":d.get("comment_karma",0),"created_at":created,
                "is_gold":d.get("is_gold",False),"verified":d.get("verified",False),"recent_posts":posts}
    except Exception: pass
    return {"found":False}

def check_gravatar(email):
    import hashlib
    try:
        email_hash=hashlib.md5(email.lower().strip().encode()).hexdigest()
        r=requests.get(f"https://www.gravatar.com/{email_hash}.json",headers={"User-Agent":"OSINT-Platform"},timeout=8)
        if r.status_code==200:
            d=r.json().get("entry",[{}])[0]
            return {"found":True,"display_name":d.get("displayName",""),
                "profile_url":d.get("profileUrl",""),
                "avatar_url":f"https://www.gravatar.com/avatar/{email_hash}",
                "about_me":d.get("aboutMe",""),"location":d.get("currentLocation",""),
                "accounts":[a.get("name","") for a in d.get("accounts",[])[:5]]}
    except Exception: pass
    return {"found":False}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def cleanup_root_txt():
    for file in BASE_DIR.glob("*.txt"):
        try: file.unlink()
        except Exception: pass

def run_sherlock(username):
    found={}; REPORTS_DIR.mkdir(exist_ok=True); cleanup_root_txt()
    sherlock_sites=[p for p in SOCIAL_PLATFORMS if p["site"] not in DIRECT_CHECK_SITES]
    command=["python","-m","sherlock_project",username,"--print-found","--folderoutput",str(REPORTS_DIR)]
    for p in sherlock_sites: command.extend(["--site",p["site"]])
    try:
        process=subprocess.run(command,cwd=str(BASE_DIR),capture_output=True,text=True,timeout=90)
        output=(process.stdout or "")+"\n"+(process.stderr or "")
        for line in output.splitlines():
            for p in sherlock_sites:
                site=p["site"]
                if site.lower() in line.lower() and ("http://" in line or "https://" in line):
                    urls=re.findall(r"https?://[^\s]+",line)
                    if urls: found[site]=urls[0].strip()
    except Exception: pass
    cleanup_root_txt()
    report_file=REPORTS_DIR/f"{username}.txt"
    if report_file.exists():
        try:
            content=report_file.read_text(encoding="utf-8",errors="ignore")
            for line in content.splitlines():
                for p in sherlock_sites:
                    site=p["site"]
                    if site.lower() in line.lower() and ("http://" in line or "https://" in line):
                        urls=re.findall(r"https?://[^\s]+",line)
                        if urls: found[site]=urls[0].strip()
        except Exception: pass
    return found

def direct_check(username,found):
    for p in SOCIAL_PLATFORMS:
        site=p["site"]
        if site not in DIRECT_CHECK_SITES or site in found: continue
        url=p["url"].format(username)
        try:
            r=requests.get(url,headers=HEADERS,timeout=12,allow_redirects=True)
            if r.status_code==404: continue
            if r.status_code==200:
                if any(sig in r.text.lower() for sig in NOT_FOUND_SIGNALS): continue
                found[site]=url
        except Exception: continue
    return found

def analyze_url(url):
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        soup=BeautifulSoup(r.text,"html.parser")
        title=soup.title.string.strip() if soup.title else "No title"
        text=soup.get_text(separator=" ",strip=True); words=text.split()
        return {"enabled":True,"title":title,"links":len(soup.find_all("a")),"preview":text[:700],"keywords":list(dict.fromkeys(words[:18]))}
    except Exception as e:
        return {"enabled":True,"title":"Error","links":0,"preview":str(e),"keywords":[]}


# ═══════════════════════════════════════════════════════
# BUILD RESULTS
# ═══════════════════════════════════════════════════════
def build_results(username):
    results=[]; found=run_sherlock(username); found=direct_check(username,found)
    github_info=get_github_info(username) if "GitHub" in found else {"found":False}
    reddit_info=get_reddit_info(username) if "Reddit" in found else {"found":False}
    for p in SOCIAL_PLATFORMS:
        site=p["site"]
        if site in found:
            url=found[site].lower(); conf=85; label="Public Presence Detected"
            if "github.com" in url:
                conf=98
                if github_info.get("found"):
                    g=github_info; parts=[]
                    if g.get("name"):      parts.append(g["name"])
                    if g.get("location"):  parts.append(f"📍 {g['location']}")
                    if g.get("repos"):     parts.append(f"{g['repos']} repos")
                    if g.get("followers"): parts.append(f"{g['followers']} followers")
                    if g.get("email"):     parts.append(f"✉ {g['email']}")
                    label=" | ".join(parts) if parts else "Developer Profile Detected"
                else: label="Developer Profile Detected"
            elif "linkedin.com" in url: conf,label=92,"Professional Presence Confirmed"
            elif "t.me" in url:         conf,label=88,"Messaging Profile Detected"
            elif "snapchat.com" in url: conf,label=90,"Snapchat Profile Detected"
            elif "facebook.com" in url: conf,label=88,"Facebook Profile Detected"
            elif "reddit.com" in url:
                conf=90
                if reddit_info.get("found"):
                    r=reddit_info
                    label=f"Karma: {r['karma']:,} | Joined: {r['created_at']}"
                    if r.get("recent_posts"):
                        subs=list(set(p["subreddit"] for p in r["recent_posts"]))
                        label+=f" | r/{', r/'.join(subs[:3])}"
                else: label="Confirmed Public Presence"
            elif any(x in url for x in ["instagram","tiktok","youtube","x.com","twitter"]):
                conf,label=95,"Confirmed Public Presence"
            results.append({"site":site,"url":found[site],"status":"FOUND","confidence":conf,"label":label,"source":"OSINT Verified"})
        else:
            results.append({"site":site,"url":p["url"].format(username),"status":"NOT FOUND","confidence":0,"label":"No Public Evidence Found","source":"OSINT Scan"})
    return results


def build_email_results(email):
    results=[]
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$",email):
        results.append({"site":"Email Format","url":"#","status":"NOT FOUND","confidence":20,"label":"Invalid Email Structure"})
        return results
    domain=email.split("@")[-1].lower()
    disposable=["tempmail.com","guerrillamail.com","10minutemail.com","mailinator.com","throwaway.email","yopmail.com"]
    is_disp=domain in disposable
    results.append({"site":"Email Format","url":"#","status":"FOUND","confidence":100,
        "label":"Valid Email Structure"+(" | ⚠ Disposable Domain" if is_disp else "")})
    public=["gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com","live.com","msn.com"]
    ptype="Public Email Provider" if domain in public else "Custom / Organisation Domain"
    results.append({"site":"Email Provider","url":f"https://{domain}","status":"FOUND",
        "confidence":85 if domain in public else 92,"label":f"{ptype} — {domain}"})
    dns_data=dns_lookup(domain)
    if dns_data:
        mx_list=dns_data.get("MX",[])
        a_list=dns_data.get("A",[])
        mx_info=", ".join(mx_list[:2]) if mx_list else "Not found"
        results.append({"site":"MX Records","url":f"https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{domain}",
            "status":"FOUND","confidence":90,"label":f"Mail servers: {mx_info[:80]}"})
        if a_list:
            results.append({"site":"Domain IP","url":f"https://ipapi.co/{a_list[0]}/",
                "status":"FOUND","confidence":92,"label":f"IP: {', '.join(a_list[:3])}"})
            ip_info=lookup_ip(a_list[0])
            if ip_info:
                results.append({"site":"IP Geolocation","url":f"https://ipapi.co/{ip_info['ip']}/",
                    "status":"FOUND","confidence":88,
                    "label":f"🌍 {ip_info['country']} — {ip_info['city']} | ISP: {ip_info['org']}"})
    gravatar=check_gravatar(email)
    if gravatar.get("found"):
        g=gravatar; label="Gravatar profile found"
        if g.get("display_name"): label+=f" — {g['display_name']}"
        if g.get("location"):     label+=f" | 📍 {g['location']}"
        if g.get("accounts"):     label+=f" | Linked: {', '.join(g['accounts'][:3])}"
        results.append({"site":"Gravatar","url":g.get("profile_url","https://gravatar.com"),
            "status":"FOUND","confidence":92,"label":label})
    else:
        results.append({"site":"Gravatar","url":"https://gravatar.com","status":"NOT FOUND","confidence":60,"label":"No Gravatar profile found"})
    results.append({"site":"WHOIS Domain","url":f"https://who.is/whois/{domain}","status":"FOUND","confidence":85,"label":"WHOIS Lookup Ready"})
    try:
        r=requests.get(f"https://emailrep.io/{email}",headers={"Accept":"application/json","User-Agent":"OSINT-Platform"},timeout=10)
        if r.status_code==200:
            d=r.json(); rep=d.get("reputation","unknown"); sus=d.get("suspicious",False)
            ref=d.get("references",0); tags=d.get("details",{}).get("tags",[])
            conf={"high":95,"medium":80,"low":60}.get(rep,75)
            label=f"Reputation: {rep.upper()} | References: {ref}"
            if sus:  label+=" | ⚠ SUSPICIOUS"
            if tags: label+=f" | Tags: {', '.join(tags[:3])}"
            results.append({"site":"Email Reputation","url":"#","status":"FOUND","confidence":conf,"label":label})
        else:
            results.append({"site":"Email Reputation","url":"#","status":"NOT FOUND","confidence":40,"label":"EmailRep unavailable"})
    except Exception:
        results.append({"site":"Email Reputation","url":"#","status":"NOT FOUND","confidence":40,"label":"EmailRep request failed"})
    hibp_key=os.getenv("HIBP_API_KEY")
    if hibp_key:
        try:
            resp=requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={"hibp-api-key":hibp_key,"User-Agent":"OSINT-Platform"},
                params={"truncateResponse":"false"},timeout=15)
            if resp.status_code==200:
                breaches=resp.json(); n=len(breaches)
                names=", ".join(b.get("Name","") for b in breaches[:4])
                results.append({"site":"HIBP Breach Check","url":"https://haveibeenpwned.com/",
                    "status":"FOUND","confidence":95,"label":f"⚠ {n} Breach(es): {names}"})
            elif resp.status_code==404:
                results.append({"site":"HIBP Breach Check","url":"https://haveibeenpwned.com/",
                    "status":"NOT FOUND","confidence":90,"label":"✅ No known breaches"})
        except Exception:
            results.append({"site":"HIBP Breach Check","url":"#","status":"NOT FOUND","confidence":40,"label":"HIBP failed"})
    else:
        results.append({"site":"HIBP Breach Check","url":"https://haveibeenpwned.com/","status":"NOT FOUND","confidence":50,"label":"Add HIBP_API_KEY in .env for breach data"})
    return results


def build_phone_results(phone):
    results=[]; clean=phone.replace(" ","").replace("-","").replace("(","").replace(")","")
    if clean.startswith("+") and clean[1:].isdigit() and len(clean)>=8:
        results.append({"site":"Phone Format","url":"#","status":"FOUND","confidence":100,"label":"Valid International Format (E.164)"})
    elif clean.isdigit() and len(clean)>=8:
        results.append({"site":"Phone Format","url":"#","status":"FOUND","confidence":80,"label":"Valid Local Format"})
    else:
        results.append({"site":"Phone Format","url":"#","status":"NOT FOUND","confidence":20,"label":"Invalid Phone Structure"})
        return results
    country_codes={
        "+966":("Saudi Arabia","SA",95),"+971":("UAE","AE",90),"+965":("Kuwait","KW",90),
        "+974":("Qatar","QA",90),"+973":("Bahrain","BH",90),"+968":("Oman","OM",90),
        "+1":("USA/Canada","US",88),"+44":("UK","GB",88),"+20":("Egypt","EG",85),
        "+962":("Jordan","JO",88),"+961":("Lebanon","LB",88),"+963":("Syria","SY",85),
        "+964":("Iraq","IQ",85),"+90":("Turkey","TR",85),"+92":("Pakistan","PK",85),
        "+91":("India","IN",85),"+49":("Germany","DE",88),"+33":("France","FR",88),
    }
    country,country_code,conf="Unknown Region","XX",60
    for code,(name,cc,c) in country_codes.items():
        if clean.startswith(code): country,country_code,conf=name,cc,c; break
    results.append({"site":"Country Detection","url":"#","status":"FOUND","confidence":conf,"label":f"🌍 {country} ({country_code})"})
    num_digits=len(clean.lstrip("+"))
    line_type="Mobile" if num_digits in [9,10,12] else "Landline/Unknown"
    results.append({"site":"Number Analysis","url":"#","status":"FOUND","confidence":70,"label":f"Type: {line_type} | Digits: {num_digits}"})
    try:
        r=requests.get(f"https://api.numlookupapi.com/v1/info/{clean}",headers={"User-Agent":"OSINT-Platform"},timeout=8)
        if r.status_code==200:
            d=r.json()
            results.append({"site":"Carrier & Line Type","url":"#","status":"FOUND","confidence":82,
                "label":f"Carrier: {d.get('carrier','Unknown')} | Type: {d.get('line_type','Unknown')} | {d.get('country_name',country)}"})
    except Exception: pass
    wa_num=clean.replace("+","")
    results.append({"site":"WhatsApp","url":f"https://wa.me/{wa_num}","status":"FOUND","confidence":75,"label":f"Direct link → wa.me/{wa_num}"})
    results.append({"site":"Telegram","url":f"https://t.me/+{wa_num}","status":"FOUND","confidence":60,"label":"Telegram link — manual verification"})
    results.append({"site":"Truecaller","url":"https://www.truecaller.com/","status":"FOUND","confidence":65,"label":"Search manually — Truecaller"})
    results.append({"site":"Sync.me","url":"https://sync.me/","status":"FOUND","confidence":60,"label":"Reverse lookup — Sync.me"})
    if country_code in ["SA","AE","KW","QA","BH","OM"]:
        results.append({"site":"Gulf Directory","url":"https://whitepages.ae/","status":"FOUND","confidence":65,"label":f"Gulf directory — {country}"})
    return results


def build_domain_results(domain):
    domain=re.sub(r"https?://","",domain).replace("www.","").strip().strip("/")
    results=[]
    if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",domain):
        results.append({"site":"Domain Format","url":"#","status":"NOT FOUND","confidence":20,"label":"Invalid Domain Structure"})
        return results
    tld=domain.split(".")[-1].upper()
    results.append({"site":"Domain Format","url":f"https://{domain}","status":"FOUND","confidence":100,"label":f"Valid Domain — .{tld} TLD"})
    dns_data=dns_lookup(domain)
    if dns_data.get("A"):
        a_records=dns_data["A"]
        results.append({"site":"A Record (IP)","url":f"https://ipapi.co/{a_records[0]}/",
            "status":"FOUND","confidence":97,"label":f"IP: {', '.join(a_records[:3])}"})
        ip_info=lookup_ip(a_records[0])
        if ip_info:
            results.append({"site":"IP Geolocation","url":f"https://ipapi.co/{ip_info['ip']}/",
                "status":"FOUND","confidence":92,
                "label":f"🌍 {ip_info['country']} — {ip_info['city']} | ISP: {ip_info['org']} | TZ: {ip_info['timezone']}"})
    if dns_data.get("MX"):
        mx=", ".join(dns_data["MX"][:2])
        results.append({"site":"MX Records","url":f"https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{domain}",
            "status":"FOUND","confidence":90,"label":f"Mail servers: {mx[:80]}"})
    if dns_data.get("NS"):
        ns=", ".join(dns_data["NS"][:2])
        results.append({"site":"Nameservers","url":"#","status":"FOUND","confidence":93,"label":f"NS: {ns[:80]}"})
    if dns_data.get("TXT"):
        txt_records=dns_data["TXT"]
        spf=next((t for t in txt_records if "v=spf" in t.lower()),None)
        dmarc=next((t for t in txt_records if "v=dmarc" in t.lower()),None)
        results.append({"site":"SPF Record","url":"#","status":"FOUND" if spf else "NOT FOUND",
            "confidence":88 if spf else 60,
            "label":f"SPF: {spf[:70]}" if spf else "No SPF record — email spoofing possible ⚠"})
        results.append({"site":"DMARC Record","url":"#","status":"FOUND" if dmarc else "NOT FOUND",
            "confidence":88 if dmarc else 60,
            "label":"DMARC policy configured ✅" if dmarc else "No DMARC record ⚠"})
    subdomains=get_subdomains(domain)
    if subdomains:
        results.append({"site":"Subdomains (crt.sh)","url":f"https://crt.sh/?q=%.{domain}",
            "status":"FOUND","confidence":87,
            "label":f"Found {len(subdomains)}: {', '.join(subdomains[:5])}{'...' if len(subdomains)>5 else ''}"})
    else:
        results.append({"site":"Subdomains (crt.sh)","url":f"https://crt.sh/?q=%.{domain}",
            "status":"NOT FOUND","confidence":60,"label":"No subdomains in certificate logs"})
    wayback=check_wayback(domain)
    if wayback.get("available"):
        results.append({"site":"Wayback Machine","url":wayback.get("url",""),
            "status":"FOUND","confidence":88,"label":f"🕰 Archived — Last snapshot: {wayback.get('date','')}"})
    else:
        results.append({"site":"Wayback Machine","url":f"https://web.archive.org/web/*/{domain}",
            "status":"NOT FOUND","confidence":50,"label":"No archived snapshots"})
    urlscan=search_urlscan(domain)
    if urlscan.get("found"):
        label=f"Scans: {urlscan.get('total',0)} | Last: {urlscan.get('last_scan','')[:10]}"
        if urlscan.get("server"):  label+=f" | Server: {urlscan['server']}"
        if urlscan.get("country"): label+=f" | 🌍 {urlscan['country']}"
        results.append({"site":"URLScan.io","url":urlscan.get("scan_url",""),
            "status":"FOUND","confidence":83,"label":label})
    for site,url,conf,label in [
        ("WHOIS Lookup",f"https://who.is/whois/{domain}",88,"Domain registration info"),
        ("SSL Certificate",f"https://www.ssllabs.com/ssltest/analyze.html?d={domain}",83,"SSL/TLS security grade"),
        ("VirusTotal",f"https://www.virustotal.com/gui/domain/{domain}",85,"Malware & reputation check"),
        ("Security Headers",f"https://securityheaders.com/?q={domain}",78,"HTTP security headers"),
        ("Shodan",f"https://www.shodan.io/search?query={domain}",75,"Open ports & services"),
    ]:
        results.append({"site":site,"url":url,"status":"FOUND","confidence":conf,"label":label})
    return results


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@app.get("/report")
def download_report(target:str,search_type:str="username"):
    dispatch={"username":build_results,"email":build_email_results,"phone":build_phone_results,"domain":build_domain_results}
    results=dispatch.get(search_type,build_results)(target)
    filepath=generate_pdf_report(target,search_type,results)
    return FileResponse(filepath,media_type="application/pdf",filename=os.path.basename(filepath))
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    token = login(username.strip(), password)
    if not token:
        return templates.TemplateResponse(request=request, name="login.html",
            context={"error": "اسم المستخدم أو كلمة المرور غلط"}, status_code=401)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, samesite="lax", max_age=60*60*8)
    return response

@app.get("/logout")
def logout_route(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token: logout(token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse(request=request,name="index.html",context={"username":None,"results":[],"report":None,"found_count":0,"notfound_count":0})

@app.post("/",response_class=HTMLResponse)
def search(request:Request,username:str=Form(...),search_type:str=Form("username")):
    username=username.strip()
    if search_type=="username":
        username=username.replace("@","")
    elif search_type=="phone":
        if username.startswith("00"):
            username="+"+username[2:]
    report=None
    if username.startswith("http://") or username.startswith("https://"):
        results=[]; report=analyze_url(username); found_count=notfound_count=0
    else:
        dispatch={"username":build_results,"email":build_email_results,"phone":build_phone_results,"domain":build_domain_results}
        results=dispatch.get(search_type,build_results)(username) or []
        save_search(username,search_type,results)
        found_count=sum(1 for r in results if r["status"]=="FOUND")
        notfound_count=sum(1 for r in results if r["status"]=="NOT FOUND")
    return templates.TemplateResponse(request=request,name="index.html",context={
        "username":username,"search_type":search_type,"results":results,
        "report":report,"found_count":found_count,"notfound_count":notfound_count})
        
@app.get("/saved",response_class=HTMLResponse)
def saved_results(request:Request):
    searches=get_all_searches()
    return templates.TemplateResponse(request=request,name="saved.html",context={"searches":searches})

@app.get("/suggestions")
def suggestions(q:str=""):
    searches=get_all_searches(limit=100)
    seen=[]
    for s in searches:
        if q.lower() in s["target"].lower() and s["target"] not in seen: seen.append(s["target"])
    return {"results":seen[:5]}