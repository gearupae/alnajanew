"""Company letterhead data for HTML / WeasyPrint PDFs (Settings → Company)."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings

from apps.settings_app.models import CompanySettings


def pdf_media_absolute_url(request, file_field, *, for_weasyprint: bool = False) -> str:
    if not file_field:
        return ''
    url = file_field.url
    if url.startswith(('http://', 'https://')):
        return url
    if not for_weasyprint:
        return request.build_absolute_uri(url)
    try:
        path = file_field.path
        if path and os.path.isfile(path):
            return Path(path).resolve().as_uri()
    except (ValueError, NotImplementedError):
        pass
    return request.build_absolute_uri(url)


def build_company_pdf_branding_context(request, *, for_weasyprint: bool = False) -> dict:
    """Merge into any PDF template context as {{ company }}, logo URLs, etc."""
    company = CompanySettings.get_settings()
    kw = {'for_weasyprint': for_weasyprint}
    logo_absolute_url = pdf_media_absolute_url(request, company.logo, **kw)
    pdf_stamp_url = pdf_media_absolute_url(request, company.estimate_pdf_stamp_image, **kw)
    pdf_footer_badge_url = pdf_media_absolute_url(request, company.estimate_pdf_footer_image, **kw)

    if not logo_absolute_url:
        static_logo = os.path.join(settings.BASE_DIR, 'static', 'logo.png')
        if os.path.isfile(static_logo):
            if for_weasyprint:
                logo_absolute_url = Path(static_logo).resolve().as_uri()
            elif request is not None:
                logo_absolute_url = request.build_absolute_uri(settings.STATIC_URL + 'logo.png')

    footer_services = (company.pdf_footer_services or '').strip() or (
        'Central Tank Systems | Manifold Systems | Gas Detection Systems | Annual Maintenance'
    )
    header_subtitle = (company.pdf_letterhead_subtitle or '').strip() or (
        'Approved by the Directorate of Civil Defence'
    )
    header_subtitle_ar = (company.pdf_letterhead_subtitle_ar or '').strip() or (
        'النجاح لتركيب خطوط الأنابيب'
    )
    services_badge = (company.pdf_services_badge_label or '').strip() or 'LPG Services'

    phones = []
    if company.phone:
        for part in company.phone.replace(';', ',').split(','):
            p = part.strip()
            if p:
                phones.append(p)

    return {
        'company': company,
        'logo_absolute_url': logo_absolute_url,
        'pdf_stamp_url': pdf_stamp_url,
        'pdf_footer_badge_url': pdf_footer_badge_url,
        'pdf_header_subtitle': header_subtitle,
        'pdf_header_subtitle_ar': header_subtitle_ar,
        'pdf_footer_services': footer_services,
        'pdf_footer_service_items': [s.strip() for s in footer_services.split('|') if s.strip()],
        'pdf_company_phones': phones,
        'pdf_lpg_badge_label': services_badge,
    }


def merge_pdf_branding(request, context: dict, *, for_weasyprint: bool = False) -> dict:
    out = dict(context)
    out.update(build_company_pdf_branding_context(request, for_weasyprint=for_weasyprint))
    out.setdefault('pdf_image_1_url', out.get('pdf_stamp_url', ''))
    out.setdefault('pdf_image_2_url', out.get('pdf_footer_badge_url', ''))
    return out
