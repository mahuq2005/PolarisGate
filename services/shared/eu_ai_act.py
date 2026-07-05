"""EU AI Act compliance data — single source of truth.
Shared between gateway API endpoints to eliminate code duplication.

Usage:
    from shared.eu_ai_act import get_compliance_data, generate_eu_ai_pdf

    data = get_compliance_data(risk_level="high", models=["gpt-4"])
    pdf_bytes = generate_eu_ai_pdf(risk_level="high", models=["gpt-4"])
"""
from io import BytesIO
from datetime import datetime, timezone
from typing import List, Optional

# ─── Compliance Scores ───────────────────────────────────────────────────

COMPLIANCE_SCORES = {
    "minimal": 95.0,
    "limited": 85.0,
    "high": 65.0,
    "unacceptable": 35.0,
}

# ─── EU AI Act Articles by Risk Level ────────────────────────────────────

ARTICLES_BY_RISK = {
    "minimal": [
        {"title": "Article 4 — Transparency Obligations", "description": "Ensure users are informed they are interacting with an AI system."},
        {"title": "Article 50 — Transparency for Certain AI Systems", "description": "Minimal risk systems must still meet basic transparency requirements."},
    ],
    "limited": [
        {"title": "Article 4 — Transparency Obligations", "description": "Ensure users are informed they are interacting with an AI system."},
        {"title": "Article 13 — Transparency and Provision of Information", "description": "Limited risk systems must provide clear documentation and instructions for use."},
        {"title": "Article 50 — Transparency for Certain AI Systems", "description": "Transparency requirements for limited risk AI systems."},
    ],
    "high": [
        {"title": "Article 6 — Classification Rules for High-Risk AI Systems", "description": "High-risk systems must comply with strict conformity assessment procedures."},
        {"title": "Article 9 — Risk Management System", "description": "Establish, implement, document and maintain a risk management system."},
        {"title": "Article 10 — Data and Data Governance", "description": "Training, validation and testing data sets shall be relevant, representative and free from errors."},
        {"title": "Article 13 — Transparency and Provision of Information", "description": "High-risk AI systems must be accompanied by clear and comprehensive instructions."},
        {"title": "Article 14 — Human Oversight", "description": "High-risk AI systems shall be designed to enable effective human oversight."},
        {"title": "Article 15 — Accuracy, Robustness and Cybersecurity", "description": "High-risk AI systems shall achieve appropriate levels of accuracy, robustness and cybersecurity."},
        {"title": "Article 43 — Conformity Assessment", "description": "High-risk systems require third-party conformity assessment before market placement."},
    ],
    "unacceptable": [
        {"title": "Article 5 — Prohibited AI Practices", "description": "Certain AI practices are prohibited as they contravene Union values."},
        {"title": "Article 6 — Classification Rules for High-Risk AI Systems", "description": "Systems posing unacceptable risk are banned from the EU market."},
        {"title": "Article 71 — Penalties", "description": "Non-compliance with prohibited practices may result in fines up to €35M or 7% of annual worldwide turnover."},
    ],
}


def get_compliance_data(risk_level: str = "medium", models: Optional[List[str]] = None) -> dict:
    """Get EU AI Act compliance data for a given risk level and models.
    
    Returns a dict with compliance_score, risk_level, and articles.
    This is the single source of truth — both API endpoints call this.
    """
    if models is None:
        models = []
    score = COMPLIANCE_SCORES.get(risk_level, 85.0)
    articles = ARTICLES_BY_RISK.get(risk_level, ARTICLES_BY_RISK["limited"])
    return {
        "compliance_score": score,
        "risk_level": risk_level,
        "articles": articles,
    }


def generate_eu_ai_pdf(risk_level: str = "medium", models: Optional[List[str]] = None) -> bytes:
    """Generate EU AI Act compliance report as PDF bytes.
    
    Uses reportlab to create a professional PDF with:
    - Title and metadata
    - Compliance score with color coding
    - Applicable EU AI Act articles
    """
    if models is None:
        models = []
    data = get_compliance_data(risk_level, models)
    score = data["compliance_score"]
    articles = data["articles"]

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib import colors

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=22, leading=26, spaceAfter=12,
        textColor=HexColor('#1a1a2e'),
    )
    heading_style = ParagraphStyle(
        'SectionHead', parent=styles['Heading2'],
        fontSize=14, leading=18, spaceAfter=6,
        spaceBefore=12, textColor=HexColor('#16213e'),
    )
    normal_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=10, leading=14, spaceAfter=4,
    )
    article_title_style = ParagraphStyle(
        'ArticleTitle', parent=styles['Normal'],
        fontSize=11, leading=14, spaceAfter=2,
        textColor=HexColor('#0f3460'), fontWeight='bold',
    )
    article_desc_style = ParagraphStyle(
        'ArticleDesc', parent=styles['Normal'],
        fontSize=9, leading=12, spaceAfter=8,
        textColor=HexColor('#555555'),
    )

    elements = []

    # Title
    elements.append(Paragraph("EU AI Act Compliance Report", title_style))
    elements.append(Spacer(1, 6))

    # Metadata
    elements.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        normal_style,
    ))
    elements.append(Paragraph(
        f"Risk Classification: <b>{risk_level.upper()}</b>",
        normal_style,
    ))
    models_str = ", ".join(models) if models else "N/A"
    elements.append(Paragraph(f"Models Assessed: {models_str}", normal_style))
    elements.append(Spacer(1, 12))

    # Compliance Score
    score_color = "#22c55e" if score >= 80 else "#eab308" if score >= 50 else "#ef4444"
    elements.append(Paragraph(
        f"Compliance Score: <b><font color='{score_color}'>{score:.1f}%</font></b>",
        heading_style,
    ))
    elements.append(Spacer(1, 12))

    # Articles
    elements.append(Paragraph("Applicable EU AI Act Articles", heading_style))
    elements.append(Spacer(1, 6))

    for i, art in enumerate(articles, 1):
        elements.append(Paragraph(f"<b>{i}. {art['title']}</b>", article_title_style))
        elements.append(Paragraph(art['description'], article_desc_style))

    # Footer
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "— End of Report —",
        ParagraphStyle(
            'Footer', parent=normal_style,
            alignment=1, textColor=HexColor('#999999'), fontSize=9,
        ),
    ))

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
