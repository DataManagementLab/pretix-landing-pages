import os
import pathlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from pretix.base.models import LogEntry, Organizer, Team, User
from pretix.base.settings import GlobalSettingsObject
from pretix_landing_pages.models import LandingpageSettings
from pretix_landing_pages.views import template_base_dir

from ..helper_methods import __login_as_admin


@pytest.fixture
def env():
    admin = User.objects.create_superuser(email="admin@localhost", password="admin")
    organizer = Organizer.objects.create(name="Next Level Fachbereich", slug="FB9000")
    setting = LandingpageSettings.objects.create(organizer=organizer, active=False)
    t = Team.objects.create(organizer=organizer, can_change_organizer_settings=True)
    t.members.add(admin)
    return organizer, admin, template_base_dir, setting


# region Correct Display
@pytest.mark.django_db
def test_active_but_custom_page_doesnt_exist(env, client):
    env[3].active = True
    env[3].save()
    r = client.get("/FB9000/")
    assert r.template_name[0] == 'pretixpresale/organizers/index.html'


@pytest.mark.django_db
def test_only_active_with_index_file(env, client):
    env[3].active = False
    env[3].save()
    __login_as_admin(env, client, False)
    client.post('/control/organizer/FB9000/landingpage/', data={'active': 'on'})
    client.post('/control/organizer/FB9000/landingpage/', data={'active': ''})
    assert LandingpageSettings.objects.get(pk=env[0]).active is False
    index_file = SimpleUploadedFile('index.html', content=b"TestTest")
    client.post('/control/organizer/FB9000/landingpage/', data={'active': 'on', 'file_field': [index_file]})
    assert LandingpageSettings.objects.get(pk=env[0]).active is True


@pytest.mark.django_db
def test_uploaded_page_is_shown_if_active(env, client):
    env[3].active = True
    index = SimpleUploadedFile('index.html', content=b"<html><body>Das ist ein Test.html</body></html>")
    env[3].index = index
    env[3].save()
    r = client.get("/FB9000/")
    assert r.templates[0].name == 'landing_pages/1/index.html'


@pytest.mark.django_db
def test_organizer_does_not_exist(env, client):
    r = client.get('/xyz/')
    assert r.status_code == 404


@pytest.mark.django_db
def test_default_page_is_shown_if_inactive(env, client):
    r = client.get("/FB9000/")
    assert r.status_code == 200
    assert 'pretixpresale/organizers/index.html' == r.context_data['view'].template_name

    gs = GlobalSettingsObject().settings
    gs.enable_landingpage_for_all_organizers = False
    gs.flush()
    env[3].active = True
    env[3].save()
    r = client.get("/FB9000/")
    assert r.status_code == 200
    assert 'pretixpresale/organizers/index.html' == r.context_data['view'].template_name
# endregion


# region UI Element
@pytest.mark.django_db
def test_enable_ui_element_exists(env, client):
    __login_as_admin(env, client, False)
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.resolver_match.view_name == 'plugins:pretix_landing_pages:landingpage_settings'
# endregion


# region Change Settings
@pytest.mark.django_db
def test_change_active_status_by_organizer(env, client):
    base_log_count_active = __log_entry_activation_count('active')
    base_log_count_inactive = __log_entry_activation_count('inactive')
    index_file = SimpleUploadedFile('index.html', content=b"TestTest")
    __login_as_admin(env, client, False)

    client.post('/control/organizer/FB9000/landingpage/', data={'active': 'on', 'file_field': [index_file]})
    assert LandingpageSettings.objects.get(pk=env[0]).active is True
    assert __log_entry_activation_count('active') == base_log_count_active + 1

    client.post('/control/organizer/FB9000/landingpage/', data={})
    assert LandingpageSettings.objects.get(pk=env[0]).active is False
    assert __log_entry_activation_count('inactive') == base_log_count_inactive + 1

    client.post('/control/organizer/FB9000/landingpage/', data={'active': 'on'})
    assert LandingpageSettings.objects.get(pk=env[0]).active is True
    assert __log_entry_activation_count('active') == base_log_count_active + 2


@pytest.mark.django_db
def test_change_active_status_by_admin(env, client):
    assert GlobalSettingsObject().settings.get('enable_landingpage_individually') == []
    assert GlobalSettingsObject().settings.get('enable_landingpage_for_all_organizers') is True
    __login_as_admin(env, client, True)
    Organizer.objects.create(name="Dummy", slug="dummy")

    form_fields = client.get('/control/global/settings/').context_data['form'].fields
    required_data = {name: field.initial for name, field in form_fields.items() if field.required}
    post_data = dict(required_data, **{'enable_landingpage_individually': ['1', '2']})
    client.post('/control/global/settings/', post_data)

    gs = GlobalSettingsObject().settings
    assert gs.get('enable_landingpage_individually') == ['1', '2']
    assert gs.get('enable_landingpage_for_all_organizers') is False
# endregion


# region Helper
def __write_text_to_landingpage_of_organizer(text, organizer_id):
    organizer_template_path = os.path.join(template_base_dir, str(organizer_id))
    os.makedirs(organizer_template_path)
    file = pathlib.PosixPath(os.path.join(organizer_template_path, "index.html"))
    file.write_text(text)


def __log_entry_activation_count(new_status):
    return LogEntry.objects \
        .filter(action_type='pretix_landing_pages.landingpagesettings.status_changed') \
        .filter(data='{\"new_status\": \"%s\"}' % new_status) \
        .count()
# endregion
