"""
Builds the "Student Feedback Report" PDF that the Resume Analyzer's
"Download Feedback PDF" button downloads.

Uses reportlab (pure Django-compatible PDF generation, no external
binary like wkhtmltopdf/Cairo required) to draw the PDF directly onto
an HttpResponse — nothing is written to a static/pre-made file, so the
content is always the student's actual, current data.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def build_feedback_pdf(response, *, student_name, target_career, feedback_date,
                        rating, category, feedback_items):
    """
    Draws the report onto `response` (an HttpResponse whose
    Content-Type is already set to application/pdf) and returns it.
    """
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    x_margin = 1 * inch
    y = height - 1 * inch

    p.setFont("Helvetica-Bold", 20)
    p.setFillColorRGB(0.435, 0.125, 0.208)  # matches the site's maroon
    p.drawString(x_margin, y, "CAREERMIND")
    y -= 26

    p.setFont("Helvetica", 13)
    p.setFillColorRGB(0.2, 0.2, 0.2)
    p.drawString(x_margin, y, "Student Feedback Report")
    y -= 10
    p.line(x_margin, y, width - x_margin, y)
    y -= 26

    p.setFont("Helvetica-Bold", 11)
    fields = [
        ("Student Name", student_name),
        ("Target Career", target_career),
        ("Feedback Date", feedback_date),
        ("Rating", rating),
        ("Category", category),
    ]
    for label, value in fields:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(x_margin, y, f"{label}:")
        p.setFont("Helvetica", 11)
        p.drawString(x_margin + 1.6 * inch, y, str(value))
        y -= 20

    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x_margin, y, "Feedback")
    y -= 8
    p.line(x_margin, y, width - x_margin, y)
    y -= 20

    p.setFont("Helvetica", 10)
    for item in feedback_items:
        # Simple word-wrap so a long feedback line doesn't run off the page.
        words = str(item).split()
        line = "• "
        for word in words:
            if p.stringWidth(line + word, "Helvetica", 10) > (width - 2 * x_margin):
                p.drawString(x_margin, y, line)
                y -= 15
                line = "  " + word + " "
                if y < 1 * inch:
                    p.showPage()
                    y = height - 1 * inch
                    p.setFont("Helvetica", 10)
            else:
                line += word + " "
        p.drawString(x_margin, y, line)
        y -= 20
        if y < 1 * inch:
            p.showPage()
            y = height - 1 * inch
            p.setFont("Helvetica", 10)

    p.showPage()
    p.save()
    return response
