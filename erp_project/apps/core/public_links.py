"""Canonical list of no-login (self-service) portal URLs for the login page and help text."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse


def public_portal_link_specs() -> list[dict]:
    """Static metadata; URLs resolved per request in ``public_portal_links``."""
    return [
        {
            'title': 'Mark attendance',
            'description': 'Clock in and out with your employee code or name (location optional).',
            'url_name': 'hr:public_attendance',
            'icon': 'fa-clock',
        },
        {
            'title': 'Apply for leave',
            'description': 'Submit a leave request for HR approval.',
            'url_name': 'hr:public_leave_apply',
            'icon': 'fa-calendar-check',
        },
        {
            'title': 'Submit expense bill',
            'description': 'Upload a vendor bill or receipt for expense claim processing.',
            'url_name': 'purchase:public_expense_submit',
            'icon': 'fa-receipt',
        },
        {
            'title': 'Upload project files',
            'description': 'Send photos or documents to a project folder.',
            'url_name': 'projects:public_upload',
            'icon': 'fa-cloud-upload-alt',
        },
        {
            'title': 'Request project items',
            'description': 'Request inventory items for a job site (select project on the form).',
            'url_name': 'projects:public_item_request',
            'icon': 'fa-boxes',
        },
        {
            'title': 'Upload customer documents',
            'description': 'Share files with CRM for a lead or customer record.',
            'url_name': 'crm:public_upload',
            'icon': 'fa-file-upload',
        },
    ]


def public_portal_links(request) -> list[dict]:
    out: list[dict] = []
    for spec in public_portal_link_specs():
        try:
            path = reverse(spec['url_name'])
        except NoReverseMatch:
            continue
        out.append(
            {
                'title': spec['title'],
                'description': spec['description'],
                'icon': spec.get('icon', 'fa-link'),
                'url': request.build_absolute_uri(path),
                'path': path,
            }
        )
    return out
