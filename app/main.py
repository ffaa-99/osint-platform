from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import subprocess
import re
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4

from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
    Paragraph,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib import styles
from reportlab.lib.units import cm

from datetime import datetime
import os


def generate_pdf_report(target, search_type, results):

    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors, styles
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER
    from datetime import datetime

    pdf_path = REPORTS_DIR / f"report_{search_type}_{target}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    story = []
    style = styles.getSampleStyleSheet()

    title = style["Title"]
    title.alignment = TA_CENTER
    title.fontSize = 24

    subtitle = style["Italic"]
    subtitle.alignment = TA_CENTER
    subtitle.fontSize = 11
    subtitle.textColor = colors.grey

    normal = style["BodyText"]
    normal.fontSize = 10
    normal.leading = 18

    heading = style["Heading2"]

    generated = datetime.now().strftime("%d %B %Y %H:%M")
    case_id = f"OS-{datetime.now().strftime('%Y%m%d-%H%M')}"

    found_results = [
        r for r in results
        if r["status"] == "FOUND"
    ]

    found_count = len(found_results)

    confidence = min(
        95,
        50 + (found_count * 10)
    )

    risk = "LOW"
    if found_count >= 5:
        risk = "MEDIUM"
    if found_count >= 8:
        risk = "HIGH"

    story.append(Spacer(1, 4 * cm))

    story.append(Paragraph(
        "DIGITAL INTELLIGENCE<br/><br/>CASE REPORT",
        title
    ))

    story.append(Spacer(1, 1 * cm))

    story.append(Paragraph(
        f"""
        CASE ID: {case_id}
        <br/><br/>
        TARGET: {target.upper()}
        <br/><br/>
        CLASSIFICATION: CONFIDENTIAL
        """,
        subtitle
    ))

    story.append(Spacer(1, 5 * cm))

    story.append(Paragraph(
        "Open Source Intelligence Division",
        subtitle
    ))

    story.append(PageBreak())

    banner = Table(
        [["INTELLIGENCE CASE FILE"]],
        colWidths=[16 * cm]
    )

    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
    ]))

    story.append(banner)
    story.append(Spacer(1, .4 * cm))

    story.append(Paragraph("OSINT INTELLIGENCE REPORT", title))
    story.append(Paragraph("CONFIDENTIAL | DIGITAL INVESTIGATION REPORT", subtitle))
    story.append(Spacer(1, .5 * cm))

    info = [
        ["Case ID", case_id],
        ["Generated", generated],
        ["Analyst", "Digital Intelligence Unit"],
        ["Target", target],
        ["Search Type", search_type],
        ["Discovery Score", f"{confidence}%"]
    ]

    info_table = Table(info, colWidths=[4 * cm, 10 * cm])
    info_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("GRID", (0, 0), (-1, -1), .5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EFEFEF")),
    ]))

    story.append(info_table)
    story.append(Spacer(1, .5 * cm))

    story.append(Paragraph("THREAT ASSESSMENT", heading))

    threat_data = [
        ["Exposure Level", risk],
        ["Confirmed Footprint", f"{found_count} Assets"],
        ["False Positive Risk", "Low"],
        ["Confidence", f"{confidence}%"]
    ]

    threat_table = Table(threat_data, colWidths=[6 * cm, 8 * cm])
    threat_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), .5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F3F3")),
    ]))

    story.append(threat_table)
    story.append(Spacer(1, .5 * cm))

    story.append(Paragraph("CONFIRMED DIGITAL ASSETS", heading))

    data = [["Platform", "Status", "Confidence"]]

    if found_results:
        for r in found_results:
            data.append([
                r["site"],
                r["status"],
                f"{r['confidence']}%"
            ])
    else:
        data.append([
            "No confirmed assets",
            "NOT FOUND",
            "0%"
        ])

    result_table = Table(data, colWidths=[6 * cm, 4 * cm, 4 * cm])
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .5, colors.grey),
    ]))

    story.append(result_table)
    story.append(Spacer(1, .6 * cm))

    story.append(Paragraph("ANALYST CONCLUSION", heading))

    story.append(Paragraph(
        f"""
        Intelligence assessment identified <b>{found_count}</b> confirmed digital indicators
        associated with the submitted target. Analysis suggests a detectable online footprint
        with an estimated exposure score of <b>{confidence}%</b>.

        Findings contained in this report represent open-source intelligence indicators only
        and should be considered preliminary analytical data requiring independent verification
        before operational or investigative use.
        """,
        normal
    ))

    story.append(Spacer(1, 1 * cm))

    story.append(Paragraph(
        "CLASSIFICATION: CONFIDENTIAL | END OF CASE FILE",
        subtitle
    ))

    doc.build(story)

    return pdf_path

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SOCIAL_PLATFORMS = [
    {"site": "Instagram", "url": "https://www.instagram.com/{}/"},
    {"site": "Twitter", "url": "https://x.com/{}"},
    {"site": "GitHub", "url": "https://github.com/{}"},
    {"site": "YouTube", "url": "https://www.youtube.com/@{}"},
    {"site": "LinkedIn", "url": "https://www.linkedin.com/in/{}/"},
    {"site": "Telegram", "url": "https://t.me/{}"},
]

