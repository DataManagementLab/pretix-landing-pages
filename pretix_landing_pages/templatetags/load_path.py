from urllib.parse import urljoin

from django import template
from pretix.settings import MEDIA_URL
from pretix_landing_pages.models import LandingpageFile, StartingpageFile

register = template.Library()


@register.simple_tag(takes_context=True)
def load_path(context, filename):
    # distinguish between organizer page and starting page
    if hasattr(context.request, 'organizer'):
        slug = context.request.organizer.slug
        file_entry = LandingpageFile.objects.filter(organizer__slug=slug, filename=filename).first()
        if file_entry is not None:
            return urljoin(MEDIA_URL, str(file_entry.file))
    else:
        file_entry = StartingpageFile.objects.filter(filename=filename).first()
        if file_entry is not None:
            return urljoin(MEDIA_URL, str(file_entry.file))
    return ''
