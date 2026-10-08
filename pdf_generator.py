from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os


def generate_pdf(output_path, config, questions):
    # Override marks from config if provided
    mcq_marks   = config.get('mcq_marks', None)
    short_marks = config.get('short_marks', None)
    long_marks  = config.get('long_marks', None)

    type_marks = {}
    if mcq_marks:   type_marks['MCQ']   = mcq_marks
    if short_marks: type_marks['Short'] = short_marks
    if long_marks:  type_marks['Long']  = long_marks

    # Apply configured marks to all questions
    for q in questions:
        if q['question_type'] in type_marks:
            q['marks'] = type_marks[q['question_type']]
    """
    Generates a formatted question paper PDF.
    config: dict with keys - college_name, subject, exam_type, total_marks, duration, date, units
    questions: list of question dicts from the selection engine
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    college_style = ParagraphStyle('College', fontSize=14, fontName='Helvetica-Bold',
                                    alignment=TA_CENTER, spaceAfter=2)
    title_style = ParagraphStyle('Title', fontSize=11, fontName='Helvetica-Bold',
                                  alignment=TA_CENTER, spaceAfter=2)
    sub_style = ParagraphStyle('Sub', fontSize=10, fontName='Helvetica',
                                alignment=TA_CENTER, spaceAfter=4)
    section_style = ParagraphStyle('Section', fontSize=11, fontName='Helvetica-Bold',
                                    spaceBefore=12, spaceAfter=6,
                                    textColor=colors.HexColor('#1a1a2e'))
    question_style = ParagraphStyle('Question', fontSize=10, fontName='Helvetica',
                                     spaceBefore=4, spaceAfter=2, leading=14)
    option_style = ParagraphStyle('Option', fontSize=10, fontName='Helvetica',
                                   leftIndent=20, spaceAfter=1, leading=12)
    marks_style = ParagraphStyle('Marks', fontSize=9, fontName='Helvetica-Oblique',
                                  alignment=TA_RIGHT)

    story = []

    # ── HEADER ──────────────────────────────────────────────
    story.append(Paragraph(config.get('college_name', 'Your College Name'), college_style))
    story.append(Paragraph("Department of Computer Science & Engineering", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black))
    story.append(Spacer(1, 6))

    # Exam info table
    exam_data = [
        ["Subject:", config['subject'], "Exam Type:", config['exam_type']],
        ["Total Marks:", str(config['total_marks']), "Duration:", f"{config['duration']} Minutes"],
        ["Date:", config.get('date', datetime.now().strftime("%d-%m-%Y")),
         "Units Covered:", ", ".join(config.get('units', []))],
    ]
    info_table = Table(exam_data, colWidths=[3.5*cm, 6*cm, 3.5*cm, 5*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 4))

    # Instructions
    story.append(Paragraph("<b>Instructions:</b> Answer all questions. Each question carries marks as indicated.", question_style))
    story.append(Spacer(1, 8))

    # ── QUESTIONS BY SECTION ────────────────────────────────
    sections = [
        ("SECTION A — Multiple Choice Questions (MCQ)", "MCQ"),
        ("SECTION B — Short Answer Questions", "Short"),
        ("SECTION C — Long Answer Questions", "Long"),
    ]

    for section_title, q_type in sections:
        section_qs = [q for q in questions if q['question_type'] == q_type]
        if not section_qs:
            continue

        story.append(Paragraph(section_title, section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 4))

        for i, q in enumerate(section_qs, 1):
            # Question text with marks
            q_text = f"<b>Q{i}.</b> {q['question_text']}"
            marks_text = f"[{q['marks']} Mark{'s' if q['marks'] > 1 else ''}]"

            row = Table(
                [[Paragraph(q_text, question_style), Paragraph(marks_text, marks_style)]],
                colWidths=[14*cm, 3.5*cm]
            )
            row.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(row)

            # MCQ options
            if q_type == "MCQ":
                options = [
                    ('A', q.get('option_a')),
                    ('B', q.get('option_b')),
                    ('C', q.get('option_c')),
                    ('D', q.get('option_d')),
                ]
                for opt_label, opt_text in options:
                    if opt_text:
                        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;({opt_label}) {opt_text}", option_style))

            story.append(Spacer(1, 8))

    # ── FOOTER ──────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    total = sum(q['marks'] for q in questions)
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Total Marks: {total} &nbsp;&nbsp;&nbsp; Total Questions: {len(questions)}</b>",
                            ParagraphStyle('Footer', fontSize=10, fontName='Helvetica-Bold', alignment=TA_CENTER)))
    story.append(Spacer(1, 6))
    story.append(Paragraph("— End of Question Paper —",
                            ParagraphStyle('End', fontSize=9, fontName='Helvetica-Oblique', alignment=TA_CENTER,
                                           textColor=colors.grey)))

    doc.build(story)
    print(f"[PDF] Question paper saved to: {output_path}")