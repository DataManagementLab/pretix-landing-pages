from django import forms
from django.core import validators
from django.utils.translation import ugettext_lazy as _

from .models import LandingpageSettings

filename_validator = validators.RegexValidator(
    r'^[-a-zA-Z0-9_\.]+\Z',
    _('Filenames may only contain latin letters, underscores, dots, hyphens and numbers'),
    'invalid'
)


class LandingpageSettingsForm(forms.ModelForm):

    class Meta:
        model = LandingpageSettings
        fields = ['active']
        labels = {'active': _("Use custom landing page")}


class LandingpageFilesForm(forms.Form):
    file_field = forms.FileField(widget=forms.ClearableFileInput(
        attrs={'multiple': True}),
        help_text=_("The main HTML page needs to be named \"index.html\". "
                    "Filenames may only contain latin letters, underscores, dots, hyphens and numbers."),
        required=False,
        validators=[filename_validator],
        label=_("File upload:")
    )

    override_files = forms.BooleanField(
        label=_('Override'),
        required=False,
        help_text=_("If selected, uploaded files that already exist will be overwritten")
    )


class UploadStartingPageForm(forms.Form):
    use_startingpage = forms.BooleanField(
        label=_("<strong>Use uploaded starting page</strong>"),
        required=False,
    )
    file_field = forms.FileField(widget=forms.ClearableFileInput(
        attrs={'multiple': True}),
        label=_("Files:"),
        help_text=_("The main HTML page needs to be named \"index.html\". "
                    "Filenames may only contain latin letters, underscores, dots, hyphens and numbers."),
        required=False,
        validators=[filename_validator]
    )


class RedirectForm(forms.Form):
    enable_redirect = forms.BooleanField(
        label=_("<strong>Enable redirect</strong>"),
        required=False,
    )
    redirect_link = forms.URLField(
        label=_("Enter redirect URL:"),
        required=False,
    )
