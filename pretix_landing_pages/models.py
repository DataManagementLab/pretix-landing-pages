import os

from django.core.files.storage import FileSystemStorage
from django.db import models
from pretix.base.models import LoggedModel, Organizer
from pretix.settings import DATA_DIR, MEDIA_ROOT


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, **kwargs):
        if self.exists(name):
            os.remove(os.path.join(self.location, name))
        return name


index_storage = OverwriteStorage(DATA_DIR)
media_storage = OverwriteStorage(MEDIA_ROOT)


def get_upload_path(instance, filename):
    return os.path.join('templates', 'landing_pages', str(instance.organizer.id), filename)


def get_startingpage_path(instance, filename):
    return os.path.join('templates', 'starting_pages', filename)


class StartingpageSettings(LoggedModel):
    startingpage_active = models.BooleanField(default=False)
    index = models.FileField(upload_to=get_startingpage_path, null=True, default=None, storage=index_storage)
    redirect_active = models.BooleanField(default=False)
    redirect_link = models.URLField()


class LandingpageSettings(LoggedModel):
    organizer = models.OneToOneField(Organizer, on_delete=models.CASCADE, primary_key=True)
    active = models.BooleanField(default=False)
    index = models.FileField(upload_to=get_upload_path, null=True, default=None, storage=index_storage)


class LandingpageFile(LoggedModel):
    organizer = models.ForeignKey(Organizer, on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_upload_path, storage=media_storage)
    filename = models.CharField(max_length=255)

    class Meta:
        unique_together = (("organizer", "filename"),)

    def delete(self, *args, **kwargs):
        self.file.delete(*args, **kwargs)
        super().delete(*args, **kwargs)


class StartingpageFile(LoggedModel):
    file = models.FileField(upload_to=get_startingpage_path, storage=media_storage)
    filename = models.CharField(max_length=255)

    def delete(self, *args, **kwargs):
        self.file.delete(*args, **kwargs)
        super().delete(*args, **kwargs)
