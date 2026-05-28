from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import re
import requests
import random
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
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
app = FastAPI()
BASE_DIR  = Path(__file__).resolve().parent.parent
APP_DIR   = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

def cleanup_reports():
    now = datetime.now()
    for file in REPORTS_DIR.glob("*"):
        try:
            if now - datetime.fromtimestamp(file.stat().st_mtime) > timedelta(hours=24):
                file.unlink()
        except Exception:
            pass
cleanup_reports()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
]

# المنصات + طريقة الفحص لكل واحدة
SOCIAL_PLATFORMS = [
    {"site": "Instagram",   "url": "https://www.instagram.com/{}/",       "method": "http"},
    {"site": "Twitter",     "url": "https://x.com/{}",                    "method": "api"},
    {"site": "Snapchat",    "url": "https://www.snapchat.com/add/{}",     "method": "http"},
    {"site": "Facebook",    "url": "https://www.facebook.com/{}",         "method": "http"},
    {"site": "GitHub",      "url": "https://github.com/{}",               "method": "api"},
    {"site": "YouTube",     "url": "https://www.youtube.com/@{}",         "method": "http"},
    {"site": "LinkedIn",    "url": "https://www.linkedin.com/in/{}/",     "method": "http"},
    {"site": "Telegram",    "url": "https://t.me/{}",                     "method": "http"},
    {"site": "TikTok",      "url": "https://www.tiktok.com/@{}",          "method": "http"},
    {"site": "Reddit",      "url": "https://www.reddit.com/user/{}",      "method": "api"},
    {"site": "Pastebin",    "url": "https://pastebin.com/u/{}",           "method": "http"},
    {"site": "Gravatar",    "url": "https://gravatar.com/{}",             "method": "api"},
]

# إشارات "مو موجود" لكل منصة
NOT_FOUND_SIGNALS = {
    "Instagram":  ["page not found", "sorry, this page", "pagenotfound"],
    "Twitter":    ["this account doesn't exist", "account suspended", "page doesn't exist", "sorry, that page doesn't exist", "this account has been suspended"],
    "Snapchat":   ["page not found", "no user found", "this page"],
    "Facebook":   ["page not found", "content not found", "this page isn't available", "this content isn't available", "this page isn't available right now", "المحتوى غير متوفر"],
    "YouTube":    ["404", "page not found", "this page is not available"],
    "LinkedIn":   ["page not found", "this page doesn't exist", "profile not found"],
    "Telegram":   ["page not found", "if you have telegram"],
    "TikTok":     ["couldn't find this account", "page not found", "user not found"],
    "Reddit":     ["page not found", "nobody on reddit goes by that name"],
    "GitHub":     ["not found", "page not found"],
    "Pastebin":   ["not found", "unknown user", "no pastes"],
}

# إشارات "موجود" — أدق من مجرد 200
FOUND_SIGNALS = {
    "Instagram":  ["og:type", "profile", "followers"],
    "Twitter":    ["og:title", "twitter:title", "tweets"],
    "Snapchat":   ["snapcode", "bitmoji", "add me on snapchat"],
    "Facebook":   ["og:title", "timeline", "fb_dtsg"],
    "YouTube":    ["subscriberCountText", "channelId", "subscribers"],
    "LinkedIn":   ["og:title", "experience", "linkedin"],
    "Telegram":   ["tgme_page", "tgme_page_title", "telegram"],
    "TikTok":     ["uniqueId", "followerCount", "tiktok"],
    "Reddit":     ["totalKarma", "created", "redditor"],
    "GitHub":     ["repositories", "followers", "contributions"],
    "Pastebin":   ["public pastes", "pastebin", "recent pastes"],
}


# ─────────────────────────────────────────
# APIs مجانية — دقيقة 100%
# ─────────────────────────────────────────
def api_check_twitter(username):
    # نستخدم nitter كـ proxy مفتوح المصدر — أدق من x.com مباشرة
    mirrors = [
        f"https://nitter.poast.org/{username}",
        f"https://nitter.privacydev.net/{username}",
    ]
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    for url in mirrors:
        try:
            r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
            if r.status_code == 404:
                return False, 0, ""
            if r.status_code == 200:
                body = r.text.lower()
                not_found = ["user not found", "no results", "this account doesn't exist"]
                if any(s in body for s in not_found):
                    return False, 0, ""
                if "tweets" in body or "following" in body or "followers" in body:
                    return True, 90, "Twitter/X Profile Detected"
        except Exception:
            continue
    return False, 0, ""


