import pytest
from django.utils.translation import ugettext as _
from pretix.base.models import Organizer, Team, User
from pretix.base.settings import GlobalSettingsObject

from ..helper_methods import __login_as_admin


@pytest.fixture
def env():
    admin = User.objects.create_superuser(email="admin@localhost", password="admin")
    not_an_admin = User.objects.create_user(email="casual@user.com", password="wannaBeAdmin")
    User.objects.create_user(email="worthless@user.com", password="nothing")
    organizer = Organizer.objects.create(name="Next Level Fachbereich", slug="FB9000")

    t = Team.objects.create(organizer=organizer, can_change_organizer_settings=True)
    t.members.add(admin)

    t2 = Team.objects.create(organizer=organizer, can_change_event_settings=True, can_change_items=True,
                             can_change_orders=True, can_change_organizer_settings=False, can_change_teams=True,
                             can_change_vouchers=True, can_create_events=True, can_manage_gift_cards=True,
                             can_view_orders=True, can_view_vouchers=True)
    t2.members.add(admin, not_an_admin)
    return organizer, admin


# region Permissions
@pytest.mark.django_db
def test_access_landing_page_before_settings(env, client):
    __login_as_admin(env, client, False)
    r1 = client.get("/FB09/")
    r2 = client.get("/FB9000/")
    assert r1.status_code == 404
    assert r1.templates[0].name == '404.html'
    assert r2.status_code == 200
    assert r2.templates[0].name == 'pretixpresale/organizers/index.html'


@pytest.mark.django_db
def test_user_has_correct_permissions(env, client):
    __login_as_admin(env, client, False)
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 200
    r2 = client.post('/control/organizer/FB09/landingpage/', data={'active': 'on'})
    assert r2.status_code == 404
    client.logout()

    client.login(email="casual@user.com", password="wannaBeAdmin")
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 403
    client.logout()

    client.login(email="worthless@user.com", password="nothing")
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 404
    client.logout()

    r1 = client.get('/control/organizer/FB9000/landingpage/')
    assert r1.status_code == 302


@pytest.mark.django_db
def test_organizer_not_allowed_to_use_plugin(env, client):
    gs = GlobalSettingsObject().settings
    gs.enable_landingpage_for_all_organizers = False
    gs.flush()

    __login_as_admin(env, client, False)
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 404
    available = _("This page is unavailable for the selected organizer")
    assert bytes(available, 'utf-8') in r.content

    r2 = client.post('/control/organizer/FB9000/landingpage/', data={'active': 'on'})
    assert r2.status_code == 404
    available = _("This page is unavailable for the selected organizer")
    assert bytes(available, 'utf-8') in r2.content


@pytest.mark.django_db
def test_organizer_allowed_to_use_plugin(env, client):
    gs = GlobalSettingsObject().settings
    gs.enable_landingpage_for_all_organizers = True
    gs.flush()
    __login_as_admin(env, client, False)
    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 200

    gs.enable_landingpage_for_all_organizers = False
    gs.enable_landingpage_individually = ['1']
    gs.flush()

    r = client.get('/control/organizer/FB9000/landingpage/')
    assert r.status_code == 200
# endregion
