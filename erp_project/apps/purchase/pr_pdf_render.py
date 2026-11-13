"""Purchase Request PDF context + WeasyPrint rendering."""
from django.template.loader import get_template

from apps.core.pdf_branding import merge_pdf_branding


def build_pr_pdf_context(request, pr, *, for_weasyprint=False):
    """Context dict for purchase/pr_pdf.html (HTML or PDF)."""
    return merge_pdf_branding(
        request,
        {
            'pr': pr,
            'is_pdf': True,
        },
        for_weasyprint=for_weasyprint,
    )


def render_pr_pdf_bytes(request, pr):
    """
    Render PR as PDF bytes using WeasyPrint.
    Returns (pdf_bytes, None) on success, or (None, error_message) on failure.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        return None, 'WeasyPrint is not installed; cannot generate PDF.'

    context = build_pr_pdf_context(request, pr, for_weasyprint=True)
    template = get_template('purchase/pr_pdf.html')
    html_string = template.render(context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()
    return pdf, None
