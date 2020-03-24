import pytz
from django import template
from django.utils.timezone import now
from pretix.base.models import Event, SubEvent
from pretix.presale.views.organizer import CalendarView

register = template.Library()


@register.simple_tag(takes_context=True)
def load_calendar_data(context, request):
    """
    Calculates the data necessary for using the calendar.html template by using the CalendarView of pretix
    :param context: The context of the calling template
    :param request: The request the caused the rendering of the template
    :return:
    """
    month, year = _get_month_year(request)
    cal = CalendarView()
    cal.request = request
    cal.year = year
    cal.month = month
    context_data = cal.get_context_data()

    desired_attributes = ['years', 'months', 'weeks', 'before', 'after', 'date']
    context.update({key: value for key, value in context_data.items() if key in desired_attributes})
    return context


def _get_month_year(request):
    if 'year' in request.GET and 'month' in request.GET:
        try:
            return int(request.GET.get('month')), int(request.GET.get('year'))
        except ValueError:
            return now().month, now().year
    else:
        return _get_month_year_of_next_event(request)


def _get_month_year_of_next_event(request):
    next_event = Event.objects.filter(
        organizer=request.organizer,
        live=True,
        is_public=True,
        date_from__gte=now(),
        has_subevents=False
    ).order_by('date_from').first()
    next_subevent = SubEvent.objects.filter(
        event__organizer=request.organizer,
        event__is_public=True,
        event__live=True,
        active=True,
        is_public=True,
        date_from__gte=now()
    ).select_related('event').order_by('date_from').first()

    datetime_from = None
    if (next_subevent and not next_event) \
            or (next_event and next_subevent and next_subevent.date_from < next_event.date_from):
        datetime_from = next_subevent.date_from
        next_event = next_subevent.event
    elif next_event:
        datetime_from = next_event.date_from

    if datetime_from:
        tz = pytz.timezone(next_event.settings.timezone)
        year = datetime_from.astimezone(tz).year
        month = datetime_from.astimezone(tz).month
    else:
        year = now().year
        month = now().month

    return month, year
