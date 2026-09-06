#!/usr/bin/env python3
"""
build_sih_deck.py
=================
Generates the official SIH 2025 Idea Presentation PPTX and PDF from the template
SIH-ppt-idea.pptx according to all Smart India Hackathon constraints:
- Exactly 6 slides (Slide 7 deleted)
- Template formatting, layout, colors, logos, and fonts preserved 100%
- Bullets only, no paragraphs
- Methodology rendered as a native vector shape flow diagram on Slide 3
- Native PDF export via macOS Microsoft PowerPoint
"""

import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
import xml.sax.saxutils

def xml_escape(text: str) -> str:
    if not text:
        return ""
    return xml.sax.saxutils.escape(str(text))


SOURCE_PPTX = "SIH-ppt-idea.pptx"
TARGET_PPTX = "SIH2025-IDEA-Presentation-Format.pptx"
TARGET_PDF = "SIH2025-IDEA-Presentation-Format.pdf"

# DrawingML / PresentationML namespaces
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def make_bullet_p(bold_prefix: str, text: str, sz: int = 2000, bullet_char: str = "•") -> str:
    """Generate a single DrawingML bullet paragraph with optional bold lead-in."""
    bold_run = ""
    if bold_prefix:
        bold_run = f"""<a:r>
  <a:rPr lang="en-US" sz="{sz}" b="1" dirty="0">
    <a:solidFill><a:srgbClr val="0F243E"/></a:solidFill>
    <a:latin typeface="Arial" pitchFamily="34" charset="0"/>
    <a:cs typeface="Arial" pitchFamily="34" charset="0"/>
  </a:rPr>
  <a:t>{xml_escape(bold_prefix)} </a:t>
</a:r>"""

    return f"""<a:p>
  <a:pPr marL="342900" indent="-342900" algn="just">
    <a:buFont typeface="Arial" panose="020B0604020202020204" pitchFamily="34" charset="0"/>
    <a:buChar char="{bullet_char}"/>
  </a:pPr>
  {bold_run}
  <a:r>
    <a:rPr lang="en-US" sz="{sz}" dirty="0">
      <a:solidFill><a:srgbClr val="333333"/></a:solidFill>
      <a:latin typeface="Arial" pitchFamily="34" charset="0"/>
      <a:cs typeface="Arial" pitchFamily="34" charset="0"/>
    </a:rPr>
    <a:t>{xml_escape(text)}</a:t>
  </a:r>
</a:p>"""

def make_header_p(text: str, sz: int = 2400) -> str:
    """Generate a section header paragraph."""
    return f"""<a:p>
  <a:pPr marL="0" algn="l">
    <a:buNone/>
  </a:pPr>
  <a:r>
    <a:rPr lang="en-US" sz="{sz}" b="1" u="sng" dirty="0">
      <a:solidFill><a:srgbClr val="0070C0"/></a:solidFill>
      <a:latin typeface="Arial" pitchFamily="34" charset="0"/>
      <a:cs typeface="Arial" pitchFamily="34" charset="0"/>
    </a:rPr>
    <a:t>{xml_escape(text)}</a:t>
  </a:r>
</a:p>"""