def api_check_github(username):
    try:
        r = requests.get(
            f"https://api.github.com/users/{username}",
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "OSINT-Platform"},
            timeout=8
        )
        if r.status_code == 200:
            d = r.json()
            parts = []
            if d.get("name"):      parts.append(d["name"])
            if d.get("location"):  parts.append(f"📍 {d['location']}")
            if d.get("public_repos"): parts.append(f"{d['public_repos']} repos")
            if d.get("followers"): parts.append(f"{d['followers']} followers")
            if d.get("email"):     parts.append(f"✉ {d['email']}")
            label = " | ".join(parts) if parts else "Developer Profile"
            return True, 98, label
        return False, 0, ""
    except Exception:
        return False, 0, ""

def api_check_reddit(username):
    try:
        r = requests.get(
            f"https://www.reddit.com/user/{username}/about.json",
            headers={"User-Agent": "OSINT-Platform/2.0"},
            timeout=8
        )
        if r.status_code == 200:
            d = r.json().get("data", {})
            karma   = d.get("total_karma", 0)
            created = datetime.fromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d")
            label   = f"Karma: {karma:,} | Joined: {created}"
            return True, 95, label
        return False, 0, ""
    except Exception:
        return False, 0, ""

    except Exception:
        return False, 0, ""

def api_check_gravatar(username):
    try:
        email_hash = hashlib.md5(username.lower().strip().encode()).hexdigest()
        r = requests.get(
            f"https://www.gravatar.com/{email_hash}.json",
            headers={"User-Agent": "OSINT-Platform"},
            timeout=8
        )
        if r.status_code == 200:
            d = r.json().get("entry", [{}])[0]
            label = "Gravatar Profile Found"
            if d.get("displayName"): label += f" — {d['displayName']}"
            if d.get("currentLocation"): label += f" | 📍 {d['currentLocation']}"
            accounts = [a.get("name","") for a in d.get("accounts", [])[:3]]
            if accounts: label += f" | Linked: {', '.join(accounts)}"
            profile_url = d.get("profileUrl", f"https://gravatar.com/{username}")
            return True, 92, label, profile_url
        return False, 0, "", ""
    except Exception:
        return False, 0, "", ""


# ─────────────────────────────────────────
# HTTP Check — لكل المنصات الأخرى
# ─────────────────────────────────────────
def http_check(site, url):
    headers = {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer":         "https://www.google.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        # 404 = مو موجود قطعاً
        if r.status_code == 404:
            return False, 0, ""

        # المنصة محجبت الطلب — نتجاهل بدل false positive
        if r.status_code in [401, 403, 429, 999]:
            return False, 0, ""

        if r.status_code == 200:
            body = r.text.lower()

            # فحص negative أولاً
            for sig in NOT_FOUND_SIGNALS.get(site, []):
                if sig in body:
                    return False, 0, ""

            # فحص positive
            pos = FOUND_SIGNALS.get(site, [])
            if pos:
                hits = sum(1 for s in pos if s in body)
                if hits >= 1:
                    conf = min(60 + hits * 10, 95)
                    return True, conf, "Public Profile Detected"
                return False, 0, ""

            return True, 75, "Public Profile Detected"

    except Exception:
        pass
    return False, 0, ""


# ─────────────────────────────────────────
# فحص منصة واحدة
# ─────────────────────────────────────────
def check_platform(p, username):
    site   = p["site"]
    url    = p["url"].format(username)
    method = p["method"]

    # skip = Facebook وأمثاله يعيدون توجيه لنتائج خاطئة — نعطي رابط فقط
    if method == "skip":
        return {
            "site": site, "url": url,
            "status": "NOT FOUND", "confidence": 0,
            "label": "فحص يدوي مطلوب — اضغط الرابط للتحقق",
            "source": "Manual Check Required",
        }

    if method == "api":
        if site == "Twitter":
            found, conf, label = api_check_twitter(username)
        elif site == "GitHub":
            found, conf, label = api_check_github(username)
        elif site == "Reddit":
            found, conf, label = api_check_reddit(username)
        elif site == "Gravatar":
            result = api_check_gravatar(username)
            found, conf, label = result[0], result[1], result[2]
            if found and result[3]:
                url = result[3]
        else:
            found, conf, label = False, 0, ""
    else:
        found, conf, label = http_check(site, url)

    if not label and found:
        label = "Public Presence Detected"

    return {
        "site":       site,
        "url":        url,
        "status":     "FOUND" if found else "NOT FOUND",
        "confidence": conf,
        "label":      label if found else "No Public Evidence Found",
        "source":     "OSINT Direct",
    }


# ─────────────────────────────────────────
# EMAIL CHAINING — يربط الهوية تلقائياً
# ─────────────────────────────────────────
def chain_email_intel(email, source_site):
    chain_results = []
    if not email or "@" not in email:
        return chain_results
    domain = email.split("@")[-1].lower()

    # Gravatar
    try:
        email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
        r = requests.get(f"https://www.gravatar.com/{email_hash}.json",
                         headers={"User-Agent": "OSINT-Platform"}, timeout=6)
        if r.status_code == 200:
            d = r.json().get("entry", [{}])[0]
            label = f"🔗 Email: {email}"
            if d.get("displayName"):      label += f" | Name: {d['displayName']}"
            if d.get("currentLocation"):  label += f" | 📍 {d['currentLocation']}"
            accounts = [a.get("name","") for a in d.get("accounts",[])[:3]]
            if accounts: label += f" | Linked: {', '.join(accounts)}"
            chain_results.append({
                "site": "Gravatar (Auto-Chain)",
                "url": f"https://www.gravatar.com/avatar/{email_hash}",
                "status": "FOUND", "confidence": 92,
                "label": label, "source": f"Chained from {source_site}",
            })
    except Exception:
        pass

    # HIBP
    hibp_key = os.getenv("HIBP_API_KEY")
    if hibp_key:
        try:
            r = requests.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={"hibp-api-key": hibp_key, "User-Agent": "OSINT-Platform"},
                params={"truncateResponse": "false"}, timeout=10)
            if r.status_code == 200:
                breaches = r.json()
                names = ", ".join(b.get("Name","") for b in breaches[:4])
                chain_results.append({
                    "site": "HIBP (Auto-Chain)",
                    "url": "https://haveibeenpwned.com/",
                    "status": "FOUND", "confidence": 95,
                    "label": f"🔗 Email: {email} | ⚠ {len(breaches)} تسريب: {names}",
                    "source": f"Chained from {source_site}",
                })
            elif r.status_code == 404:
                chain_results.append({
                    "site": "HIBP (Auto-Chain)",
                    "url": "https://haveibeenpwned.com/",
                    "status": "FOUND", "confidence": 90,
                    "label": f"🔗 Email: {email} | ✅ لا تسريبات",
                    "source": f"Chained from {source_site}",
                })
        except Exception:
            pass

    # Email Domain Info
    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX",
                         headers={"User-Agent": "OSINT-Platform"}, timeout=6)
        if r.status_code == 200:
            answers = r.json().get("Answer", [])
            if answers:
                mx = answers[0].get("data","")
                chain_results.append({
                    "site": "Email Domain (Auto-Chain)",
                    "url": f"https://who.is/whois/{domain}",
                    "status": "FOUND", "confidence": 85,
                    "label": f"🔗 Domain: {domain} | MX: {mx[:50]}",
                    "source": f"Chained from {source_site}",
                })
    except Exception:
        pass

    return chain_results


