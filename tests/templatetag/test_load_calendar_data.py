from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope
from pretix.base.models import Event, Organizer, SubEvent
from pretix_landing_pages.templatetags.load_calendar_data import (
    load_calendar_data,
)


class ContextMock(dict):
    def __init__(self, request):
        super().__init__()
        self.request = request if request else {}


class RequestMock(object):
    def __init__(self, organizer, year=None, month=None):
        super().__init__()
        self.organizer = organizer if organizer else {}
        self.session = {}
        self.GET = {}
        if year:
            self.GET['year'] = year
        if month:
            self.GET['month'] = month


@pytest.fixture
def env():
    orga = Organizer.objects.create(slug="dummy", name="Dummy")
    event_prev_1 = Event.objects.create(
        organizer=orga,
        name="event_prev_1",
        slug="prev1", live=1,
        date_from=now() - timedelta(days=32),
        has_subevents=True
    )
    event_prev_2 = Event.objects.create(
        organizer=orga,
        name="event_prev_2",
        slug="prev2", live=1,
        date_from=now() - timedelta(days=63),
    )
    event_post_2 = Event.objects.create(
        organizer=orga,
        name="event_post_1",
        slug="post1", live=1,
        date_from=now() + timedelta(days=63),
    )
    return orga, event_prev_1, event_prev_2, event_post_2


@pytest.mark.django_db
def test_next_event_in_future(env):
    _load_data_and_assert_month_year(env[0], env[3].date_from.month, env[3].date_from.year)

    event_now = Event.objects.create(
        organizer=env[0],
        name="event_now",
        slug="now", live=1,
        date_from=now() + timedelta(minutes=5),
        date_to=now(),
    )

    _load_data_and_assert_month_year(env[0], event_now.date_from.month, event_now.date_from.year)


@pytest.mark.django_db
def test_next_subevent_in_future(env):
    with scope(organizer=env[0]):
        subevent = SubEvent.objects.create(
            event=env[1],
            active=True,
            name='subevent1',
            date_from=now() + timedelta(days=32)
        )

    _load_data_and_assert_month_year(env[0], subevent.date_from.month, subevent.date_from.year)


@pytest.mark.django_db
def test_no_events(env):
    with scope(organizer=env[0]):
        Event.objects.filter(slug="post1").delete()

    _load_data_and_assert_month_year(env[0], now().month, now().year)


@pytest.mark.django_db
def test_month_year_in_request(env):
    custom_year = 2018
    custom_month = 5
    request = RequestMock(env[0], year=custom_year, month=custom_month)
    _load_data_and_assert_month_year(env[0], custom_month, custom_year, request)

    request.GET['year'] = 'no_year'
    _load_data_and_assert_month_year(env[0], now().month, now().year, request)


def _load_data_and_assert_month_year(organizer, expected_month, expected_year, request=None):
    request = request if request else RequestMock(organizer)
    context = ContextMock(request)

    with scope(organizer=organizer):
        calendar_data = load_calendar_data(context, request)

    assert calendar_data['date'].month == expected_month
    assert calendar_data['date'].year == expected_year

    desired_attributes = ['years', 'months', 'weeks', 'before', 'after', 'date']
    for key in desired_attributes:
        assert calendar_data[key] is not None