def create_flow_node(sp_id, name, line1, line2, x, y, cx, cy, fill_color="F0F6FB", border_color="0070C0"):
    """Create a native DrawingML rounded rectangle node for flowchart."""
    l2_run = ""
    if line2:
        l2_run = f"""<a:p>
  <a:pPr algn="ctr"/>
  <a:r>
    <a:rPr lang="en-US" sz="1100" dirty="0">
      <a:solidFill><a:srgbClr val="334155"/></a:solidFill>
      <a:latin typeface="Arial" pitchFamily="34" charset="0"/>
    </a:rPr>
    <a:t>{xml_escape(line2)}</a:t>
  </a:r>
</a:p>"""

    return f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr>
    <p:cNvPr id="{sp_id}" name="{name}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm>
      <a:off x="{x}" y="{y}"/>
      <a:ext cx="{cx}" cy="{cy}"/>
    </a:xfrm>
    <a:prstGeom prst="roundRect">
      <a:avLst><a:gd name="adj" fmla="val 12000"/></a:avLst>
    </a:prstGeom>
    <a:solidFill><a:srgbClr val="{fill_color}"/></a:solidFill>
    <a:ln w="19050">
      <a:solidFill><a:srgbClr val="{border_color}"/></a:solidFill>
    </a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr anchor="ctr" lIns="36000" rIns="36000" tIns="36000" bIns="36000" wrap="square"/>
    <a:lstStyle/>
    <a:p>
      <a:pPr algn="ctr"/>
      <a:r>
        <a:rPr lang="en-US" sz="1200" b="1" dirty="0">
          <a:solidFill><a:srgbClr val="0070C0"/></a:solidFill>
          <a:latin typeface="Arial" pitchFamily="34" charset="0"/>
        </a:rPr>
        <a:t>{xml_escape(line1)}</a:t>
      </a:r>
    </a:p>
    {l2_run}
  </p:txBody>
</p:sp>"""

def create_arrow(sp_id, name, x, y, cx, cy, color="0070C0", prst="rightArrow"):
    """Create a native DrawingML arrow shape."""
    return f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr>
    <p:cNvPr id="{sp_id}" name="{name}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm>
      <a:off x="{x}" y="{y}"/>
      <a:ext cx="{cx}" cy="{cy}"/>
    </a:xfrm>
    <a:prstGeom prst="{prst}">
      <a:avLst/>
    </a:prstGeom>
    <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
    <a:ln w="9525"><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr anchor="ctr"/>
    <a:lstStyle/>
    <a:p><a:pPr/></a:p>
  </p:txBody>
</p:sp>"""


def build_slide1(content: str) -> str:
    # Replace content of TextBox 9
    new_tb9 = """<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="10" name="TextBox 9"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="331286" y="2076450"/><a:ext cx="11000000" cy="4703019"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" rtlCol="0"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>Problem Statement ID – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>[fill in — I'll provide]</a:t></a:r>
    </a:p>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>Problem Statement Title – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>Real-time weather data collection, misinformation triage, and analysis platform for disaster response</a:t></a:r>
    </a:p>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>Theme – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>Disaster Management</a:t></a:r>
    </a:p>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>PS Category – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>Software</a:t></a:r>
    </a:p>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>Team ID – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>[fill in]</a:t></a:r>
    </a:p>
    <a:p>
      <a:pPr marL="285750" indent="-285750" algn="left"><a:lnSpc><a:spcPct val="160000"/></a:lnSpc><a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="en-US" sz="2400" b="1"><a:latin typeface="Arial"/></a:rPr><a:t>Team Name (Registered on portal) – </a:t></a:r>
      <a:r><a:rPr lang="en-US" sz="2400"><a:latin typeface="Arial"/></a:rPr><a:t>[fill in]</a:t></a:r>
    </a:p>
  </p:txBody>
</p:sp>"""

    # Replace the old TextBox 9
    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 9".*?</p:sp>'
    content = re.sub(pattern, new_tb9, content, flags=re.DOTALL)
    return content


