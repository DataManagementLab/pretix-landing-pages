from _collections import OrderedDict
from django import forms
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import ugettext as _
from pretix.base.models.organizer import Organizer
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import register_global_settings
from pretix.control.permissions import (
    organizer_permission_required, staff_member_required,
)
from pretix.control.signals import nav_global, nav_organizer

from .views import is_plugin_available_for_organizer


@organizer_permission_required('can_change_organizer_settings')
@receiver(nav_organizer)
def add_landingpage_on_nav_page(sender, request=None, **kwargs):
    """
     Receive the 'nav_organizer' signal which triggers when controlling an organization.\n
     If this signal occurs, the 'Landing Page' tab will be added to the menu bar on the left side.\n
     With the added tab you'll have access to the Landing Page Settings
    """
    if not is_plugin_available_for_organizer(request.organizer):
        return []
    url = request.resolver_match
    return [{'label': _('Landing Page'),
             'url': reverse('plugins:pretix_landing_pages:landingpage_settings', kwargs={
                 'organizer': request.organizer.slug
             }),
             'active': (url.url_name == 'landingpage_settings'),
             'icon': 'file-text',
             }]


@staff_member_required()
@receiver(nav_global)
def add_startingpage_settings(sender, request, **kwargs):
    url = request.resolver_match
    return[{'label': _('Starting Page Settings'),
            'url': reverse('plugins:pretix_landing_pages:startingpage_settings'),
            'active': (url.url_name == 'startingpage_settings'),
            'icon': 'upload',
            'parent': reverse('control:global.settings'),
            }]


settings_hierarkey.add_default('enable_landingpage_individually', [], list)
settings_hierarkey.add_default('enable_landingpage_for_all_organizers', True, bool)


@receiver(register_global_settings, dispatch_uid='pretix_landing_pages_global_settings')
def register_global_settings(sender, **kwargs):
    choices = map(lambda x: (x.id, x), Organizer.objects.all())

    return OrderedDict([
        ('enable_landingpage_individually', forms.MultipleChoiceField(
            choices=choices,
            widget=forms.CheckboxSelectMultiple,
            required=False,
            label=_("Enable landing page plugin for organizer..."),
        )),
        ('enable_landingpage_for_all_organizers', forms.BooleanField(
            label=_('Enable landing page plugin for all organizers'),
            required=False,
            help_text=_('If enabled, this option overrides the selection above.')
        ))
    ])
