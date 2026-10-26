#!/usr/bin/env python3
"""Job Radar: public ATS discovery, conservative qualification and office-commute matching."""
import concurrent.futures
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import smtplib
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
UA = "JobRadarPersonal/1.0 (github.com/dylaneburkey/dylanburkey; personal research)"
ORS_KEY = os.getenv("ORS_API_KEY", "").strip()
SOURCES = [
    ("greenhouse","andurilindustries","Anduril"),
    ("greenhouse","spacex","SpaceX"),
    ("greenhouse","shieldai","Shield AI"),
    ("greenhouse","relativityspace","Relativity Space"),
    ("greenhouse","rocketlab","Rocket Lab"),
    ("greenhouse","formlabs","Formlabs"),
    ("greenhouse","zipline","Zipline"),
    ("greenhouse","hadrian","Hadrian"),
    ("greenhouse","geckorobotics","Gecko Robotics"),
    ("greenhouse","agilityrobotics","Agility Robotics"),
    ("greenhouse","brightmachines","Bright Machines"),
    ("greenhouse","astranis","Astranis"),
    ("greenhouse","saronic","Saronic"),
    ("greenhouse","varda","Varda Space Industries"),
    ("greenhouse","forterra","Forterra"),
    ("greenhouse","machinalabs","Machina Labs"),
    ("greenhouse","skildai","Skild AI"),
    ("greenhouse","saildrone","Saildrone"),
    ("greenhouse","nuro","Nuro"),
    ("greenhouse","boomsupersonic","Boom Supersonic"),
    ("greenhouse","redwoodmaterials","Redwood Materials"),
    ("greenhouse","epicgames","Epic Games"),
    ("greenhouse","figureai","Figure AI"),
    ("greenhouse","atomicmachines","Atomic Machines"),
    ("greenhouse","freeform","Freeform"),
    ("greenhouse","samsara","Samsara"),
    ("lever","anduril","Anduril"),
    ("lever","carbon","Carbon"),
    ("lever","geckorobotics","Gecko Robotics"),
    ("lever","zipline","Zipline"),
    ("lever","astranis","Astranis"),
    ("lever","brightmachines","Bright Machines"),
    ("lever","varda","Varda"),
    ("lever","reliablerobotics","Reliable Robotics"),
    ("lever","nuro","Nuro"),
    ("lever","saronic","Saronic"),
    ("lever","formlabs","Formlabs"),
    ("ashby","physicalintelligence","Physical Intelligence"),
    ("ashby","SkildAI","Skild AI"),
    ("ashby","skildai","Skild AI"),
    ("ashby","Figure","Figure AI"),
    ("ashby","figure","Figure AI"),
    ("ashby","Freeform","Freeform"),
    ("ashby","Hadrian","Hadrian"),
    ("ashby","Saronic","Saronic"),
    ("ashby","Varda","Varda"),
    ("ashby","MachinaLabs","Machina Labs"),
    ("ashby","AtomicMachines","Atomic Machines"),
]
STATE_CODES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi",
    "MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire",
    "NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina",
    "ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania",
    "RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee",
    "TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
    "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming","DC":"District of Columbia","PR":"Puerto Rico"
}
US_STATES = {v.lower():k for k,v in STATE_CODES.items()}

def get_json(url, timeout=22, post=None, headers=None):
    h = {"User-Agent":UA, "Accept":"application/json"}
    if headers: h.update(headers)
    if post is not None: h["Content-Type"]="application/json"
    data = None if post is None else json.dumps(post).encode("utf-8")
    req=urllib.request.Request(url, headers=h, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200: raise ValueError("HTTP "+str(response.status))
        return json.load(response)

def load(name, default):
    try: return json.loads((DATA/name).read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError): return default

def save(name, value):
    (DATA/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)+"\n",encoding="utf-8")