# ─────────────────────────────────────────
# BUILD USERNAME RESULTS — متوازي + Chaining
# ─────────────────────────────────────────
def build_results(username):
    results_map = {}

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(check_platform, p, username): p for p in SOCIAL_PLATFORMS}
        for future in as_completed(futures, timeout=20):
            try:
                result = future.result()
                results_map[result["site"]] = result
            except Exception:
                p = futures[future]
                results_map[p["site"]] = {
                    "site": p["site"], "url": p["url"].format(username),
                    "status": "NOT FOUND", "confidence": 0,
                    "label": "No Public Evidence Found", "source": "OSINT Direct",
                }

    # Email Chaining من GitHub
    chained = []
    github_result = results_map.get("GitHub", {})
    if github_result.get("status") == "FOUND":
        label = github_result.get("label", "")
        email_match = re.search(r"✉\s*([\w\.\-]+@[\w\.\-]+\.\w+)", label)
        if email_match:
            chained = chain_email_intel(email_match.group(1), "GitHub")

    # النتائج الأساسية + Chained
    final = [results_map.get(p["site"], {
        "site": p["site"], "url": p["url"].format(username),
        "status": "NOT FOUND", "confidence": 0,
        "label": "No Public Evidence Found", "source": "OSINT Direct",
    }) for p in SOCIAL_PLATFORMS]

    if chained:
        final.extend(chained)

    return final


