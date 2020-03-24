import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from pretix.base.models import Organizer
from pretix_landing_pages.models import LandingpageFile, StartingpageFile
from pretix_landing_pages.templatetags.load_path import load_path


class ContextMock(object):
    request = {}

    def __init__(self, request):
        self.request = request


class RequestMock(object):
    organizer = {}

    def __init__(self, organizer):
        self.organizer = organizer


@pytest.fixture
def env():
    orga = Organizer.objects.create(slug="dummy", name="Dummy")
    landing_file = SimpleUploadedFile(name="test.css", content=b".h1{color:green}", content_type="text/plain")
    LandingpageFile.objects.create(organizer=orga, filename="test.css", file=landing_file)
    starting_file = SimpleUploadedFile(name="test2.css", content=b".h1{color:green}", content_type="text/plain")
    StartingpageFile.objects.create(file=starting_file, filename="test2.css")
    return orga


@pytest.mark.django_db
def test_path_to_landingpage_correct(env):
    request = RequestMock(env)
    context = ContextMock(request)
    path = load_path(context, "test.css")
    assert re.match(r'^.*templates/landing_pages/1/test.css', path)

    path = load_path(context, "kein.css")
    assert path == ''


@pytest.mark.django_db
def test_path_to_startingpage_correct(env):
    context = ContextMock("dummy")
    path = load_path(context, "test2.css")
    assert re.match(r'^.*templates/starting_pages/test2.css', path)

    path = load_path(context, "kein.css")
    assert path == ''