def build_slide2(content: str) -> str:
    # Update title to "National Weather Big Data Analytics Platform + WeatherGPT"
    content = re.sub(
        r'(<p:cNvPr[^>]*name="Title 1"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)',
        r'\g<1>IDEA TITLE: National Weather Big Data Analytics Platform + WeatherGPT\g<2>',
        content,
        flags=re.DOTALL
    )

    # Bullets for Slide 2
    bullets = [
        make_bullet_p("Multi-Source Ingestion:", "Ingests 4 weather APIs (Open-Meteo, OpenWeather, Tomorrow.io, WeatherAPI), citizen reports, and news/social feeds (GDELT, Reddit) into a single pipeline.", sz=1800),
        make_bullet_p("AI Classification & Triage:", "NLP engine classifies reports into 13 hazard categories with calibrated confidence scores [0.45–0.98].", sz=1800),
        make_bullet_p("Multimodal Deduplication:", "Collapses duplicates using Haversine distance (≤3.5km) + temporal delta (≤90m) + Jaccard token overlap without discarding velocity metrics.", sz=1800),
        make_bullet_p("Explainable Trust Scoring:", "Evaluates credibility [0–100] across 6 transparent physical signals (radar consistency, spatial bounds, temporal freshness, cross-corroboration, media).", sz=1800),
        make_bullet_p("PostGIS Incident Clustering:", "Groups reports into spatial hazard incidents (≤12km, ≤4h), computes a 0–100 Platform Impact Score, and escalates high-velocity hotspots to Early Warning feeds.", sz=1800),
        make_bullet_p("Grounded WeatherGPT:", "Provides emergency teams a grounded, citation-backed conversational interface — zero hallucinated figures, strictly factual live telemetry.", sz=1800),
        make_bullet_p("Core Innovation:", "Multi-provider consensus scoring + transparent 6-signal trust audit (not a black-box filter) + human-in-the-loop verification console with permanent audit trails.", sz=1800),
    ]

    new_tb8 = f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="15362" name="TextBox 8"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr bwMode="auto"><a:xfrm><a:off x="609600" y="1650000"/><a:ext cx="10972800" cy="4500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    {make_header_p("Proposed Solution & System Capabilities (Working Prototype):", sz=2200)}
    {''.join(bullets)}
  </p:txBody>