# ─────────────────────────────────────────
# أدوات مساعدة
# ─────────────────────────────────────────
def lookup_ip(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", headers={"User-Agent": "OSINT-Platform"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            if "error" not in d:
                return {"ip": d.get("ip", ip), "country": d.get("country_name", "Unknown"),
                        "city": d.get("city", "Unknown"), "region": d.get("region", "Unknown"),
                        "org": d.get("org", "Unknown"), "timezone": d.get("timezone", "Unknown"),
                        "latitude": d.get("latitude", 0), "longitude": d.get("longitude", 0)}
    except Exception:
        pass
    return {}

def get_subdomains(domain):
    subdomains = set()
    try:
        r = requests.get(f"https://crt.sh/?q=%.{domain}&output=json", headers={"User-Agent": "OSINT-Platform"}, timeout=12)
        if r.status_code == 200:
            for entry in r.json()[:50]:
                for sub in entry.get("name_value", "").split("\n"):
                    sub = sub.strip().lower()
                    if sub.endswith(f".{domain}") and "*" not in sub:
                        subdomains.add(sub)
    except Exception:
        pass
    return sorted(list(subdomains))[:20]

def check_wayback(domain):
    try:
        r = requests.get(f"http://archive.org/wayback/available?url={domain}", headers={"User-Agent": "OSINT-Platform"}, timeout=8)
        if r.status_code == 200:
            snap = r.json().get("archived_snapshots", {}).get("closest", {})
            if snap.get("available"):
                ts = snap.get("timestamp", "")
                return {"available": True, "url": snap.get("url", ""),
                        "date": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts}
    except Exception:
        pass
    return {"available": False}

def dns_lookup(domain):
    results = {}
    for rtype in ["A", "MX", "TXT", "NS"]:
        try:
            r = requests.get(f"https://dns.google/resolve?name={domain}&type={rtype}",
                             headers={"User-Agent": "OSINT-Platform"}, timeout=6)
            if r.status_code == 200:
                answers = r.json().get("Answer", [])
                if answers:
                    results[rtype] = [a.get("data", "") for a in answers[:5]]
        except Exception:
            pass
    return results

def search_urlscan(domain):
    try:
        r = requests.get(f"https://urlscan.io/api/v1/search/?q=domain:{domain}&size=5",
                         headers={"User-Agent": "OSINT-Platform"}, timeout=8)
        if r.status_code == 200:
            rl = r.json().get("results", [])
            if rl:
                latest = rl[0]
                return {"found": True, "total": r.json().get("total", 0),
                        "last_scan": latest.get("task", {}).get("time", ""),
                        "scan_url": f"https://urlscan.io/result/{latest.get('task', {}).get('uuid', '')}/",
                        "country": latest.get("page", {}).get("country", ""),
                        "server": latest.get("page", {}).get("server", ""),
                        "ip": latest.get("page", {}).get("ip", "")}
    except Exception:
        pass
    return {"found": False}

def check_gravatar(email):
    try:
        email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
        r = requests.get(f"https://www.gravatar.com/{email_hash}.json", headers={"User-Agent": "OSINT-Platform"}, timeout=6)
        if r.status_code == 200:
            d = r.json().get("entry", [{}])[0]
            return {"found": True, "display_name": d.get("displayName", ""),
                    "profile_url": d.get("profileUrl", ""),
                    "avatar_url": f"https://www.gravatar.com/avatar/{email_hash}",
                    "about_me": d.get("aboutMe", ""), "location": d.get("currentLocation", ""),
                    "accounts": [a.get("name", "") for a in d.get("accounts", [])[:5]]}
    except Exception:
        pass
    return {"found": False}

def analyze_url(url):
    try:
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title"
        text = soup.get_text(separator=" ", strip=True)
        words = text.split()
        return {"enabled": True, "title": title, "links": len(soup.find_all("a")),
                "preview": text[:700], "keywords": list(dict.fromkeys(words[:18]))}
    except Exception as e:
        return {"enabled": True, "title": "Error", "links": 0, "preview": str(e), "keywords": []}


# ─────────────────────────────────────────
# EMAIL RESULTS
# ─────────────────────────────────────────
def build_email_results(email):
    results = []
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        results.append({"site": "Email Format", "url": "#", "status": "NOT FOUND", "confidence": 20, "label": "Invalid Email Structure"})
        return results
    domain = email.split("@")[-1].lower()
    disposable = ["tempmail.com","guerrillamail.com","10minutemail.com","mailinator.com","throwaway.email","yopmail.com"]
    is_disp = domain in disposable
    results.append({"site": "Email Format", "url": "#", "status": "FOUND", "confidence": 100,
                    "label": "Valid Email Structure" + (" | ⚠ Disposable Domain" if is_disp else "")})
    public = ["gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com","live.com","msn.com"]
    ptype  = "Public Email Provider" if domain in public else "Custom / Organisation Domain"
    results.append({"site": "Email Provider", "url": f"https://{domain}", "status": "FOUND",
                    "confidence": 85 if domain in public else 92, "label": f"{ptype} — {domain}"})
    dns_data = dns_lookup(domain)
    if dns_data:
        mx_list = dns_data.get("MX", [])
        a_list  = dns_data.get("A",  [])
        mx_info = ", ".join(mx_list[:2]) if mx_list else "Not found"
        results.append({"site": "MX Records", "url": f"https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{domain}",
                        "status": "FOUND", "confidence": 90, "label": f"Mail servers: {mx_info[:80]}"})
        if a_list:
            results.append({"site": "Domain IP", "url": f"https://ipapi.co/{a_list[0]}/",
                            "status": "FOUND", "confidence": 92, "label": f"IP: {', '.join(a_list[:3])}"})
            ip_info = lookup_ip(a_list[0])
            if ip_info:
                results.append({"site": "IP Geolocation", "url": f"https://ipapi.co/{ip_info['ip']}/",
                                "status": "FOUND", "confidence": 88,
                                "label": f"🌍 {ip_info['country']} — {ip_info['city']} | ISP: {ip_info['org']}"})
    gravatar = check_gravatar(email)
    if gravatar.get("found"):
        g = gravatar
        label = "Gravatar profile found"
        if g.get("display_name"): label += f" — {g['display_name']}"
        if g.get("location"):     label += f" | 📍 {g['location']}"
        if g.get("accounts"):     label += f" | Linked: {', '.join(g['accounts'][:3])}"
        results.append({"site": "Gravatar", "url": g.get("profile_url", "https://gravatar.com"),
                        "status": "FOUND", "confidence": 92, "label": label})
    else:
        results.append({"site": "Gravatar", "url": "https://gravatar.com", "status": "NOT FOUND",
                        "confidence": 60, "label": "No Gravatar profile found"})
    results.append({"site": "WHOIS Domain", "url": f"https://who.is/whois/{domain}",
                    "status": "FOUND", "confidence": 85, "label": "WHOIS Lookup Ready"})
    try:
        r = requests.get(f"https://emailrep.io/{email}",
                         headers={"Accept": "application/json", "User-Agent": "OSINT-Platform"}, timeout=8)
        if r.status_code == 200:
            d   = r.json()
            rep = d.get("reputation", "unknown")
            sus = d.get("suspicious", False)
            ref = d.get("references", 0)
            tags = d.get("details", {}).get("tags", [])
            conf = {"high": 95, "medium": 80, "low": 60}.get(rep, 75)
            label = f"Reputation: {rep.upper()} | References: {ref}"
            if sus:  label += " | ⚠ SUSPICIOUS"
            if tags: label += f" | Tags: {', '.join(tags[:3])}"
            results.append({"site": "Email Reputation", "url": "#", "status": "FOUND", "confidence": conf, "label": label})
        else:
            results.append({"site": "Email Reputation", "url": "#", "status": "NOT FOUND", "confidence": 40, "label": "EmailRep unavailable"})
    except Exception:
        results.append({"site": "Email Reputation", "url": "#", "status": "NOT FOUND", "confidence": 40, "label": "EmailRep request failed"})
    hibp_key = os.getenv("HIBP_API_KEY")
    if hibp_key:
        try:
            resp = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                                headers={"hibp-api-key": hibp_key, "User-Agent": "OSINT-Platform"},
                                params={"truncateResponse": "false"}, timeout=12)
            if resp.status_code == 200:
                breaches = resp.json()
                names    = ", ".join(b.get("Name", "") for b in breaches[:4])
                results.append({"site": "HIBP Breach Check", "url": "https://haveibeenpwned.com/",
                                "status": "FOUND", "confidence": 95, "label": f"⚠ {len(breaches)} Breach(es): {names}"})
            elif resp.status_code == 404:
                results.append({"site": "HIBP Breach Check", "url": "https://haveibeenpwned.com/",
                                "status": "NOT FOUND", "confidence": 90, "label": "✅ No known breaches"})
        except Exception:
            results.append({"site": "HIBP Breach Check", "url": "#", "status": "NOT FOUND", "confidence": 40, "label": "HIBP failed"})
    else:
        results.append({"site": "HIBP Breach Check", "url": "https://haveibeenpwned.com/",
                        "status": "NOT FOUND", "confidence": 50, "label": "Add HIBP_API_KEY in .env for breach data"})
    return results


