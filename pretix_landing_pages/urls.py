from django.conf.urls import url

from .views import (
    LandingpageSettingsView, StartingpageSettingsView,
    delete_all_organizer_files, delete_all_startingpage_files,
    delete_organizer_file, delete_startingpage_file, organizer_index,
    starting_page_index,
)

urlpatterns = [
    url(r'^control/organizer/(?P<organizer>[^/]+)/landingpage/$', LandingpageSettingsView.as_view(), name="landingpage_settings"),
    url(r'^(?P<organizer>[^/]+)/$', organizer_index, name='organization.landingpage'),
    url(r'^control/startingpage_settings/$', StartingpageSettingsView.as_view(), name="startingpage_settings"),
    url(r'^control/startingpage_settings/delete_files/(?P<filename>[^/]+)/$', delete_startingpage_file, name="delete_startingpage_file"),
    url(r'^control/startingpage_settings/delete_all/$', delete_all_startingpage_files, name="delete_all_startingpage_files"),
    url(r'^$', starting_page_index, name='pretix.startingpage'),
    url(r'^control/organizer/(?P<organizer>[^/]+)/landingpage/delete_files/(?P<filename>[^/]+)/$', delete_organizer_file, name='delete_organizer_file'),
    url(r'^control/organizer/(?P<organizer>[^/]+)/landingpage/delete_all/$', delete_all_organizer_files, name='delete_all_organizer_files'),
]
