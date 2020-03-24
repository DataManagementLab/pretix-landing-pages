import os

from django.contrib import messages
from django.db.models.functions.datetime import datetime
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import engines
from django.utils.translation import ugettext as _
from django.views import View
from django.views.generic import TemplateView
from django_scopes import scopes_disabled
from pretix.base.models import Event, Organizer
from pretix.base.settings import GlobalSettingsObject
from pretix.control.permissions import (
    administrator_permission_required, organizer_permission_required,
)
from pretix.control.views.organizer import (
    AdministratorPermissionRequiredMixin, OrganizerPermissionRequiredMixin,
)
from pretix.presale.views.organizer import OrganizerIndex
from pretix.settings import DATA_DIR

from .forms import (
    LandingpageFilesForm, LandingpageSettingsForm, RedirectForm,
    UploadStartingPageForm,
)
from .models import (
    LandingpageFile, LandingpageSettings, StartingpageFile,
    StartingpageSettings,
)

"""
The path to the directory that stores the landing page template files.
The files for of each organization are stored in a separate subdirectory of that directory for namespacing.
The organizations subdirectory is named after the persistent id of the organizer (not the slug).
"""
template_base_dir = os.path.join(DATA_DIR, 'templates', 'landing_pages')

# The path to the directory that stores the starting page template files.
starting_page_base_dir = os.path.join(DATA_DIR, 'templates', 'starting_pages')


def organizer_index(request, organizer):
    """
    loads upcoming and previous events for an organization
    renders the custom landing page for a given organization
    if the plugin is disabled, it displays the default organizer page
    :param request: httpRequest of the user
    :param organizer: slug of the organizer
    :return: httpResponse containing the custom landing page or the default view for an organizer
    """
    try:
        organizer_model = Organizer.objects.get(slug=organizer)
    except Organizer.DoesNotExist:
        raise Http404(_("The selected organizer was not found."))
    request.organizer = organizer_model

    with scopes_disabled():
        plugin_available = is_plugin_available_for_organizer(request.organizer)
        plugin_activated = __plugin_activated_by_organizer(request.organizer)
        index_available = __index_file_available(request.organizer)
        if not plugin_available or not plugin_activated or not index_available:
            return OrganizerIndex.as_view()(request, kwargs={'organizer': organizer})

        upcoming_events = Event.objects.filter(
            organizer_id=organizer_model.id,
            date_from__gt=datetime.now(),
            live=1,
            is_public=1
        )
        previous_events = Event.objects.filter(
            organizer_id=organizer_model.id,
            date_from__lte=datetime.now(),
            live=1,
            is_public=1
        )

        context = {
            'upcoming_events': upcoming_events,
            'previous_events': previous_events
        }
        return render(request, 'landing_pages/%d/index.html' % organizer_model.id, context=context)


def starting_page_index(request):
    """
    renders the custom starting page of the Pretix installation
    @param request: httpRequest of the user
    @return: httpResponse containing the custom starting page
    """
    if is_redirect_activated() and get_redirect_link():
        return redirect(get_redirect_link())
    else:
        setting, _ = StartingpageSettings.objects.get_or_create(pk=1)
        if setting.index.name and is_startingpage_activated():
            return render(request, 'starting_pages/index.html')
        else:
            return TemplateView.as_view(template_name='pretixpresale/index.html')(request)