# ─────────────────────────────────────────
# PHONE RESULTS
# ─────────────────────────────────────────
def build_phone_results(phone):
    results = []
    clean = phone.replace(" ","").replace("-","").replace("(","").replace(")","")
    if clean.startswith("+") and clean[1:].isdigit() and len(clean) >= 8:
        results.append({"site": "Phone Format", "url": "#", "status": "FOUND", "confidence": 100, "label": "Valid International Format (E.164)"})
    elif clean.isdigit() and len(clean) >= 8:
        results.append({"site": "Phone Format", "url": "#", "status": "FOUND", "confidence": 80, "label": "Valid Local Format"})
    else:
        results.append({"site": "Phone Format", "url": "#", "status": "NOT FOUND", "confidence": 20, "label": "Invalid Phone Structure"})
        return results
    country_codes = {
        "+966":("Saudi Arabia","SA",95), "+971":("UAE","AE",90), "+965":("Kuwait","KW",90),
        "+974":("Qatar","QA",90), "+973":("Bahrain","BH",90), "+968":("Oman","OM",90),
        "+1":("USA/Canada","US",88), "+44":("UK","GB",88), "+20":("Egypt","EG",85),
        "+962":("Jordan","JO",88), "+961":("Lebanon","LB",88), "+963":("Syria","SY",85),
        "+964":("Iraq","IQ",85), "+90":("Turkey","TR",85), "+92":("Pakistan","PK",85),
        "+91":("India","IN",85), "+49":("Germany","DE",88), "+33":("France","FR",88),
    }
    country, country_code, conf = "Unknown Region", "XX", 60
    for code, (name, cc, c) in country_codes.items():
        if clean.startswith(code):
            country, country_code, conf = name, cc, c
            break
    results.append({"site": "Country Detection", "url": "#", "status": "FOUND", "confidence": conf, "label": f"🌍 {country} ({country_code})"})
    num_digits = len(clean.lstrip("+"))
    line_type  = "Mobile" if num_digits in [9, 10, 12] else "Landline/Unknown"
    results.append({"site": "Number Analysis", "url": "#", "status": "FOUND", "confidence": 70, "label": f"Type: {line_type} | Digits: {num_digits}"})
    wa_num = clean.replace("+", "")
    results.append({"site": "WhatsApp",  "url": f"https://wa.me/{wa_num}", "status": "FOUND", "confidence": 75, "label": f"Direct link → wa.me/{wa_num}"})
    results.append({"site": "Telegram",  "url": f"https://t.me/+{wa_num}", "status": "FOUND", "confidence": 60, "label": "Telegram link — manual verification"})
    results.append({"site": "Truecaller","url": "https://www.truecaller.com/", "status": "FOUND", "confidence": 65, "label": "Search manually — Truecaller"})
    results.append({"site": "Sync.me",   "url": "https://sync.me/", "status": "FOUND", "confidence": 60, "label": "Reverse lookup — Sync.me"})
    if country_code in ["SA","AE","KW","QA","BH","OM"]:
        results.append({"site": "Gulf Directory", "url": "https://whitepages.ae/", "status": "FOUND", "confidence": 65, "label": f"Gulf directory — {country}"})
    return results


