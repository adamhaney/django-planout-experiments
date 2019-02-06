from django.contrib import admin

from .models import Experiment


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    pass
