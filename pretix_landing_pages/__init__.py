from django.utils.translation import ugettext_lazy
from pretix.base.plugins import PluginConfig


class PluginApp(PluginConfig):
    name = 'pretix_landing_pages'
    verbose_name = 'Custom landing pages for pretix organizers'

    class PretixPluginMeta:
        name = ugettext_lazy('Pretix Landing Pages')
        author = 'BP 2019/20 Gruppe 45'
        description = ugettext_lazy('Enables users to create custom landingpages for organizers')
        visible = True
        version = '0.9.1'
        compatibility = "pretix>=3.4.0"

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_landing_pages.PluginApp'
