from django.views.generic.detail import DetailView
from django.contrib.auth.mixins import PermissionRequiredMixin

from .models import Experiment


class ExperimentBreakdownView(PermissionRequiredMixin, DetailView):
    permission_required = ('experiments.can_open', 'experiments.can_edit')
    model = Experiment
    template = "experiments/experiment_breakdown.html"