class LandingpageSettingsView(OrganizerPermissionRequiredMixin, View):
    """
        handles requests for the settings page of the plugin for an organizer
        if the status of the landingpage is changed (User clicks on "save", the whole template cache will be invalidated
    """
    template_name = "landingpage_upload.html"
    permission = 'can_change_organizer_settings'

    def get(self, request, organizer):
        if not is_plugin_available_for_organizer(request.organizer):
            raise Http404(_("This page is unavailable for the selected organizer"))
        return self.__render_page(request, False, False, False, False, LandingpageFilesForm())

    def post(self, request, organizer):
        if not is_plugin_available_for_organizer(request.organizer):
            raise Http404(_("This page is unavailable for the selected organizer"))

        settings_form = LandingpageSettingsForm(request.POST)
        file_form = LandingpageFilesForm(request.POST, request.FILES)
        saved, uploaded, duplicated, failed = False, False, False, True
        if settings_form.is_valid() and file_form.is_valid():
            saved = True
            settings_model, __ = LandingpageSettings.objects.get_or_create(organizer=request.organizer)
            uploaded_files = file_form.files.getlist('file_field')
            override_files = file_form.cleaned_data['override_files']
            duplicated_files = self.__save_uploaded_files(request, uploaded_files, override_files, settings_model)

            failed = self.__save_landingpage_settings(request, settings_form, settings_model)
            """
            template cache (for the organizer landing page) needs to be reset or else the changes won't be
            immediately) visible. Might need adoption if there is a different template cache in use than the
            django default cached loader
            """
            # TODO still needed?
            invalidate_template_in_cache("landing_pages/%d/index.html" % request.organizer.id)
            uploaded = (len(uploaded_files) > 0) and (not duplicated_files or override_files)
            duplicated = duplicated_files and not override_files
            file_form = LandingpageFilesForm()

        return self.__render_page(request, saved, uploaded, duplicated, failed, file_form)

    def __save_landingpage_settings(self, request, settings_form, settings_model):
        enabled = settings_form.cleaned_data['active']
        index_available = settings_model.index.name
        if index_available or not enabled:
            settings_model.active = enabled
            settings_model.log_action(
                action='pretix_landing_pages.landingpagesettings.status_changed',
                data={'new_status': 'active' if enabled else 'inactive'},
                user=request.user)
            settings_model.save()
        return enabled and index_available == ''

    def __save_uploaded_files(self, request, uploaded_files, override_files, settings_model):
        existing_files = LandingpageFile.objects.filter(organizer=request.organizer)
        uploaded_files_names = list(map(lambda x: x.name, uploaded_files))
        duplicated_files = (settings_model.index and 'index.html' in uploaded_files_names) \
            or existing_files.filter(filename__in=uploaded_files_names).count() > 0

        if not duplicated_files or override_files:
            for f in uploaded_files:
                # uploaded file is index.html
                if f.name == 'index.html':
                    settings_model.index = f
                    settings_model.log_action('pretix_landing_pages.landingpagesettings.index_updated',
                                              user=request.user)
                    settings_model.save()
                # uploaded file is something else
                else:
                    file_model, __ = LandingpageFile.objects.get_or_create(
                        organizer=request.organizer, filename=f.name)
                    file_model.file = f
                    file_model.log_action('pretix_landing_pages.landingpagefile.updated',
                                          data={'file': f.name}, user=request.user)
                    file_model.save()
        return duplicated_files

    def __render_page(self, request, saved, uploaded, duplicated, failed, file_form):
        # Load saved settings into form
        settings_model, __ = LandingpageSettings.objects.get_or_create(organizer=request.organizer)
        settings_model.save()
        settings_form = LandingpageSettingsForm(initial={'active': settings_model.active})

        # Load information of saved files
        file_models = LandingpageFile.objects.filter(organizer=request.organizer)
        file_information = [(os.path.splitext(file.filename) + (file.filename,)) for file in file_models]
        if settings_model.index:
            file_information += [('index', '.html', 'index.html')]

        return render(request, "pretixplugins/pretix_landing_pages/" + self.template_name,
                      {'form': settings_form,
                       'file_form': file_form,
                       'file_information': file_information,
                       'organizer': request.organizer,
                       'saved': saved,
                       'uploaded': uploaded,
                       'duplicated': duplicated,
                       'failed': failed})


@organizer_permission_required('can_change_organizer_settings')
def delete_all_organizer_files(request, organizer):
    """
    deletes all files uploaded by the specified organizer
    :param request: The issuing request
    :param organizer: the slug of the organizer whose files are to be deleted
    :return: a redirect to the landingepage_settings view
    """
    try:
        if request.method == 'POST':
            files = LandingpageFile.objects.filter(organizer=request.organizer)
            for f in files:
                f.log_action('pretix_landing_pages.landingpagefile.deleted',
                             data={'file': f.filename}, user=request.user)
                f.delete()
            settings = LandingpageSettings.objects.get(organizer=request.organizer)
            settings.log_action('pretix_landing_pages.landingpagesettings.index_deleted', user=request.user)
            index = settings.index.name
            settings.index.delete()
            settings.active = False
            settings.save()
            if index or files:
                messages.success(request, _("Successfully deleted."))
    except:
        messages.error(request, _("Deletion failed."))

    return redirect('plugins:pretix_landing_pages:landingpage_settings',
                    organizer=organizer)


