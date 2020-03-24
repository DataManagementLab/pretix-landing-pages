import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from pretix.base.models import LogEntry, User
from pretix.settings import MEDIA_ROOT
from pretix_landing_pages.models import StartingpageFile, StartingpageSettings
from pretix_landing_pages.views import starting_page_base_dir

from ..helper_methods import __get_upload_file, __login_as_admin


@pytest.fixture
def env():
    admin = User.objects.create_superuser(email="admin@localhost", password="admin")
    User.objects.create_user(email="casual@user.com", password="wannaBeAdmin")
    setting = StartingpageSettings(redirect_active=False)
    return setting, admin, MEDIA_ROOT


# region Save, Delete, Replace
@pytest.mark.django_db
def test_uploaded_startingpage_is_saved(env, client):
    try:
        os.unlink(os.path.join(starting_page_base_dir, 'index.html'))
    except OSError:
        pass
    file_a = SimpleUploadedFile('index.html',
                                content=b"<html><body>Das ist ein Test.html</body></html>",
                                content_type="text/plain")
    __login_as_admin(env, client, True)
    client.post('/control/startingpage_settings/', data={'file_field': [file_a], 'redirect_link': '', 'apply': 'Apply'})
    assert LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagesettings.index_updated') \
        .filter(user_id=env[1].id) \
        .filter(data="""{"index.html": "updated"}""") \
        .first() is not None
    file = StartingpageSettings.objects.get().index
    assert file.readlines()[0] == b"<html><body>Das ist ein Test.html</body></html>"


@pytest.mark.django_db
def test_uploaded_startingpage_is_deleted(env, client):
    env[0].startingpage_active = True
    env[0].save()
    file_a = SimpleUploadedFile('index.html',
                                content=b"<html><body>Das ist ein Test.html</body></html>",
                                content_type="text/plain")
    __login_as_admin(env, client, True)
    file, _ = StartingpageSettings.objects.get_or_create()
    file.index = file_a
    file.save()
    client.post("/control/startingpage_settings/delete_files/index.html/")
    a = LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagesettings.index_deleted') \
        .filter(user_id=env[1].id)
    assert a.first() is not None
    assert StartingpageSettings.objects.filter(index='index.html').first() is None
    assert not StartingpageSettings.objects.get().index.name
    init = a.count()
    assert StartingpageSettings.objects.get().startingpage_active is False

    client.post('/control/startingpage_settings/delete_all/')
    assert LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagesettings.index_deleted') \
        .filter(user_id=env[1].id)\
        .count() == init
    assert StartingpageSettings.objects.filter(index='index.html').first() is None

    file, _ = StartingpageSettings.objects.get_or_create()
    file.index = file_a
    file.save()
    client.post('/control/startingpage_settings/delete_all/')
    assert LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagesettings.index_deleted') \
        .filter(user_id=env[1].id) \
        .count() == init + 1
    assert StartingpageSettings.objects.filter(index='index.html').first() is None


@pytest.mark.django_db
def test_no_error_delete_before_upload(env, client):
    __login_as_admin(env, client, True)
    client.post('/control/startingpage_settings/', data={'deleteAll': 'DeleteAll'})
    b = LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagesettings.index_deleted') \
        .filter(user_id=env[1].id)
    assert b.first() is None
    c = LogEntry.objects \
        .filter(action_type='pretix_landing_pages.startingpagefile.deleted') \
        .filter(user_id=env[1].id)
    assert c.first() is None


@pytest.mark.django_db
def test_startingpage_files_are_deleted(env, client):
    file_index = SimpleUploadedFile('index.html', content=b"<html><body>Das ist ein Test.html</body></html>")
    file_style = SimpleUploadedFile('style.css', content=b"h1{color:blue;}")
    file_jpg = SimpleUploadedFile('image.jpg', content=b"<html><body>Das ist ein Test.html</body></html>")
    __login_as_admin(env, client, True)

    for file in (file_index, file_style, file_jpg):
        if file == file_index:
            file, _ = StartingpageSettings.objects.get_or_create()
            file.index = file_index
            file.save()
        else:
            file_upload, _ = StartingpageFile.objects.get_or_create(filename=file.name)
            file_upload.file = file_style
            file_upload.filename = file.name
            file_upload.save()

    client.post("/control/startingpage_settings/delete_files/style.css/")
    a = StartingpageFile.objects.filter(filename='style.css')
    assert a.first() is None
    client.post("/control/startingpage_settings/delete_files/index.html/")
    b = StartingpageSettings.objects.filter(index='index.html')
    assert b.first() is None
    client.post('/control/startingpage_settings/delete_all/')
    c = StartingpageFile.objects.filter(filename='image.jpg')
    assert c.first() is None


@pytest.mark.django_db
def test_same_name_file_replaced_startingpage(env, client):
    file_a = SimpleUploadedFile('someUnusedStyle.css', content=b"TestTestTest")
    file_b = SimpleUploadedFile('someUnusedStyle.css', content=b"NeuerInhalt")

    file, _ = StartingpageFile.objects.get_or_create()
    file.file = file_a
    file.filename = 'someUnusedStyle.css'
    file.save()

    __login_as_admin(env, client, True)

    first_file = StartingpageFile.objects.get(filename="someUnusedStyle.css").file
    lines = first_file.readlines()
    assert lines[0] == b"TestTestTest"

    client.post('/control/startingpage_settings/', data={'file_field': [file_b], 'redirect_link': '', 'apply': 'Apply'})
    second_file = StartingpageFile.objects.get(filename="someUnusedStyle.css").file
    lines = second_file.readlines()
    assert lines[0] == b"NeuerInhalt"
# endregion


# region Media Files
@pytest.mark.django_db
def test_media_files_are_in_media_dir(env, client):
    expected_folder = os.path.join(env[2] + "/templates", 'starting_pages')
    file_a = __get_upload_file('someUnusedStyle.css', b"TestTestTest")
    file_b = __get_upload_file('style.css', b"zweiterTest")

    file, _ = StartingpageFile.objects.get_or_create(filename='someUnusedStyle.css')
    file.file = file_a
    file.filename = 'someUnusedStyle.css'
    file.save()
    file, _ = StartingpageFile.objects.get_or_create(filename='style.css')
    file.file = file_b
    file.filename = 'style.css'
    file.save()

    assert os.path.isdir(expected_folder)
    assert os.path.isfile(os.path.join(expected_folder, 'someUnusedStyle.css'))
    assert os.path.isfile(os.path.join(expected_folder, 'style.css'))


@pytest.mark.django_db
def test_index_not_in_media_dir(env, client):
    file_a = __get_upload_file('index.html', b"<html><body>Das ist ein Test.html</body></html>")
    __login_as_admin(env, client, True)

    client.post('/control/startingpage_settings/', data={'file_field': [file_a], 'redirect_link': '', 'apply': 'Apply'})
    assert not os.path.exists(os.path.join(env[2], '/templates/starting_pages', 'index.html'))
# endregion