# ─────────────────────────────────────────
# DOMAIN RESULTS
# ─────────────────────────────────────────
def build_domain_results(domain):
    domain = re.sub(r"https?://", "", domain).replace("www.", "").strip().strip("/")
    results = []
    if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
        results.append({"site": "Domain Format", "url": "#", "status": "NOT FOUND", "confidence": 20, "label": "Invalid Domain Structure"})
        return results
    tld = domain.split(".")[-1].upper()
    results.append({"site": "Domain Format", "url": f"https://{domain}", "status": "FOUND", "confidence": 100, "label": f"Valid Domain — .{tld} TLD"})
    dns_data = dns_lookup(domain)
    if dns_data.get("A"):
        a_records = dns_data["A"]
        results.append({"site": "A Record (IP)", "url": f"https://ipapi.co/{a_records[0]}/",
                        "status": "FOUND", "confidence": 97, "label": f"IP: {', '.join(a_records[:3])}"})
        ip_info = lookup_ip(a_records[0])
        if ip_info:
            results.append({"site": "IP Geolocation", "url": f"https://ipapi.co/{ip_info['ip']}/",
                            "status": "FOUND", "confidence": 92,
                            "label": f"🌍 {ip_info['country']} — {ip_info['city']} | ISP: {ip_info['org']} | TZ: {ip_info['timezone']}"})
    if dns_data.get("MX"):
        mx = ", ".join(dns_data["MX"][:2])
        results.append({"site": "MX Records", "url": f"https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{domain}",
                        "status": "FOUND", "confidence": 90, "label": f"Mail servers: {mx[:80]}"})
    if dns_data.get("NS"):
        ns = ", ".join(dns_data["NS"][:2])
        results.append({"site": "Nameservers", "url": "#", "status": "FOUND", "confidence": 93, "label": f"NS: {ns[:80]}"})
    if dns_data.get("TXT"):
        txt_records = dns_data["TXT"]
        spf   = next((t for t in txt_records if "v=spf"   in t.lower()), None)
        dmarc = next((t for t in txt_records if "v=dmarc" in t.lower()), None)
        results.append({"site": "SPF Record",   "url": "#",
                        "status": "FOUND" if spf else "NOT FOUND", "confidence": 88 if spf else 60,
                        "label": f"SPF: {spf[:70]}" if spf else "No SPF record — email spoofing possible ⚠"})
        results.append({"site": "DMARC Record", "url": "#",
                        "status": "FOUND" if dmarc else "NOT FOUND", "confidence": 88 if dmarc else 60,
                        "label": "DMARC policy configured ✅" if dmarc else "No DMARC record ⚠"})
    subdomains = get_subdomains(domain)
    if subdomains:
        results.append({"site": "Subdomains (crt.sh)", "url": f"https://crt.sh/?q=%.{domain}",
                        "status": "FOUND", "confidence": 87,
                        "label": f"Found {len(subdomains)}: {', '.join(subdomains[:5])}{'...' if len(subdomains)>5 else ''}"})
    else:
        results.append({"site": "Subdomains (crt.sh)", "url": f"https://crt.sh/?q=%.{domain}",
                        "status": "NOT FOUND", "confidence": 60, "label": "No subdomains in certificate logs"})
    wayback = check_wayback(domain)
    if wayback.get("available"):
        results.append({"site": "Wayback Machine", "url": wayback.get("url", ""),
                        "status": "FOUND", "confidence": 88, "label": f"🕰 Archived — Last snapshot: {wayback.get('date', '')}"})
    else:
        results.append({"site": "Wayback Machine", "url": f"https://web.archive.org/web/*/{domain}",
                        "status": "NOT FOUND", "confidence": 50, "label": "No archived snapshots"})
    urlscan = search_urlscan(domain)
    if urlscan.get("found"):
        label = f"Scans: {urlscan.get('total',0)} | Last: {urlscan.get('last_scan','')[:10]}"
        if urlscan.get("server"):  label += f" | Server: {urlscan['server']}"
        if urlscan.get("country"): label += f" | 🌍 {urlscan['country']}"
        results.append({"site": "URLScan.io", "url": urlscan.get("scan_url", ""),
                        "status": "FOUND", "confidence": 83, "label": label})
    for site, url, conf, label in [
        ("WHOIS Lookup",    f"https://who.is/whois/{domain}",                              88, "Domain registration info"),
        ("SSL Certificate", f"https://www.ssllabs.com/ssltest/analyze.html?d={domain}",   83, "SSL/TLS security grade"),
        ("VirusTotal",      f"https://www.virustotal.com/gui/domain/{domain}",             85, "Malware & reputation check"),
        ("Security Headers",f"https://securityheaders.com/?q={domain}",                   78, "HTTP security headers"),
        ("Shodan",          f"https://www.shodan.io/search?query={domain}",                75, "Open ports & services"),
    ]:
        results.append({"site": site, "url": url, "status": "FOUND", "confidence": conf, "label": label})
    return results


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@app.get("/report")
def download_report(target: str, search_type: str = "username"):
    dispatch = {"username": build_results, "email": build_email_results,
                "phone": build_phone_results, "domain": build_domain_results}
    results  = dispatch.get(search_type, build_results)(target)
    filepath = generate_pdf_report(target, search_type, results)
    return FileResponse(filepath, media_type="application/pdf", filename=os.path.basename(filepath))

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

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html",
                                      context={"username": None, "results": [], "report": None,
                                               "found_count": 0, "notfound_count": 0})