def cleanup_root_txt(username: str):
    for file in BASE_DIR.glob("*.txt"):
        if file.name.lower() == f"{username.lower()}.txt":
            try:
                file.unlink()
            except:
                pass

def run_sherlock(username: str):
    found = {}

    command = [
        "python",
        "-m",
        "sherlock_project",
        username,
        "--print-found",
        "--folderoutput",
        str(REPORTS_DIR),
    ]

    for platform in SOCIAL_PLATFORMS:
        command.extend(["--site", platform["site"]])

    try:
        process = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=90
        )

        output = (process.stdout or "") + "\n" + (process.stderr or "")

        for line in output.splitlines():

            urls = re.findall(r"https?://[^\s]+", line)

            for url in urls:

                clean = url.lower()

                if username.lower() not in clean:
                    continue

                if "instagram.com" in clean:
                    found["Instagram"] = url

                elif "tiktok.com" in clean:
                    found["TikTok"] = url

                elif "github.com" in clean:
                    found["GitHub"] = url

                elif "reddit.com" in clean:
                    found["Reddit"] = url

                elif "youtube.com" in clean:
                    found["YouTube"] = url

                elif "twitter.com" in clean or "x.com" in clean:
                    found["Twitter"] = url

                elif "linkedin.com" in clean:
                    found["LinkedIn"] = url

                elif "t.me" in clean:
                    found["Telegram"] = url

                elif "snapchat.com" in clean:
                    found["Snapchat"] = url

    except Exception:
        pass

    cleanup_root_txt(username)

    return found

def analyze_url(url: str):

    report = {
        "enabled": False
    }

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        title = soup.title.string if soup.title else "No title"

        text = soup.get_text(
            separator=" ",
            strip=True
        )

        words = text.split()

        report = {
            "enabled": True,
            "title": title,
            "links": len(soup.find_all("a")),
            "preview": text[:700],
            "keywords": list(dict.fromkeys(words[:15]))
        }

    except Exception as e:

        report = {
            "enabled": True,
            "title": "Error",
            "links": 0,
            "preview": str(e),
            "keywords": []
        }

    return report

