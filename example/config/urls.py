"""URL configuration: the admin is the only thing served.

Everything interesting in this example happens in the ORM; see
``python manage.py demo``.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
