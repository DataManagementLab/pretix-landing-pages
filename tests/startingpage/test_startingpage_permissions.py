import pytest
from django.utils.timezone import now
from pretix.base.models import Organizer, Team, User

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


# region Permission
@pytest.mark.django_db
def test_access_starting_page_before_settings(env, client):
    __login_as_admin(env, client, False)
    r = client.get("")
    assert r.status_code == 200
    assert r.templates[0].name == 'pretixpresale/index.html'


@pytest.mark.django_db
def test_correct_permissions(env, client):
    __login_as_admin(env, client, False)
    r = client.get('')
    assert r.status_code == 200
    r1 = client.get('/control/startingpage_settings/')
    r2 = client.post('/control/startingpage_settings/', data={'deleteAll': 'DeleteAll'})
    assert r1.status_code == 302
    assert r1.url == '/control/sudo/?next=/control/startingpage_settings/'
    assert r2.status_code == 302
    assert r2.url == '/control/sudo/?next=/control/startingpage_settings/'

    env[1].staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    env[1].save()
    r = client.get('/control/startingpage_settings/')
    assert r.status_code == 200
    client.logout()

    client.login(email="casual@user.com", password="wannaBeAdmin")
    r = client.get('/control/startingpage_settings/')
    assert r.status_code == 403
    client.logout()

    r = client.get('/control/startingpage_settings/')
    assert r.status_code == 302
# endregion