@app.post("/", response_class=HTMLResponse)
def search(request: Request, username: str = Form(...), search_type: str = Form("username")):
    username = username.strip()
    if search_type == "username":
        username = username.replace("@", "")
    elif search_type == "phone":
        if username.startswith("00"):
            username = "+" + username[2:]
    report = None
    if username.startswith("http://") or username.startswith("https://"):
        results = []; report = analyze_url(username); found_count = notfound_count = 0
    else:
        dispatch = {"username": build_results, "email": build_email_results,
                    "phone": build_phone_results, "domain": build_domain_results}
        results      = dispatch.get(search_type, build_results)(username) or []
        save_search(username, search_type, results)
        found_count    = sum(1 for r in results if r["status"] == "FOUND")
        notfound_count = sum(1 for r in results if r["status"] == "NOT FOUND")
    return templates.TemplateResponse(request=request, name="index.html",
                                      context={"username": username, "search_type": search_type,
                                               "results": results, "report": report,
                                               "found_count": found_count, "notfound_count": notfound_count})

@app.get("/saved", response_class=HTMLResponse)
def saved_results(request: Request):
    searches = get_all_searches()
    return templates.TemplateResponse(request=request, name="saved.html", context={"searches": searches})

@app.get("/suggestions")
def suggestions(q: str = ""):
    searches = get_all_searches(limit=100)
    seen = []
    for s in searches:
        if q.lower() in s["target"].lower() and s["target"] not in seen:
            seen.append(s["target"])
    return {"results": seen[:5]}

    # ─────────────────────────────────────────
# IMAGE ANALYSIS
# ─────────────────────────────────────────
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io