@organizer_permission_required('can_change_organizer_settings')
def delete_organizer_file(request, organizer, filename):
    """
    deletes a file uploaded by the specified organizer
    :param request: the issuing request
    :param organizer: the slug of the organizer whose files are to be deleted
    :param filename: the file to delete
    :return: a redirect to the landingepage_settings view
    """
    try:
        if request.method == 'POST':
            if filename == 'index.html':
                settings = LandingpageSettings.objects.get(organizer=request.organizer)
                settings.log_action('pretix_landing_pages.landingpagesettings.index_deleted', user=request.user)
                settings.index.delete()
                settings.active = False
                settings.save()
            else:
                file = LandingpageFile.objects.get(organizer=request.organizer, filename=filename)
                file.log_action('pretix_landing_pages.landingpagefile.deleted',
                                data={'file': filename}, user=request.user)
                file.delete()
            messages.success(request, _("Successfully deleted."))
    except:
        messages.error(request, _("Deletion failed."))

    return redirect('plugins:pretix_landing_pages:landingpage_settings', organizer=organizer)


def invalidate_template_in_cache(template):
    """
    invalidates the specified template in the registers caches
    :param template: the name of the template, e.g. pretixplugins/pretix_landing_pages/startingpage_settings.html
    """
    for engine in engines.all():
        for template_loader in engine.engine.template_loaders:
            try:
                key = template_loader.cache_key(template)
                template_loader.get_template_cache.pop(key, None)
                template_loader.template_cache.pop(key, None)
            except AttributeError:  # pragma: no cover
                pass


class StartingpageSettingsView(AdministratorPermissionRequiredMixin, View):
    """
    Displays and allows editing of the startingpage settings
    """
    template_name = "startingpage_settings.html"

    def get(self, request):
        return self.__render_page(request, {})

    def __render_page(self, request, context):
        os.makedirs(starting_page_base_dir, exist_ok=True)
        redirect_form = RedirectForm(initial={
            'enable_redirect': is_redirect_activated(),
            'redirect_link': get_redirect_link(),
        })
        file_information = self.__get_startingpage_files()
        starting_page_status = is_startingpage_activated()
        if (not file_information and starting_page_status) or ('index', '.html', 'index.html') not in file_information:
            self.__set_starting_page(False, request.user)
            upload_form = UploadStartingPageForm(initial={
                'use_startingpage': False,
            })
        else:
            upload_form = UploadStartingPageForm(initial={
                'use_startingpage': starting_page_status,
            })
        if os.path.isdir(starting_page_base_dir):
            context['file_information'] = file_information
        context['upload_form'] = upload_form
        context['redirect_form'] = redirect_form
        return render(request, "pretixplugins/pretix_landing_pages/" + self.template_name, context)

    def post(self, request):
        context = {}
        if 'apply' in request.POST:
            context['saved'], context['uploaded'] = self.__apply_starting_page_settings(request)
        context['status_enabled'] = True

        return self.__render_page(request, context)

    @staticmethod
    def __set_redirect_status_and_link(enable_bool, link, user):
        redirect_object = StartingpageSettings.objects.get_or_create(pk=1)[0]
        redirect_object.redirect_link = link
        redirect_object.redirect_active = enable_bool
        redirect_object.save()
        redirect_object.log_action(
            'pretix_landing_pages.startingpage_settings.redirect_changed',
            data={'new_status': 'redirecting' if enable_bool else 'not redirecting', 'link': link},
            user=user
        )

    def __apply_starting_page_settings(self, request):
        redirect_form = RedirectForm(request.POST)
        upload_form = UploadStartingPageForm(request.POST, request.FILES)
        if redirect_form.is_valid() and upload_form.is_valid():
            uploaded_files = upload_form.files.getlist('file_field')
            if uploaded_files:
                sth_to_upload = True
            else:
                sth_to_upload = False
            is_redirecting = redirect_form['enable_redirect'].data
            redirect_link = redirect_form['redirect_link'].data
            is_using_startingpage = upload_form['use_startingpage'].data
            if self.__check_settings_config_validity(is_redirecting, redirect_link,
                                                     is_using_startingpage, uploaded_files):
                self.__upload_all_files(request, uploaded_files)
                self.__set_redirect_status_and_link(is_redirecting, redirect_link, request.user)
                self.__set_starting_page(is_using_startingpage, request.user)
                return True, sth_to_upload

        return False, False

    def __check_settings_config_validity(self, is_redirecting, redirect_link, is_using_startingpage, uploaded_files):
        if is_redirecting and is_using_startingpage:
            return False
        elif is_redirecting and redirect_link == '':
            return False
        elif is_using_startingpage and uploaded_files:
            return_val = False
            for f in uploaded_files:
                if f.name == "index.html":
                    return_val = True
            return return_val
        elif is_using_startingpage and not self.__get_startingpage_files().__contains__(('index', '.html', 'index.html')):
            return False
        else:
            return True

    @staticmethod
    def __upload_all_files(request, uploaded_files):
        settings_model = StartingpageSettings.objects.get_or_create(pk=1)[0]
        logdata = {}
        for uf in uploaded_files:
            if uf.name == 'index.html':
                logdata[uf.name] = 'updated'
                settings_model.index = uf
                settings_model.save()
                settings_model.log_action(
                    'pretix_landing_pages.startingpagesettings.index_updated',
                    data=logdata,
                    user=request.user)
            else:
                file_model, created = StartingpageFile.objects.get_or_create(filename=uf.name)
                logdata[uf.name] = 'updated'
                file_model.file = uf
                file_model.save()
                file_model.log_action(
                    'pretix_landing_pages.startingpagefile.updated',
                    data=logdata,
                    user=request.user)
        invalidate_template_in_cache("starting_pages/index.html")

    @staticmethod
    def __set_starting_page(setting_bool, user):
        setting = StartingpageSettings.objects.get_or_create(pk=1)[0]
        setting.startingpage_active = setting_bool
        setting.save()
        setting.log_action(
            'pretix_landing_pages.startingpagesettings.custom_status_changed',
            data={'new_status': 'active' if setting_bool else 'inactive'},
            user=user
        )

    @staticmethod
    def __get_startingpage_files():
        existing_files = StartingpageFile.objects.all()
        file_information = [(os.path.splitext(file.filename) + (file.filename,)) for file in existing_files]
        startingpage_file, created = StartingpageSettings.objects.get_or_create(pk=1)
        if not created and startingpage_file.index.name:
            file_information += [('index', '.html', 'index.html')]
        return file_information