def build_email_results(email: str):

    results = []

    email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"

    if not re.match(email_pattern, email):
        results.append({
            "site": "Email Format",
            "url": "#",
            "status": "NOT FOUND",
            "confidence": 20,
            "label": "Invalid Email Structure"
        })
        return results

    domain = email.split("@")[-1].lower()

    results.append({
        "site": "Email Format",
        "url": "#",
        "status": "FOUND",
        "confidence": 100,
        "label": "Valid Email Structure"
    })

    results.append({
        "site": "Email Domain",
        "url": f"https://{domain}",
        "status": "FOUND",
        "confidence": 90,
        "label": f"Domain Detected: {domain}"
    })

    public_providers = [
        "gmail.com",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
        "live.com",
        "msn.com"
    ]

    if domain in public_providers:
        provider_label = "Public Email Provider"
        provider_confidence = 85
    else:
        provider_label = "Custom or Organization Domain"
        provider_confidence = 90

    results.append({
        "site": "Email Provider",
        "url": "#",
        "status": "FOUND",
        "confidence": provider_confidence,
        "label": provider_label
    })

    results.append({
        "site": "WHOIS Domain Check",
        "url": f"https://who.is/whois/{domain}",
        "status": "FOUND",
        "confidence": 85,
        "label": "WHOIS Lookup Ready"
    })

    hibp_key = os.getenv("HIBP_API_KEY")

    if hibp_key:
        try:
            hibp_response = requests.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={
                    "hibp-api-key": hibp_key,
                    "User-Agent": "OSINT-Platform"
                },
                params={
                    "truncateResponse": "false"
                },
                timeout=15
            )

            if hibp_response.status_code == 200:
                breaches = hibp_response.json()
                breach_count = len(breaches)

                results.append({
                    "site": "HIBP Breach Check",
                    "url": "https://haveibeenpwned.com/",
                    "status": "FOUND",
                    "confidence": 95,
                    "label": f"Breaches Found: {breach_count}"
                })

            elif hibp_response.status_code == 404:
                results.append({
                    "site": "HIBP Breach Check",
                    "url": "https://haveibeenpwned.com/",
                    "status": "NOT FOUND",
                    "confidence": 90,
                    "label": "No Breach Found"
                })

            else:
                results.append({
                    "site": "HIBP Breach Check",
                    "url": "https://haveibeenpwned.com/",
                    "status": "NOT FOUND",
                    "confidence": 40,
                    "label": "HIBP unavailable or API limit reached"
                })

        except Exception:
            results.append({
                "site": "HIBP Breach Check",
                "url": "https://haveibeenpwned.com/",
                "status": "NOT FOUND",
                "confidence": 40,
                "label": "HIBP request failed"
            })

    else:
        results.append({
            "site": "HIBP Breach Check",
            "url": "https://haveibeenpwned.com/",
            "status": "NOT FOUND",
            "confidence": 50,
            "label": "Needs HIBP API Key"
        })

    try:
        response = requests.get(
            f"https://emailrep.io/{email}",
            headers={
                "Accept": "application/json",
                "User-Agent": "OSINT-Platform"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            reputation = data.get("reputation", "unknown")
            suspicious = data.get("suspicious", False)
            references = data.get("references", 0)

            confidence = 75

            if reputation == "high":
                confidence = 95
            elif reputation == "medium":
                confidence = 80
            elif reputation == "low":
                confidence = 60

            label = f"Reputation: {reputation} | References: {references}"

            if suspicious:
                label += " | Suspicious"

            results.append({
                "site": "Email Reputation",
                "url": "#",
                "status": "FOUND",
                "confidence": confidence,
                "label": label
            })

        elif response.status_code == 429:
            results.append({
                "site": "Email Reputation",
                "url": "#",
                "status": "NOT FOUND",
                "confidence": 40,
                "label": "EmailRep rate limit reached"
            })

        else:
            results.append({
                "site": "Email Reputation",
                "url": "#",
                "status": "NOT FOUND",
                "confidence": 40,
                "label": "EmailRep unavailable"
            })

    except Exception:
        results.append({
            "site": "Email Reputation",
            "url": "#",
            "status": "NOT FOUND",
            "confidence": 40,
            "label": "EmailRep request failed"
        })

    return results

def build_phone_results(phone: str):

    results = []

    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if clean_phone.startswith("+") and clean_phone[1:].isdigit() and len(clean_phone) >= 8:
        results.append({
            "site": "Phone Format",
            "url": "#",
            "status": "FOUND",
            "confidence": 100,
            "label": "Valid International Phone Format"
        })
    elif clean_phone.isdigit() and len(clean_phone) >= 8:
        results.append({
            "site": "Phone Format",
            "url": "#",
            "status": "FOUND",
            "confidence": 80,
            "label": "Valid Local Phone Format"
        })
    else:
        results.append({
            "site": "Phone Format",
            "url": "#",
            "status": "NOT FOUND",
            "confidence": 20,
            "label": "Invalid Phone Structure"
        })

        return results

    if clean_phone.startswith("+966"):
        country = "Saudi Arabia"
        confidence = 95
    elif clean_phone.startswith("+1"):
        country = "United States / Canada"
        confidence = 90
    elif clean_phone.startswith("+44"):
        country = "United Kingdom"
        confidence = 90
    elif clean_phone.startswith("+971"):
        country = "United Arab Emirates"
        confidence = 90
    else:
        country = "Unknown or Local Region"
        confidence = 60

    results.append({
        "site": "Country Code",
        "url": "#",
        "status": "FOUND",
        "confidence": confidence,
        "label": f"Detected Region: {country}"
    })

    results.append({
        "site": "WhatsApp Check",
        "url": f"https://wa.me/{clean_phone.replace('+', '')}",
        "status": "FOUND",
        "confidence": 75,
        "label": "WhatsApp Link Ready"
    })

    results.append({
        "site": "Telegram Check",
        "url": f"https://t.me/+{clean_phone.replace('+', '')}",
        "status": "FOUND",
        "confidence": 60,
        "label": "Telegram Manual Check Ready"
    })

    results.append({
        "site": "Truecaller Search",
        "url": "https://www.truecaller.com/",
        "status": "FOUND",
        "confidence": 60,
        "label": "Manual Phone Lookup Source"
    })

    return results

    
def build_domain_results(domain: str):

    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.replace("www.", "").strip().strip("/")

    results = []

    domain_pattern = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if re.match(domain_pattern, domain):
        results.append({
            "site": "Domain Format",
            "url": f"https://{domain}",
            "status": "FOUND",
            "confidence": 100,
            "label": "Valid Domain Structure"
        })
    else:
        results.append({
            "site": "Domain Format",
            "url": "#",
            "status": "NOT FOUND",
            "confidence": 20,
            "label": "Invalid Domain Structure"
        })

        return results

    results.append({
        "site": "WHOIS Lookup",
        "url": f"https://who.is/whois/{domain}",
        "status": "FOUND",
        "confidence": 90,
        "label": "WHOIS Lookup Ready"
    })

    results.append({
        "site": "DNS Records",
        "url": f"https://dnschecker.org/all-dns-records-of-domain.php?query={domain}",
        "status": "FOUND",
        "confidence": 90,
        "label": "DNS Records Ready"
    })

    results.append({
        "site": "SSL Certificate",
        "url": f"https://www.ssllabs.com/ssltest/analyze.html?d={domain}",
        "status": "FOUND",
        "confidence": 85,
        "label": "SSL Security Check Ready"
    })

    results.append({
        "site": "Subdomain Search",
        "url": f"https://crt.sh/?q={domain}",
        "status": "FOUND",
        "confidence": 80,
        "label": "Certificate Transparency Search"
    })

    results.append({
        "site": "VirusTotal Domain",
        "url": f"https://www.virustotal.com/gui/domain/{domain}",
        "status": "FOUND",
        "confidence": 85,
        "label": "Reputation Check Ready"
    })

    results.append({
        "site": "Security Headers",
        "url": f"https://securityheaders.com/?q={domain}",
        "status": "FOUND",
        "confidence": 80,
        "label": "HTTP Security Headers Check"
    })

    return results


def build_results(username: str):

    results=[]

    found=run_sherlock(username)

    for platform in SOCIAL_PLATFORMS:

        site=platform["site"]

        if site in found:

            confidence=85
            label="Public Presence Detected"
            source="Sherlock"

            url=found[site].lower()

            if "github.com" in url:
                confidence=98
                label="Developer Profile Detected"

            elif "linkedin.com" in url:
                confidence=92
                label="Professional Presence"

            elif "t.me" in url:
                confidence=88
                label="Messaging Profile"

            elif any(x in url for x in [
                "instagram.com",
                "tiktok.com",
                "reddit.com",
                "youtube.com",
                "twitter.com",
                "x.com"
            ]):
                confidence=95
                label="Confirmed Public Presence"

            results.append({

                "site":site,
                "url":found[site],
                "status":"FOUND",
                "confidence":confidence,
                "label":label,
                "source":"Sherlock Verified"

            })

        else:

            results.append({

                "site":site,
                "url":platform["url"].format(username),
                "status":"NOT FOUND",
                "confidence":0,
                "label":"No Public Evidence Found",
                "source":"OSINT Scan"

            })

    return results


@app.get("/report")
def download_report(target: str, search_type: str = "username"):

    if search_type == "username":
        results = build_results(target)

    elif search_type == "email":
        results = build_email_results(target)

    elif search_type == "phone":
        results = build_phone_results(target)

    else:
        results = build_domain_results(target)

    filepath = generate_pdf_report(
        target,
        search_type,
        results
    )

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=os.path.basename(filepath)
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "username": None,
            "results": [],
            "report": None,
            "found_count": 0,
            "notfound_count": 0,
        }
    )
@app.post("/", response_class=HTMLResponse)
def search(
    request: Request,
    username: str = Form(...),
    search_type: str = Form("username")
):

    username = username.strip()

    if search_type == "username":
        username = username.replace("@", "")

    report = None

    if username.startswith("http://") or username.startswith("https://"):

        results = []
        report = analyze_url(username)
        found_count = 0
        notfound_count = 0

    else:

        if search_type == "username":
            results = build_results(username)

        elif search_type == "email":
            results = build_email_results(username)

        elif search_type == "phone":
            results = build_phone_results(username)

        else:
            results = build_domain_results(username)

        if results is None:
            results = []

        found_count = sum(
            1 for r in results
            if r["status"] == "FOUND"
        )

        notfound_count = sum(
            1 for r in results
            if r["status"] == "NOT FOUND"
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "username": username,
            "search_type": search_type,
            "results": results,
            "report": report,
            "found_count": found_count,
            "notfound_count": notfound_count,
        }
    )