def clean(s):
    s=html.unescape(str(s or ""))
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def normalise(provider, token, company, r):
    if provider=="greenhouse":
        location=(r.get("location") or {}).get("name","")
        url=r.get("absolute_url","")
        description=clean(r.get("content",""))
        posted=r.get("first_published") or r.get("updated_at") or ""
        address=""
        job_id=str(r.get("id") or url)
    elif provider=="lever":
        categories=r.get("categories") or {}
        location=categories.get("location") or ""
        url=r.get("applyUrl") or r.get("hostedUrl") or ""
        description=clean((r.get("descriptionPlain") or "")+" "+(r.get("openingPlain") or ""))
        posted=r.get("createdAt") or ""
        address=""
        job_id=str(r.get("id") or url)
    else:
        location=r.get("location") or ""
        url=r.get("applyUrl") or r.get("jobUrl") or ""
        description=clean(r.get("descriptionPlain") or r.get("descriptionHtml") or "")
        posted=r.get("publishedAt") or ""
        postal=(((r.get("address") or {}).get("postalAddress")) or {})
        street=postal.get("streetAddress") or ""
        city=postal.get("addressLocality") or ""
        region=postal.get("addressRegion") or ""
        address=f"{street}, {city}, {region}".strip(", ") if street else ""
        job_id=str(r.get("id") or url)
    if isinstance(posted,(float,int)):
        posted=dt.datetime.fromtimestamp(posted/1000 if posted>1e11 else posted,dt.timezone.utc).isoformat()
    return {
        "id":hashlib.sha256((provider+":"+token+":"+job_id).encode()).hexdigest()[:18],
        "company":company, "title":clean(r.get("title") or r.get("text")),
        "location":clean(location), "worksite_address":address,
        "description":description[:9000], "url":url, "source":provider.title(),
        "published_at":posted, "source_id":job_id
    }