</p:sp>"""

    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 8".*?</p:sp>'
    content = re.sub(pattern, new_tb8, content, flags=re.DOTALL)
    # Update Team Name oval
    content = re.sub(r'(<p:cNvPr[^>]*name="Oval 9"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)', r'\g<1>Team: [fill in]\g<2>', content, flags=re.DOTALL)
    return content


def build_slide3(content: str) -> str:
    # Update title
    content = re.sub(
        r'(<p:cNvPr[^>]*name="Title 1"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)',
        r'\g<1>TECHNICAL APPROACH &amp; ARCHITECTURE\g<2>',
        content,
        flags=re.DOTALL
    )

    # Bullets for Technologies
    tech_bullets = [
        make_bullet_p("Backend & Queue:", "FastAPI (Python async ASGI), Celery worker pool + Redis 7 for asynchronous background ingestion & reclustering.", sz=1600),
        make_bullet_p("Database & GIS:", "PostgreSQL 15 + PostGIS 3.4 for geodesic spatial indexing (ST_DWithin, SRID 4326), GeoAlchemy2, ACID audit history.", sz=1600),
        make_bullet_p("Frontend UX:", "Next.js 14 App Router, React 18, TypeScript, Tailwind CSS (dark command palette), Leaflet GIS, Recharts telemetry.", sz=1600),
        make_bullet_p("AI / ML Pipeline:", "Calibrated 13-category lexical NLP classifier (<1.5ms latency), Haversine + Jaccard deduplication, OpenCLIP zero-shot support.", sz=1600),
        make_bullet_p("WeatherGPT Reasoning:", "Google Gemini 1.5 Flash primary → OpenAI GPT-4o-mini secondary → Rule-based deterministic fallback with citation evidence panels.", sz=1600),
        make_bullet_p("Deployment:", "Docker Compose single-command orchestration (`docker compose up --build`), pre-cached offline demo resilience.", sz=1600),
    ]

    new_tb8 = f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="17410" name="TextBox 8"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr bwMode="auto"><a:xfrm><a:off x="609600" y="1400000"/><a:ext cx="10972800" cy="2300000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    {make_header_p("Technologies & Tools Employed:", sz=2000)}
    {''.join(tech_bullets)}
    {make_header_p("Methodology & Processing Flow (10-Stage Pipeline):", sz=2000)}
  </p:txBody>
</p:sp>"""

    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 8".*?</p:sp>'
    content = re.sub(pattern, new_tb8, content, flags=re.DOTALL)

    # Now add the 10-node flowchart shapes into spTree
    # 2 rows of 5 nodes
    row1_nodes = [
        ("01. Weather Feeds", "4 APIs + Citizens"),
        ("02. Normalization", "UTC, GPS, Schema"),
        ("03. AI Classifier", "13 Hazard Classes"),
        ("04. Deduplication", "Haversine ≤ 3.5km"),
        ("05. Trust Engine", "6-Signal Scoring"),
    ]
    row2_nodes = [
        ("06. PostGIS Store", "Spatiotemporal Clust"),
        ("07. Impact Score", "0–100 Severity Index"),
        ("08. Early Warning", "Hotspot Escalation"),
        ("09. Admin Console", "Human Verification"),
        ("10. WeatherGPT", "Grounded Decision AI"),
    ]

    shapes_xml = []
    sp_id = 20000

    # Layout coordinates
    # Available width: x = 609600 to 11582400 (width = 10972800)
    card_w = 1880000
    card_h = 750000
    gap = 390000
    arrow_w = 260000
    arrow_h = 240000

    y_row1 = 4050000
    y_row2 = 5150000

    # Row 1 (Nodes 1 to 5)
    for i, (l1, l2) in enumerate(row1_nodes):
        x = 609600 + i * (card_w + gap)
        shapes_xml.append(create_flow_node(sp_id, f"Node_R1_{i+1}", l1, l2, x, y_row1, card_w, card_h))
        sp_id += 1
        if i < 4:
            ax = x + card_w + 65000
            ay = y_row1 + (card_h - arrow_h) // 2
            shapes_xml.append(create_arrow(sp_id, f"Arrow_R1_{i+1}", ax, ay, arrow_w, arrow_h, prst="rightArrow"))
            sp_id += 1

    # Connector from Node 5 down to Node 6
    # Card 5 x is: 609600 + 4 * (card_w + gap)
    c5_x = 609600 + 4 * (card_w + gap)
    down_ax = c5_x + card_w // 2 - 120000
    down_ay = y_row1 + card_h + 40000
    shapes_xml.append(create_arrow(sp_id, "Arrow_Down", down_ax, down_ay, 240000, 260000, prst="downArrow"))
    sp_id += 1

    # Row 2 (Nodes 6 to 10) - reversed right to left so flow snakes naturally:
    # 05 -> down -> 06 -> 07 -> 08 -> 09 -> 10 (left to right)
    for i, (l1, l2) in enumerate(row2_nodes):
        x = 609600 + i * (card_w + gap)
        fill = "F0FDF4" if i >= 3 else "F0F6FB"  # light green tint for verification and weathergpt
        border = "16A34A" if i >= 3 else "0070C0"
        shapes_xml.append(create_flow_node(sp_id, f"Node_R2_{i+6}", l1, l2, x, y_row2, card_w, card_h, fill_color=fill, border_color=border))
        sp_id += 1
        if i < 4:
            ax = x + card_w + 65000
            ay = y_row2 + (card_h - arrow_h) // 2
            shapes_xml.append(create_arrow(sp_id, f"Arrow_R2_{i+6}", ax, ay, arrow_w, arrow_h, prst="rightArrow"))
            sp_id += 1

    # Insert shapes into </p:spTree>
    all_shapes = "\n".join(shapes_xml)
    content = content.replace("</p:spTree>", f"{all_shapes}\n</p:spTree>")

    # Update Team Name oval
    content = re.sub(r'(<p:cNvPr[^>]*name="Oval 10"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)', r'\g<1>Team: [fill in]\g<2>', content, flags=re.DOTALL)
    return content


