import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from pretix.base.models import Organizer, Team, User
from pretix.settings import MEDIA_ROOT
from pretix_landing_pages.models import LandingpageFile, LandingpageSettings

from ..helper_methods import __get_upload_file, __login_as_admin


@pytest.fixture
def env():
    admin = User.objects.create_superuser(email="admin@localhost", password="admin")
    organizer = Organizer.objects.create(name="Next Level Fachbereich", slug="FB20")
    setting = LandingpageSettings.objects.create(organizer=organizer, active=False)
    t = Team.objects.create(organizer=organizer, can_change_organizer_settings=True)
    t.members.add(admin)
    return organizer, admin, MEDIA_ROOT, setting


# region Override, Save, Delete
@pytest.mark.django_db
def test_same_name_file_replaced(env, client):
    file_a = SimpleUploadedFile('someUnusedStyle.css', content=b"TestTestTest")
    file_b = SimpleUploadedFile('someUnusedStyle.css', content=b"NeuerInhaltA")
    file_c = SimpleUploadedFile('someUnusedStyle.css', content=b"NeuerInhaltB")

    __login_as_admin(env, client, False)
    client.post('/control/organizer/FB20/landingpage/', data={'file_field': [file_a]})
    first_file = LandingpageFile.objects.get(organizer=env[0], filename="someUnusedStyle.css").file
    assert first_file.readlines()[0] == b"TestTestTest"

    client.post('/control/organizer/FB20/landingpage/', data={'file_field': [file_b]})
    second_file = LandingpageFile.objects.get(organizer=env[0], filename="someUnusedStyle.css").file
    assert second_file.readlines()[0] == b"TestTestTest"

    client.post('/control/organizer/FB20/landingpage/', data={'file_field': [file_c], 'override_files': 'on'})
    third_file = LandingpageFile.objects.get(organizer=env[0], filename="someUnusedStyle.css").file
    assert third_file.readlines()[0] == b"NeuerInhaltB"


@pytest.mark.django_db
def test_uploaded_landingpage_files_are_saved(env, client):
    file_a = SimpleUploadedFile('index.html',
                                content=b"<html><body>Das ist ein Test.html</body></html>",
                                content_type="text/plain")
    file_b = SimpleUploadedFile('someUnusedStyle.css',
                                content=b"TestTestTest",
                                content_type="text/plain")
    __login_as_admin(env, client, False)

    client.post('/control/organizer/FB20/landingpage/', data={'file_field': [file_a, file_b]})

    index = LandingpageSettings.objects.get(pk=env[0]).index
    assert index.readlines()[0] == b"<html><body>Das ist ein Test.html</body></html>"
    assert index.name == 'templates/landing_pages/1/index.html'

    file1 = LandingpageFile.objects.get(organizer=env[0], filename=file_b.name).file
    assert file1.readlines()[0] == b"TestTestTest"
    assert file1.name == 'templates/landing_pages/1/someUnusedStyle.css'


@pytest.mark.django_db
def test_landingpage_files_are_deleted(env, client):
    file_a = __get_upload_file('index.html', b"Das ist ein Test_HTML")
    file_b = __get_upload_file('test1.png', b"Das ist ein Test_PNG")
    file_c = __get_upload_file('style1.css', b"Das ist ein Test_CSS")

    setting, __ = LandingpageSettings.objects.get_or_create(organizer=env[0])
    setting.index = file_a
    setting.save()
    LandingpageFile.objects.create(organizer=env[0], file=file_b, filename='test1.png')
    LandingpageFile.objects.create(organizer=env[0], file=file_c, filename='style1.css')

    __login_as_admin(env, client, False)
    client.post("/control/organizer/" + env[0].slug + "/landingpage/delete_files/style1.css/")
    assert LandingpageFile.objects.filter(organizer=env[0], filename="style1.css").count() == 0

    client.post("/control/organizer/" + env[0].slug + "/landingpage/delete_files/index.html/")
    setting = LandingpageSettings.objects.get(organizer=env[0])
    assert not setting.index.name
    file_a = __get_upload_file('index.html', b"Das ist ein Test_HTML")
    setting.index = file_a
    setting.save()

    assert LandingpageFile.objects.filter(organizer=env[0]).count() > 0
    client.post("/control/organizer/" + env[0].slug + "/landingpage/delete_all/")
    assert LandingpageFile.objects.filter(organizer=env[0]).count() == 0
    client.post("/control/organizer/" + env[0].slug + "/landingpage/delete_all/")
    assert LandingpageFile.objects.filter(organizer=env[0]).count() == 0
# endregion


# region Media Files
@pytest.mark.django_db
def test_media_files_are_in_media_dir(env, client):
    expected_folder = os.path.join(env[2] + "/templates/landing_pages", str(env[0].id))
    file_a = SimpleUploadedFile('someUnusedStyle.css', content=b"TestTestTest")
    file_b = SimpleUploadedFile('style.css', content=b"zweiterTest")

    file1, _ = LandingpageFile.objects.get_or_create(organizer=env[0], filename='someUnusedStyle.css')
    file1.file = file_a
    file1.filename = 'someUnusedStyle.css'
    file1.save()
    file2, _ = LandingpageFile.objects.get_or_create(organizer=env[0], filename='style.css')
    file2.file = file_b
    file2.filename = 'style.css'
    file2.save()

    a = os.path.isdir(expected_folder)
    assert a
    b = os.path.isfile(os.path.join(expected_folder, 'someUnusedStyle.css'))
    assert b
    c = os.path.isfile(os.path.join(expected_folder, 'style.css'))
    assert c


@pytest.mark.django_db
def test_index_not_in_media_dir(env, client):
    file_a = __get_upload_file('index.html', b"<html><body>Das ist ein Test.html</body></html>")
    __login_as_admin(env, client, True)

    client.post('/control/organizer/FB20/landingpage/', data={'file_field': [file_a]})
    assert not os.path.exists(os.path.join(env[2] + "/templates/landing_pages", env[0].slug, 'index.html'))
# endregion