def fetch_board(source):
    provider, token, company = source
    try:
        if provider=="greenhouse":
            raw=get_json("https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(token)+"/jobs?content=true")
            jobs=raw.get("jobs") or []
        elif provider=="lever":
            jobs=get_json("https://api.lever.co/v0/postings/"+urllib.parse.quote(token)+"?mode=json&limit=1000")
        else:
            raw=get_json("https://api.ashbyhq.com/posting-api/job-board/"+urllib.parse.quote(token)+"?includeCompensation=true")
            jobs=[j for j in raw.get("jobs",[]) if j.get("isListed",True)]
        return [normalise(provider,token,company,j) for j in jobs], None
    except Exception as exc:
        return [], f"{company} / {provider}: {str(exc)[:90]}"

TITLE_INCLUDE=re.compile(r"\b(engineer(?:ing)?|mechanical|manufacturing|industrial|process|production|automation|robotics|controls|quality|reliability|test|hardware|design|operations|continuous improvement|manufacturability)\b",re.I)
TITLE_EXCLUDE=re.compile(r"\b(senior|sr\.?|staff|principal|director|head of|vp|vice president|chief|lead|manager|architect|intern(?:ship)?|co[- ]?op|technician|research scientist|software engineer|data engineer)\b",re.I)
EXPERIENCE_TOO_HIGH=re.compile(r"\b(?:minimum of|at least|requires?|must have)\s+(?:a\s+)?(?:minimum of\s+)?([3-9]|1\d)\+?\s+years?\b|\b([3-9]|1\d)\+\s+years?\s+(?:of\s+)?(?:relevant|professional|industry|work|engineering)\s+experience",re.I)
SKILLS={
    "Manufacturing":r"\bmanufactur(?:ing|ability)|production line|shop floor\b",
    "Mechanical design":r"\bmechanical design|solidworks|cad|dfm|dfa\b",
    "Process improvement":r"\blean|six sigma|kaizen|continuous improvement|root cause\b",
    "Automation / controls":r"\bautomation|plc|controls|sensors|robotic\b",
    "Data / Python":r"\bpython|sql|machine learning|data analysis|analytics\b",
    "Quality / testing":r"\bquality|test engineering|validation|reliability|inspection\b"
}

def rank_job(j):
    t=j["title"]; body=j["description"]
    if not TITLE_INCLUDE.search(t) or TITLE_EXCLUDE.search(t): return None
    if re.search(r"\b(software developer|backend|frontend|full.stack|electrical only)\b",t,re.I): return None
    if re.search(r"\b(remote only|worldwide|anywhere)\b",j["location"],re.I): return None
    if re.search(r"\b(2026 graduates? only|graduating in 2026 only)\b",body,re.I): return None
    if re.search(r"\b(start(?:ing)?|begin(?:ning)?)\s+(?:in\s+)?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?)\s+2027\b",body,re.I): return None
    if EXPERIENCE_TOO_HIGH.search(body): return None
    reasons=[label for label,rx in SKILLS.items() if re.search(rx,t+" "+body,re.I)]
    early=bool(re.search(r"\b(new grad|new graduate|university grad|university graduate|early career|entry.level|graduate engineer|2027)\b",t+" "+body[:3000],re.I))
    if re.search(r"\b(II|III|IV|V|2|3|4)\b",t,re.I) and not early: return None
    score=40+ min(30,len(reasons)*5)
    if early: score+=19
    if re.search(r"\b(mechanical|manufacturing|process|automation|industrial|production|quality)\b",t,re.I): score+=9
    if re.search(r"\b(2027|july 2027|summer 2027)\b",t+" "+body,re.I): score+=4
    return min(score,99),reasons[:5],("2027 / early-career signal" if early else "Start date not confirmed")

# Parse job location conservatively; no city-name substring match without a state.
def city_state(raw):
    raw=clean(raw).replace("–",",").replace("|",",")
    raw=re.sub(r"\s+\(.*?\)","",raw)
    parts=[p.strip() for p in raw.split(",")]
    if len(parts)<2: return None
    city=parts[0]
    state=parts[1]
    if len(parts)>2 and parts[-1].lower() in ("united states","usa","us"): pass
    state=re.sub(r"[^a-zA-Z ]","",state).strip()
    state_code=state.upper() if state.upper() in STATE_CODES else US_STATES.get(state.lower())
    if not state_code or len(city)<2: return None
    return city, state_code

def km(a,b):
    lat1,lon1=a; lat2,lon2=b
    dlat=math.radians(lat2-lat1); dlon=math.radians(lon2-lon1)
    h=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 6371*2*math.asin(math.sqrt(h))

GEOCACHE=load("geocache.json",{})
GEO_CHANGED=False
def geo_city(city,state):
    global GEO_CHANGED
    key="city:"+city.lower().strip()+","+state
    if key in GEOCACHE: return GEOCACHE[key]
    url="https://geocoding-api.open-meteo.com/v1/search?"+urllib.parse.urlencode({"name":city,"count":20,"language":"en","format":"json"})
    result=None
    try:
        items=get_json(url).get("results") or []
        for item in items:
            if item.get("country_code")=="US" and item.get("admin1","").lower()==STATE_CODES[state].lower():
                result={"lat":item["latitude"],"lon":item["longitude"],"precision":"city"}
                break
    except Exception: pass
    if result is not None:
        GEOCACHE[key]=result;GEO_CHANGED=True
    return result

def geo_street(address):
    global GEO_CHANGED
    key="street:"+address.strip().lower()
    if key in GEOCACHE:return GEOCACHE[key]
    # US Census address geocoding (US mainland street addresses, not approximate city matches)
    simplified=re.sub(r"\b(Suite|Ste|Floor|Fl)\.?\s*[\w-]+\b","",address,flags=re.I)
    url="https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?"+urllib.parse.urlencode({"address":simplified,"benchmark":"Public_AR_Current","vintage":"Current_Current","format":"json"})
    result=None
    try:
        matches=((get_json(url,timeout=30).get("result") or {}).get("addressMatches") or [])
        if matches:
            c=matches[0]["coordinates"]
            result={"lat":float(c["y"]),"lon":float(c["x"]),"precision":"street"}
    except Exception:pass
    if result:
        GEOCACHE[key]=result;GEO_CHANGED=True
    return result

ROUTES=load("route_cache.json",{})
ROUTE_CHANGED=False
def route_minutes(a,b):
    global ROUTE_CHANGED
    key=":".join(f"{v:.4f}" for v in (a["lat"],a["lon"],b["lat"],b["lon"]))
    if key in ROUTES:return ROUTES[key]
    if not ORS_KEY:return None
    try:
        data=get_json("https://api.openrouteservice.org/v2/directions/driving-car/json",
            post={"coordinates":[[a["lon"],a["lat"]],[b["lon"],b["lat"]]]},
            headers={"Authorization":ORS_KEY},timeout=25)
        minute=round(data["routes"][0]["summary"]["duration"]/60,1)
        ROUTES[key]=minute;ROUTE_CHANGED=True
        return minute
    except Exception:return None

def match_office(job, offices, offices_by_city):
    loc=city_state(job["location"])
    if not loc: return None
    city,state=loc
    job_geo=geo_street(job["worksite_address"]) if job["worksite_address"] else None
    if not job_geo: job_geo=geo_city(city,state)
    candidates=[]
    if job_geo:
        for office in offices:
            office_city=geo_city(office["city"],office["state"])
            if office_city and km((job_geo["lat"],job_geo["lon"]),(office_city["lat"],office_city["lon"]))<48:
                candidates.append((km((job_geo["lat"],job_geo["lon"]),(office_city["lat"],office_city["lon"])),office))
        candidates.sort(key=lambda x:x[0])
        candidates=[o for _,o in candidates[:5]]
    else:
        candidates=offices_by_city.get((city.lower(),state),[])
    if not candidates:
        candidates=offices_by_city.get((city.lower(),state),[])
    if not candidates: return None
    best=None
    for office in candidates:
        start=geo_street(office["address"])
        if not start: start=geo_city(office["city"],office["state"])
        mins=route_minutes(start,job_geo) if start and job_geo else None
        strict=bool(mins is not None and mins<=20 and start["precision"]=="street" and job_geo["precision"]=="street")
        if (mins is not None and mins>20 and start["precision"]=="street" and job_geo["precision"]=="street"): continue
        status="verified" if strict else "review"
        score=(0 if strict else 1, mins if mins is not None else 1e6)
        candidate={"office":office["city"]+", "+office["state"],"office_address":office["address"],
                   "commute_min":mins,"commute_status":status,
                   "location_precision":job_geo["precision"] if job_geo else "unknown"}
        if best is None or score < best[0]: best=(score,candidate)
    return best[1] if best else None

def send_alerts(new_jobs):
    host=os.getenv("SMTP_HOST"); username=os.getenv("SMTP_USER"); password=os.getenv("SMTP_PASSWORD")
    to=os.getenv("ALERT_TO")
    if not (host and username and password and to and new_jobs):return
    port=int(os.getenv("SMTP_PORT") or "587")
    msg=EmailMessage()
    msg["From"]=os.getenv("ALERT_FROM",username)
    msg["To"]=to
    msg["Subject"]=f"Job Radar: {len(new_jobs)} newly discovered matches"
    lines=["New engineering openings found:\n"]
    for j in new_jobs[:30]:
        lines.append(f"{j['company']} — {j['title']}\n{j['location']} | {j['commute_status']} | {j['commute_min'] or 'Unknown'} min\n{j['url']}\n")
    lines.append("More: https://github.com/dylaneburkey/dylanburkey/tree/main/job-radar")
    msg.set_content("\n".join(lines))
    try:
        with smtplib.SMTP(host,port,timeout=20) as smtp:
            smtp.starttls();smtp.login(username,password);smtp.send_message(msg)
    except Exception as exc: print("Email failed:",exc)

def main():
    offices=json.loads((BASE/"offices.json").read_text())
    office_map={}
    for o in offices: office_map.setdefault((o["city"].lower(),o["state"]),[]).append(o)
    previous=load("jobs.json",{})
    old={j["id"]:j for j in previous.get("jobs",[])}
    raw=[];errors=[];successes=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for jobs,error in pool.map(fetch_board,SOURCES):
            if error: errors.append(error)
            else:successes+=1;raw.extend(jobs)
    by_url={}
    for job in raw:
        if job["url"]:
            by_url[job["url"].split("?")[0].rstrip("/")]=job
    print(f"Boards working {successes}/{len(SOURCES)}; total postings {len(by_url)}")
    candidates=[]
    for job in by_url.values():
        ranking=rank_job(job)
        if not ranking:continue
        score,reasons,start=ranking
        job["match_score"]=score;job["match_reasons"]=reasons;job["start_fit"]=start
        candidates.append(job)
    candidates.sort(key=lambda j:(-j["match_score"],j["company"]))
    matched=[]; matched_urls=set()
    for i,job in enumerate(candidates):
        nearby=match_office(job,offices,office_map)
        if not nearby:continue
        job.update(nearby)
        # Only confirmed >20 minute routes are excluded. A city-center measurement
        # cannot prove that an employer's actual worksite is outside the 20-minute limit.
        if job["commute_status"]=="verified" and job["commute_min"]>20: continue
        prev=old.get(job["id"],{})
        job["first_seen"]=prev.get("first_seen") or NOW.isoformat()
        job.pop("description",None)
        matched.append(job);matched_urls.add(job["url"])
    matched.sort(key=lambda j:(j["commute_status"]!="verified",-j["match_score"],j["first_seen"]),reverse=False)
    new=[j for j in matched if j["id"] not in old]
    # Keep previous matching jobs if individual ATS boards are temporarily unreachable.
    if successes>=1:
        fresh={j["id"]:j for j in matched}
        failed_providers={(e.split(" / ")[0]).lower() for e in errors}
        for j in old.values():
            if j["id"] not in fresh and j["company"].lower() in failed_providers:
                j["stale"]=True;fresh[j["id"]]=j
        matched=list(fresh.values())
    else:
        matched=list(old.values())
    save("jobs.json",{
        "updated_at":NOW.isoformat(),
        "scanned_sources":successes,
        "configured_sources":len(SOURCES),
        "total_postings_scanned":len(by_url),
        "qualified_before_location":len(candidates),
        "verified_count":sum(j.get("commute_status")=="verified" for j in matched),
        "review_count":sum(j.get("commute_status")=="review" for j in matched),
        "route_api_configured":bool(ORS_KEY),
        "jobs":matched[:500]
    })
    if GEO_CHANGED: save("geocache.json",GEOCACHE)
    if ROUTE_CHANGED: save("route_cache.json",ROUTES)
    send_alerts(new)
    print(f"Retained {len(matched)}; new {len(new)}; source errors {len(errors)}")
    for e in errors[:10]:print("Source unavailable:",e)

if __name__=="__main__":
    main()
