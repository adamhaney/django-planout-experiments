from wagtail.contrib.modeladmin.options import (
    ModelAdmin,
    ModelAdminGroup,
    modeladmin_register
)

from .models import Experiment


class ExperimentAdmin(ModelAdmin):
    model = Experiment


class ExperimentsAdminGroup(ModelAdminGroup):
    menu_order = 500
    menu_label = 'Experiments'
    menu_icon = 'cogs'
    items = (ExperimentAdmin,)


modeladmin_register(ExperimentsAdminGroup)
