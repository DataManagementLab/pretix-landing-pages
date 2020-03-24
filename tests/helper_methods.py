from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now


def __login_as_admin(env, client, admin_session):
    client.login(email='admin@localhost', password='admin')
    if admin_session:
        env[1].staffsession_set.create(date_start=now(), session_key=client.session.session_key)
        env[1].save()


def __get_upload_file(name, content):
    return SimpleUploadedFile(name, content=content, content_type="text/plain")