def build_slide4(content: str) -> str:
    content = re.sub(
        r'(<p:cNvPr[^>]*name="Title 1"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)',
        r'\g<1>FEASIBILITY AND VIABILITY ANALYSIS\g<2>',
        content,
        flags=re.DOTALL
    )

    feasibility_bullets = [
        make_bullet_p("Operational Prototype Built & Validated:", "Fully implemented codebase with 62/62 automated pytest suites passing across providers, NLP classifier, dedup, clustering, and WeatherGPT.", sz=1700),
        make_bullet_p("Low-Latency Ingestion & UI:", "Sub-15ms end-to-end report ingestion pipeline; Next.js 14 production build compiled with 15 static routes and 0 errors.", sz=1700),
        make_bullet_p("100% Offline Demonstration Capability:", "Pre-cached meteorological dataset and deterministic 500-report generator (demo/seed.py) ensure zero failure risk from external connectivity during hackathon judging.", sz=1700),
        make_bullet_p("Economical & Horizontally Scalable:", "Operates on free-tier global models and open-source PostGIS/Redis stack; stateless ASGI architecture enables linear horizontal scale.", sz=1700),
    ]

    challenges_bullets = [
        make_bullet_p("Challenge 1 (No Public IMD Radar API):", "Mitigated via 4-provider global model consensus (Open-Meteo, OWM, Tomorrow, WeatherAPI) cross-validated with local citizen reports and official IMD linkouts.", sz=1700),
        make_bullet_p("Challenge 2 (Spam & Rumor Vulnerability):", "Mitigated via automated 6-factor credibility scoring, rate-limiting, and mandatory human review before unverified posts become ground truth.", sz=1700),
        make_bullet_p("Challenge 3 (Regional Language Nuances):", "Mitigated with hybrid bilingual lexicon (English/Hindi idioms like 'aandhi', 'loo', 'cloudburst') and human review queue for low-confidence text.", sz=1700),
    ]

    new_tb8 = f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="17410" name="TextBox 8"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr bwMode="auto"><a:xfrm><a:off x="609600" y="1650000"/><a:ext cx="10972800" cy="4500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    {make_header_p("Feasibility & Operational Readiness:", sz=2000)}
    {''.join(feasibility_bullets)}
    {make_header_p("Key Challenges & Architectural Mitigations:", sz=2000)}
    {''.join(challenges_bullets)}
  </p:txBody>
</p:sp>"""

    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 8".*?</p:sp>'
    content = re.sub(pattern, new_tb8, content, flags=re.DOTALL)
    content = re.sub(r'(<p:cNvPr[^>]*name="Oval 11"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)', r'\g<1>Team: [fill in]\g<2>', content, flags=re.DOTALL)
    return content


def build_slide5(content: str) -> str:
    content = re.sub(
        r'(<p:cNvPr[^>]*name="Title 1"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)',
        r'\g<1>IMPACT AND BENEFITS TO STAKEHOLDERS\g<2>',
        content,
        flags=re.DOTALL
    )

    bullets = [
        make_bullet_p("Target Beneficiaries & Users:", "National & State Disaster Management Authorities (NDMA/SDMA), district collectors, Emergency Operations Centers (EOCs), municipal flood control cells, and NDRF/SDRF field response units.", sz=1800),
        make_bullet_p("Life-Saving Social Impact:", "Accelerates triage during flash floods, cloudbursts, and cyclones from hours to seconds; enables timely targeted citizen evacuations and localized shelter management.", sz=1800),
        make_bullet_p("Economic & Resource Efficiency:", "Dramatically reduces wasteful dispatch of emergency personnel and pumps triggered by viral social media rumors, stale photos, or duplicate panic reports.", sz=1800),
        make_bullet_p("Unified Operational Picture:", "Bridges the dangerous gap between macro satellite forecasts and chaotic ground eyewitness posts into a single verified, geospatial situational dashboard.", sz=1800),
        make_bullet_p("Accountability & Governance:", "Human-in-the-loop verification station creates an immutable audit trail for every emergency declaration, ensuring institutional transparency and post-event analysis.", sz=1800),
    ]

    new_tb8 = f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="17410" name="TextBox 8"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr bwMode="auto"><a:xfrm><a:off x="609600" y="1700000"/><a:ext cx="10972800" cy="4400000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    {make_header_p("Value Proposition & Societal Returns:", sz=2200)}
    {''.join(bullets)}
  </p:txBody>
</p:sp>"""

    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 8".*?</p:sp>'
    content = re.sub(pattern, new_tb8, content, flags=re.DOTALL)
    content = re.sub(r'(<p:cNvPr[^>]*name="Oval 11"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)', r'\g<1>Team: [fill in]\g<2>', content, flags=re.DOTALL)
    return content