@administrator_permission_required()
def delete_all_startingpage_files(request):
    """
    deletes all files uploaded by the admin
    :param request: The issuing request
    :return: a redirect to the startingpage_settings view
    """
    try:
        if request.method == 'POST':
            files = StartingpageFile.objects.all()
            for f in files:
                f.log_action('pretix_landing_pages.startingpagefile.deleted',
                             data={'file': f.filename}, user=request.user)
                f.delete()
            settings = StartingpageSettings.objects.get(pk=1)
            index = settings.index.name
            if index:
                settings.log_action('pretix_landing_pages.startingpagesettings.index_deleted', user=request.user)
                settings.index.delete()
                settings.startingpage_active = False
                settings.save()
            if index or files:
                messages.success(request, _("Successfully deleted."))
    except:
        messages.error(request, _("Deletion failed."))

    return redirect('plugins:pretix_landing_pages:startingpage_settings')


@administrator_permission_required()
def delete_startingpage_file(request, filename):
    """
    deletes a file uploaded by the admin
    :param request: the issuing request
    :param filename: the file to delete
    :return: a redirect to the startinpage_settings view
    """
    try:
        if request.method == 'POST':
            if filename == 'index.html':
                settings = StartingpageSettings.objects.get(pk=1)
                if settings.index.name:
                    settings.log_action('pretix_landing_pages.startingpagesettings.index_deleted', user=request.user)
                    settings.index.delete()
                    settings.startingpage_active = False
                    settings.save()
            else:
                file = StartingpageFile.objects.get(filename=filename)
                file.log_action('pretix_landing_pages.startingpagefile.deleted',
                                data={'file': filename}, user=request.user)
                file.delete()
            messages.success(request, _("Successfully deleted."))
    except:
        messages.error(request, _("Deletion failed."))

    return redirect('plugins:pretix_landing_pages:startingpage_settings')


def is_startingpage_activated():
    return StartingpageSettings.objects.get_or_create(pk=1)[0].startingpage_active


def is_redirect_activated():
    try:
        return StartingpageSettings.objects.get(pk=1).redirect_active
    except StartingpageSettings.DoesNotExist:
        return False


def get_redirect_link():
    try:
        return StartingpageSettings.objects.get(pk=1).redirect_link
    except StartingpageSettings.DoesNotExist:
        return ""


def is_plugin_available_for_organizer(organizer):
    individually_activated = str(organizer.id) in GlobalSettingsObject().settings.get('enable_landingpage_individually')
    globally_activated = GlobalSettingsObject().settings.get('enable_landingpage_for_all_organizers')
    return individually_activated or globally_activated


def __index_file_available(organizer):
    return LandingpageSettings.objects.get_or_create(pk=organizer.id)[0].index.name


def __plugin_activated_by_organizer(organizer):
    return LandingpageSettings.objects.get_or_create(pk=organizer.id)[0].active
