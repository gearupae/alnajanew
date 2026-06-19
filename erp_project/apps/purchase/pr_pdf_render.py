"""Purchase Request PDF context + WeasyPrint rendering."""
from django.template.loader import get_template

from apps.settings_app.models import CompanySettings


def build_pr_pdf_context(request, pr):
    """Context dict for purchase/pr_pdf.html (HTML or PDF)."""
    company = CompanySettings.get_settings()
    logo_absolute_url = ''
    if company.logo:
        logo_absolute_url = request.build_absolute_uri(company.logo.url)

    return {
        'pr': pr,
        'company': company,
        'logo_absolute_url': logo_absolute_url,
        'is_pdf': True,
    }


def render_pr_pdf_bytes(request, pr):
    """
    Render PR as PDF bytes using WeasyPrint.
    Returns (pdf_bytes, None) on success, or (None, error_message) on failure.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        return None, 'WeasyPrint is not installed; cannot generate PDF.'

    context = build_pr_pdf_context(request, pr)
    template = get_template('purchase/pr_pdf.html')
    html_string = template.render(context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()
    return pdf, None
