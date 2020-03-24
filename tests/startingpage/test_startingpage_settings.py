import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from pretix.base.models import LogEntry, User
from pretix_landing_pages.models import StartingpageSettings

from ..helper_methods import __login_as_admin


@pytest.fixture
def env():
    admin = User.objects.create_superuser(email="admin@localhost", password="admin")
    User.objects.create_user(email="casual@user.com", password="wannaBeAdmin")
    setting = StartingpageSettings(redirect_active=False)
    return setting, admin


# region UI Element
@pytest.mark.django_db
def test_enable_ui_element_exists(env, client):
    client.login(email='admin@localhost', password='admin')
    env[1].staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    env[1].save()
    r = client.get('/control/startingpage_settings/')
    temp_name = r.templates[0].name
    assert temp_name == "pretixplugins/pretix_landing_pages/startingpage_settings.html"
# endregion


# region Correct Display
@pytest.mark.django_db
def test_active_but_no_upload(client):
    setting, _ = StartingpageSettings.objects.get_or_create(pk=1)
    setting.index = None
    setting.startingpage_active = True
    setting.save()
    r = client.get("/")
    assert r.templates[0].name == 'pretixpresale/index.html'


@pytest.mark.django_db
def test_uploaded_page_is_shown_if_active(env, client):
    file_a = SimpleUploadedFile('index.html',
                                content=b"<html><body>Das ist ein Test.html</body></html>",
                                content_type="text/plain")
    setting, _ = StartingpageSettings.objects.get_or_create(pk=1)
    setting.index = file_a
    setting.startingpage_active = True
    setting.save()
    r = client.get("/")
    assert r.templates[0].name == 'starting_pages/index.html'


@pytest.mark.django_db
def test_active_but_no_link(env, client):
    setting = StartingpageSettings(redirect_active=True)
    setting.save()
    r = client.get("/")
    assert r.context_data['view'].template_name == "pretixpresale/index.html"


@pytest.mark.django_db
def test_active_and_link(env, client):
    setting = StartingpageSettings(redirect_active=True, redirect_link="https://www.google.de")
    setting.save()
    r = client.get("/", follow=False)
    assert r.url == "https://www.google.de"
# endregion


# region Settings
@pytest.mark.django_db
def test_change_active_status_startingpage(env, client):
    setting = StartingpageSettings(startingpage_active=False)
    setting.save()
    file_a = SimpleUploadedFile('index.html',
                                content=b"<html><body>Das ist ein Test.html</body></html>",
                                content_type="text/plain")
    client.login(email='admin@localhost', password='admin')
    env[1].staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    env[1].save()
    client.post('/control/startingpage_settings/',
                data={'use_startingpage': 'on', 'file_field': [file_a], 'redirect_link': '', 'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).startingpage_active is True
    client.post('/control/startingpage_settings/', data={'redirect_link': '', 'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).startingpage_active is False


@pytest.mark.django_db
def test_change_active_status_redirect(env, client):
    base_active_count = __log_entry_redirect_activation_count("redirecting")
    base_inactive_count = __log_entry_redirect_activation_count("not redirecting")

    setting = StartingpageSettings(redirect_active=False, redirect_link="")
    setting.save()
    __login_as_admin(env, client, True)
    client.post('/control/startingpage_settings/',
                data={'enable_redirect': 'on', 'redirect_link': 'https://www.google.de', 'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).redirect_active is True
    assert StartingpageSettings.objects.get(pk=1).redirect_link == 'https://www.google.de'
    assert __log_entry_redirect_activation_count("redirecting") == base_active_count + 1
    assert __log_entry_redirect_activation_count("not redirecting") == base_inactive_count

    client.post('/control/startingpage_settings/', data={'redirect_link': 'https://www.pretix.eu', 'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).redirect_active is False
    assert StartingpageSettings.objects.get(pk=1).redirect_link == 'https://www.pretix.eu'
    assert __log_entry_redirect_activation_count("redirecting") == base_active_count + 1
    assert __log_entry_redirect_activation_count("not redirecting") == base_inactive_count + 1
    assert LogEntry.objects\
        .filter(data__contains="\"link\": \"https://www.pretix.eu\"")\
        .filter(action_type='pretix_landing_pages.startingpage_settings.redirect_changed')\
        .count() == 1

    client.post('/control/startingpage_settings/',
                data={'enable_redirect': 'on', 'redirect_link': '', 'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).redirect_active is False
    assert __log_entry_redirect_activation_count("redirecting") == base_active_count + 1
    assert __log_entry_redirect_activation_count("not redirecting") == base_inactive_count + 1


@pytest.mark.django_db
def test_invalid_input_configuration(env, client):
    setting = StartingpageSettings(startingpage_active=False, redirect_link=False)
    setting.save()
    __login_as_admin(env, client, True)
    client.post('/control/startingpage_settings/',
                data={'use_startingpage': 'on', 'enable_redirect': 'on', 'redirect_link': 'https://www.google.de',
                      'apply': 'Apply'})
    assert StartingpageSettings.objects.get(pk=1).startingpage_active is False
    assert StartingpageSettings.objects.get(pk=1).redirect_active is False
    client.post('/control/startingpage_settings/',
                data={'use_startingpage': 'on', 'redirect_link': '', 'apply': 'Apply'})
    assert setting.startingpage_active is False
# endregion


# region Helper
def __log_entry_redirect_activation_count(new_status):
    return LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpage_settings.redirect_changed') \
        .filter(data__contains='\"new_status\": \"%s\"' % new_status) \
        .count()
# endregion