def get_exif_data(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_raw = img._getexif()
        if not exif_raw:
            return {}
        return {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_raw.items()}
    except Exception:
        return {}

def get_gps_coords(exif_data):
    gps_info = exif_data.get("GPSInfo")
    if not gps_info:
        return None
    gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
    def to_degrees(val):
        d, m, s = val
        return float(d) + float(m)/60 + float(s)/3600
    try:
        lat = to_degrees(gps["GPSLatitude"])
        lon = to_degrees(gps["GPSLongitude"])
        if gps.get("GPSLatitudeRef") == "S": lat = -lat
        if gps.get("GPSLongitudeRef") == "W": lon = -lon
        return {"lat": round(lat, 6), "lon": round(lon, 6)}
    except Exception:
        return None
def reverse_geocode(lat, lon):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "OSINT-Platform/1.0"},
            timeout=8
        )
        if r.status_code == 200:
            d = r.json()
            addr = d.get("address", {})
            return {
                "display": d.get("display_name", ""),
                "road":    addr.get("road", ""),
                "city":    addr.get("city") or addr.get("town") or addr.get("village", ""),
                "state":   addr.get("state", ""),
                "country": addr.get("country", ""),
                "postcode":addr.get("postcode", ""),
                "country_code": addr.get("country_code", "").upper(),
            }
    except Exception:
        pass
    return {}
def analyze_image(image_bytes, filename=""):
    result = {
        "filename": filename, "gps": None, "map_url": None,
        "camera": {}, "datetime": None, "dimensions": None,
        "format": None, "size_kb": round(len(image_bytes)/1024, 1),
        "ai_indicators": [], "ai_score": 0, "exif_found": False,
    }
    try:
        img = Image.open(io.BytesIO(image_bytes))
        result["dimensions"] = f"{img.width} × {img.height}"
        result["format"] = img.format or filename.split(".")[-1].upper()
    except Exception:
        pass
    exif = get_exif_data(image_bytes)
    if exif:
        result["exif_found"] = True
        coords = get_gps_coords(exif)
        if coords:
            result["gps"] = coords
            result["map_url"] = f"https://maps.google.com/?q={coords['lat']},{coords['lon']}"
            result["location"] = reverse_geocode(coords["lat"], coords["lon"])
        for field in ["Make","Model","LensModel","Software"]:
            if field in exif:
                result["camera"][field] = str(exif[field])
        for field in ["DateTimeOriginal","DateTime","DateTimeDigitized"]:
            if field in exif:
                result["datetime"] = str(exif[field])
                break
    indicators = []
    ai_score = 0
    if not exif:
        indicators.append("No EXIF metadata (common in AI-generated images)")
        ai_score += 30
    software = str(exif.get("Software","")).lower()
    for tool in ["stable diffusion","midjourney","dall-e","firefly","ai","generated"]:
        if tool in software:
            indicators.append(f"Software tag contains AI reference: {software}")
            ai_score += 50
            break
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.width % 64 == 0 and img.height % 64 == 0:
            indicators.append("Dimensions are multiples of 64 (common in AI models)")
            ai_score += 15
        if img.width == img.height:
            indicators.append("Square dimensions (common AI output ratio)")
            ai_score += 10
    except Exception:
        pass
    result["ai_indicators"] = indicators
    result["ai_score"] = min(ai_score, 95)
    if ai_score >= 60:
        result["ai_verdict"] = "LIKELY AI-GENERATED"
        result["ai_verdict_color"] = "#ef4444"
    elif ai_score >= 30:
        result["ai_verdict"] = "POSSIBLY AI-GENERATED"
        result["ai_verdict_color"] = "#f59e0b"
    else:
        result["ai_verdict"] = "LIKELY AUTHENTIC"
        result["ai_verdict_color"] = "#22c55e"
    return result

from fastapi import UploadFile, File

@app.get("/image-analysis", response_class=HTMLResponse)
def image_analysis_page(request: Request):
    return templates.TemplateResponse(request=request, name="image_analysis.html",
                                      context={"result": None, "error": None})

@app.post("/image-analysis", response_class=HTMLResponse)
async def image_analysis_submit(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            return templates.TemplateResponse(request=request, name="image_analysis.html",
                                              context={"result": None, "error": "File too large (max 10MB)"})
        allowed = ["image/jpeg","image/png","image/webp","image/tiff"]
        if image.content_type not in allowed:
            return templates.TemplateResponse(request=request, name="image_analysis.html",
                                              context={"result": None, "error": "Unsupported format. Use JPG, PNG, WEBP, TIFF"})
        result = analyze_image(image_bytes, image.filename or "")
        return templates.TemplateResponse(request=request, name="image_analysis.html",
                                          context={"result": result, "error": None})
    except Exception as e:
        return templates.TemplateResponse(request=request, name="image_analysis.html",
                                          context={"result": None, "error": str(e)})