def build_slide6(content: str) -> str:
    content = re.sub(
        r'(<p:cNvPr[^>]*name="Title 1"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)',
        r'\g<1>RESEARCH, REFERENCES AND STANDARDS\g<2>',
        content,
        flags=re.DOTALL
    )

    api_refs = [
        make_bullet_p("Open-Meteo Weather API:", "High-resolution global weather models (ECMWF, GFS), hourly forecasts, free tier — https://open-meteo.com/", sz=1600),
        make_bullet_p("OpenWeatherMap API:", "Current atmospheric conditions, wind gusts, atmospheric pressure API v2.5 — https://openweathermap.org/api", sz=1600),
        make_bullet_p("Tomorrow.io Intelligence API:", "1-hour hyper-local precipitation and convective storm tracking API v4 — https://www.tomorrow.io/", sz=1600),
        make_bullet_p("WeatherAPI.com:", "Real-time observational feed and condition code cross-validation — https://www.weatherapi.com/", sz=1600),
        make_bullet_p("PostGIS Spatial Database:", "Geodesic geometry indexing (ST_DWithin, WGS-84 SRID 4326) — https://postgis.net/", sz=1600),
    ]

    standards_refs = [
        make_bullet_p("GDELT 2.0 Global News Project:", "Real-time news intelligence monitoring for disaster keywords — https://www.gdeltproject.org/", sz=1600),
        make_bullet_p("NDMA Incident Response System:", "National Disaster Management Guidelines on Incident Command & Response, Govt. of India (2010)", sz=1600),
        make_bullet_p("WMO Multi-Hazard Guidelines:", "World Meteorological Organization Guidelines on Multi-Hazard Early Warning Systems (MHEWS-II)", sz=1600),
        make_bullet_p("USGS Earthquake & Hazard Feed:", "Real-time GeoJSON seismic event protocols & spatial schemas — https://earthquake.usgs.gov/", sz=1600),
    ]

    new_tb8 = f"""<p:sp xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:nvSpPr><p:cNvPr id="17410" name="TextBox 8"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr bwMode="auto"><a:xfrm><a:off x="609600" y="1650000"/><a:ext cx="10972800" cy="4500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    {make_header_p("Meteorological APIs & Spatial Platforms:", sz=1900)}
    {''.join(api_refs)}
    {make_header_p("National Disaster Guidelines & Global Standards:", sz=1900)}
    {''.join(standards_refs)}
  </p:txBody>
</p:sp>"""

    pattern = r'<p:sp\b[^>]*>(?:(?!</p:sp>).)*?name="TextBox 8".*?</p:sp>'
    content = re.sub(pattern, new_tb8, content, flags=re.DOTALL)
    content = re.sub(r'(<p:cNvPr[^>]*name="Oval 8"[^>]*>.*?</p:nvSpPr>.*?<a:t>)[^<]*(</a:t>)', r'\g<1>Team: [fill in]\g<2>', content, flags=re.DOTALL)
    return content


def process_presentation_xml(content: str) -> str:
    """Remove slide 7 reference (<p:sldId id="297" r:id="rId8"/>) from presentation.xml."""
    content = re.sub(r'<p:sldId[^>]*r:id="rId8"[^>]*/>', '', content)
    return content


def process_presentation_rels(content: str) -> str:
    """Remove relationship to slide7.xml from presentation.xml.rels."""
    content = re.sub(r'<Relationship[^>]*Target="slides/slide7\.xml"[^>]*/>', '', content)
    return content


def process_content_types(content: str) -> str:
    """Remove Override for slide7.xml from [Content_Types].xml."""
    content = re.sub(r'<Override[^>]*PartName="/ppt/slides/slide7\.xml"[^>]*/>', '', content)
    content = re.sub(r'<Override[^>]*PartName="/ppt/notesSlides/notesSlide6\.xml"[^>]*/>', '', content)
    return content


