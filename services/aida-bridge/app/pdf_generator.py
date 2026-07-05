import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, grey
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime

AEGIS_BLUE = HexColor("#1e3a8a")
AEGIS_LIGHT_BLUE = HexColor("#e0f2fe")
AEGIS_GRAY = HexColor("#f1f5f9")

def add_page_number(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(grey)
    canvas_obj.drawRightString(letter[0] - 0.5*inch, 0.5*inch, f"Page {doc.page}")
    canvas_obj.restoreState()

def parse_markdown_to_paragraphs(text, base_styles, custom_styles):
    lines = text.split('\n')
    flowables = []
    bullet_items = []
    in_bullet_list = False

    for line in lines:
        line = line.rstrip()
        if not line:
            if in_bullet_list and bullet_items:
                flowables.append(ListFlowable(bullet_items, bulletType='bullet', start='•'))
                bullet_items = []
                in_bullet_list = False
            flowables.append(Spacer(1, 6))
            continue

        if line.startswith('# '):
            flowables.append(Paragraph(line[2:], custom_styles.get('Heading1', base_styles['Heading1'])))
        elif line.startswith('## '):
            flowables.append(Paragraph(line[3:], custom_styles.get('Heading2', base_styles['Heading2'])))
        elif line.startswith('### '):
            flowables.append(Paragraph(line[4:], custom_styles.get('Heading3', base_styles['Heading3'])))
        elif re.match(r'^\d+\.', line):
            flowables.append(Paragraph(line, custom_styles.get('SectionHeading', base_styles['Heading2'])))
        elif line.startswith(('- ', '• ', '* ')):
            bullet_text = line[2:].strip()
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            bullet_items.append(ListItem(Paragraph(bullet_text, custom_styles.get('Bullet', base_styles['Normal']))))
            in_bullet_list = True
        else:
            if in_bullet_list and bullet_items:
                flowables.append(ListFlowable(bullet_items, bulletType='bullet', start='•'))
                bullet_items = []
                in_bullet_list = False
            line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            flowables.append(Paragraph(line, custom_styles.get('Normal', base_styles['Normal'])))

    if in_bullet_list and bullet_items:
        flowables.append(ListFlowable(bullet_items, bulletType='bullet', start='•'))
    return flowables

def generate_compliance_pdf(report_text: str, model_name: str, approved: bool = False,
                            user_email: str = None, signature_name: str = None, output_path: str = None) -> str:
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/app/pdfs/compliance_report_{model_name}_{timestamp}.pdf"

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            topMargin=0.8*inch, bottomMargin=0.8*inch,
                            leftMargin=0.8*inch, rightMargin=0.8*inch)
    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=base_styles['Heading1'],
                                 fontName='Helvetica-Bold', fontSize=18,
                                 textColor=AEGIS_BLUE, alignment=TA_CENTER, spaceAfter=12)
    heading1_style = ParagraphStyle('Heading1', parent=base_styles['Heading1'],
                                    fontName='Helvetica-Bold', fontSize=16, textColor=AEGIS_BLUE, spaceAfter=10)
    heading2_style = ParagraphStyle('Heading2', parent=base_styles['Heading2'],
                                    fontName='Helvetica-Bold', fontSize=14, textColor=AEGIS_BLUE, spaceAfter=8)
    heading3_style = ParagraphStyle('Heading3', parent=base_styles['Heading3'],
                                    fontName='Helvetica-Bold', fontSize=12, textColor=black, spaceAfter=6)
    section_style = ParagraphStyle('SectionHeading', parent=base_styles['Heading2'],
                                   fontName='Helvetica-Bold', fontSize=14, textColor=AEGIS_BLUE,
                                   spaceBefore=12, spaceAfter=6, backColor=AEGIS_LIGHT_BLUE, borderRadius=4)
    normal_style = ParagraphStyle('Normal', parent=base_styles['Normal'],
                                  fontName='Helvetica', fontSize=9, leading=12, alignment=TA_LEFT)
    bullet_style = ParagraphStyle('Bullet', parent=base_styles['Normal'],
                                  fontName='Helvetica', fontSize=9, leading=12, leftIndent=10)
    customer_input_style = ParagraphStyle('CustomerInput', parent=base_styles['Normal'],
                                          fontName='Helvetica', fontSize=9, leading=12,
                                          backColor=AEGIS_GRAY, leftIndent=12, rightIndent=12,
                                          spaceBefore=6, spaceAfter=6)
    custom_styles = {'Title': title_style, 'Heading1': heading1_style, 'Heading2': heading2_style,
                     'Heading3': heading3_style, 'SectionHeading': section_style,
                     'Normal': normal_style, 'Bullet': bullet_style, 'CustomerInput': customer_input_style}

    story = [Spacer(1, 0.5*inch), Paragraph("AIDA COMPLIANCE REPORT", title_style),
             Spacer(1, 6), Paragraph(f"Model: {model_name}", title_style),
             Spacer(1, 6), Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", normal_style),
             Spacer(1, 12)]
    story.extend(parse_markdown_to_paragraphs(report_text, base_styles, custom_styles))
    story.append(PageBreak())
    story.append(Paragraph("APPROVAL & SIGN-OFF", title_style))
    story.append(Spacer(1, 24))

    if approved and signature_name:
        story.append(Paragraph("This report has been reviewed and officially approved.", normal_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Approved by (e-signature): {signature_name}", normal_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Email: {user_email or '____________________'}", normal_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", normal_style))
        story.append(Paragraph("I have reviewed this AI-generated draft and, to the best of my knowledge, it accurately reflects the requirements of the Artificial Intelligence and Data Act (AIDA), based on the source documents provided. I understand that final approval for regulatory submission requires further review by the appropriate legal or compliance department.", customer_input_style))
    else:
        story.append(Paragraph("This is a DRAFT report. It requires human review and sign-off before regulatory use.", customer_input_style))
        story.append(Paragraph("Approved by: ___________________________", normal_style))
        story.append(Paragraph("Title: _______________________________", normal_style))
        story.append(Paragraph("Date: _______________________________", normal_style))

    story.append(Paragraph("Notes / Conditions:", normal_style))
    story.append(Paragraph("_________________________________________________________________", normal_style))
    story.append(Paragraph("_________________________________________________________________", normal_style))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output_path