def process_app_props(content: str) -> str:
    """Update slide count from 7 to 6 in docProps/app.xml."""
    content = content.replace("<Slides>7</Slides>", "<Slides>6</Slides>")
    content = content.replace("<Notes>6</Notes>", "<Notes>5</Notes>")
    content = content.replace("<vt:i4>7</vt:i4>", "<vt:i4>6</vt:i4>")
    content = content.replace("<vt:lpstr>PowerPoint Presentation</vt:lpstr>", "")
    return content


def main():
    print(f"Reading template: {SOURCE_PPTX}")
    temp_zip = "temp_deck.zip"

    with zipfile.ZipFile(SOURCE_PPTX, "r") as zin, zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            # Skip slide 7 files
            if item.filename in ("ppt/slides/slide7.xml", "ppt/slides/_rels/slide7.xml.rels", "ppt/notesSlides/notesSlide6.xml", "ppt/notesSlides/_rels/notesSlide6.xml.rels"):
                print(f"Purging slide 7 file: {item.filename}")
                continue

            content_bytes = zin.read(item.filename)

            if item.filename == "ppt/slides/slide1.xml":
                print("Processing Slide 1 (Title Page)...")
                text = content_bytes.decode("utf-8")
                text = build_slide1(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/slides/slide2.xml":
                print("Processing Slide 2 (Proposed Solution)...")
                text = content_bytes.decode("utf-8")
                text = build_slide2(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/slides/slide3.xml":
                print("Processing Slide 3 (Technical Approach & Architecture)...")
                text = content_bytes.decode("utf-8")
                text = build_slide3(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/slides/slide4.xml":
                print("Processing Slide 4 (Feasibility & Viability)...")
                text = content_bytes.decode("utf-8")
                text = build_slide4(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/slides/slide5.xml":
                print("Processing Slide 5 (Impact & Benefits)...")
                text = content_bytes.decode("utf-8")
                text = build_slide5(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/slides/slide6.xml":
                print("Processing Slide 6 (Research & References)...")
                text = content_bytes.decode("utf-8")
                text = build_slide6(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/presentation.xml":
                print("Updating ppt/presentation.xml...")
                text = content_bytes.decode("utf-8")
                text = process_presentation_xml(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "ppt/_rels/presentation.xml.rels":
                print("Updating ppt/_rels/presentation.xml.rels...")
                text = content_bytes.decode("utf-8")
                text = process_presentation_rels(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "[Content_Types].xml":
                print("Updating [Content_Types].xml...")
                text = content_bytes.decode("utf-8")
                text = process_content_types(text)
                content_bytes = text.encode("utf-8")

            elif item.filename == "docProps/app.xml":
                print("Updating docProps/app.xml...")
                text = content_bytes.decode("utf-8")
                text = process_app_props(text)
                content_bytes = text.encode("utf-8")

            zout.writestr(item, content_bytes)

    # Move temp_zip to TARGET_PPTX
    shutil.move(temp_zip, TARGET_PPTX)
    print(f"\nSuccessfully generated official PPTX: {TARGET_PPTX}")

    # Convert to PDF using PowerPoint AppleScript
    print("Exporting to native PDF via Microsoft PowerPoint AppleScript...")
    pwd = os.path.abspath(".")
    pptx_path = os.path.join(pwd, TARGET_PPTX)
    pdf_path = os.path.join(pwd, TARGET_PDF)

    applescript_cmd = f"""osascript -e '
set pptPath to (POSIX file "{pptx_path}") as string
set pdfPath to (POSIX file "{pdf_path}") as string
tell application "Microsoft PowerPoint"
    open file pptPath
    save active presentation in pdfPath as save as PDF
    close active presentation saving no
end tell
'"""
    ret = os.system(applescript_cmd)
    if ret == 0 and os.path.exists(TARGET_PDF):
        print(f"Successfully generated official PDF: {TARGET_PDF} ({os.path.getsize(TARGET_PDF)} bytes)")
    else:
        print(f"AppleScript return code: {ret}. PDF export verification failed.")

if __name__ == "__main__":
    main()
