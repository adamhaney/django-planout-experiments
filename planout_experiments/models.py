import json

from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from planout.experiment import SimpleInterpretedExperiment
from planout.assignment import Assignment
from planout.interpreter import Interpreter

from structlog import get_logger

from django.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Sum
from django.utils.timezone import now
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings


logger = get_logger(__name__)

DJANGO_USER_DB_ID = 'django_user_db_id'


def default_now():
    return now()


def default_planout():
    return """{"op": "seq", "seq": []}"""


class AdminLinkMixin(models.Model):
    """
    Mixin that provides links to the model's admin and a link to report issues with model instances for admin users
    """
    class Meta:
        abstract = True

    def get_admin_url(self):
        return reverse("admin:%s_%s_change" % (self._meta.app_label, self._meta.model_name), args=(self.id,))

    def get_report_issue_url(self):
        content_type = ContentType.objects.get(app_label=self._meta.app_label, model=self._meta.model_name)

        path = reverse('support_tickets:generic_report_form')
        query = urlencode(
            {
                'prefill_reported_instance_content_type_id': content_type.id,
                'prefill_reported_instance_object_id': self.id,
                'prefill_queue_id': config.ADMIN_LINK_SUPPORT_QUEUE_ID
            }
        )

        return f"{path}?{query}"


class BaseModelNoHistory(TimeStampedModel):
    """
    Use this model for special cases where keeping history is
    undesirable
    """
    class Meta:
        abstract = True


class BaseModel(AdminLinkMixin, BaseModelNoHistory):
    """
    By default all models should have timestamp info and history
    """
    class Meta:
        abstract = True

    history = HistoricalRecords(inherit=True)


class FuzzyUserMixin(AdminLinkMixin, models.Model):
    """
    Used for cases when we want to identify the event but might not
    always have a user object to tie it to (allows for using IP
    address, Universal Device ID, anonymous ID etc)
    """
    class Meta:
        abstract = True

    event_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="%(app_label)s_%(class)s_related",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="user performing event all events should have either a user or event_user_identifier/event_user_identifier_type"  # NOQA
    )
    event_user_identifier = models.CharField(
        null=True,
        blank=True,
        max_length=140,
        help_text="When a user is not available user identifier/identifier_type to identifier enrollee"
    )
    event_user_identifier_type = models.CharField(
        null=True,
        blank=True,
        max_length=140,
        help_text="When a user is not available user identifier/identifier_type to identifier enrollee"
    )

    @property
    def fuzzy_user_str(self):
        if self.event_user:
            return str(self.event_user)
        else:
            return "{}: {}".format(self.user_identifier_type, self.user_identifier)


class DataEvent(BaseModelNoHistory):
    """
    A Mixin class that provides common fields that are needed when tracking user "Event Data"
    """
    class Meta:
        abstract = True

    uuid = models.UUIDField(editable=False, null=True, blank=True, unique=True)
    seen_at = models.DateTimeField(
        help_text="defaults to created unless overridden",
        null=True,
        blank=True,
        db_index=True,
        default=default_now,
        editable=False
    )
    data_source = models.CharField(
        max_length=140,
        null=True,
        blank=True,
        help_text="What system/code path this data came from"
    )
    data_meta = JSONField(default=dict, null=True, blank=True)


class FuzzyDataEvent(FuzzyUserMixin, DataEvent):
    class Meta:
        abstract = True


class FuzzyUserDataEvent(FuzzyUserMixin, DataEvent):
    class Meta:
        abstract = True


class AppDataMixin(models.Model):
    """
    A Mixin class that provides common fields for tracking user "Event Data" from a mobile device/app
    """
    class Meta:
        abstract = True

    app_version = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="The app version that sent this impression"
    )


class FuzzyUserAppDataEvent(FuzzyUserMixin, AppDataMixin, DataEvent):
    class Meta:
        abstract = True


class AppDataEvent(AdminLinkMixin, AppDataMixin, DataEvent):
    class Meta:
        abstract = True


class Experiment(BaseModel):
    name = models.CharField(max_length=140)
    salt = models.CharField(
        blank=True,
        max_length=140,
        help_text="Used to hash users into different buckets, change this if you want to 'shuffle' which users see certain variations"  # NOQA
    )
    goals = models.ManyToManyField(
        'planout_experiments.Goal',
        blank=True
    )
    planout_json = JSONField(
        null=True,
        blank=True,
        help_text="JSON experiment description using the planout design language, user the editor at http://planout-editor.herokuapp.com/",  # NOQA,
        default=default_planout
    )

    def __str__(self):
        return self.name

    def get_interpreter_instance(self, **kwargs):
        return Interpreter(
            self.get_planout_dict(),
            experiment_salt=self.salt,
            **kwargs
        )

    def get_planout_params(self):
        interpreter_instance = self.get_interpreter_instance()
        return interpreter_instance.get_params()

    @property
    def output_variables(self):
        return list([k for k in self.get_planout_params().keys()])

    def get_planout_dict(self):
        if type(self.planout_json) != dict:
            return json.loads(self.planout_json)

        return self.planout_json

    def get_planout_str(self):
        if type(self.planout_json) == dict:
            return json.dumps(self.planout_json)

        return self.planout_json

    def add_planout_variable(self, key, value):
        existing_dict = self.get_planout_dict()
        existing_dict['seq'].append({"op": "set", "var": key, "value": value})

        self.planout_json = existing_dict
        self.save()

    def set_planout_from_control(self, control):
        if type(control) != dict:
            control = {"single_value": control}

        for key, value in control.items():
            self.add_planout_variable(key, value)

    def get_experiment_trial(self, **inputs):
        trial = getattr(self, 'trial', None)

        if trial is None:
            self.trial = SingleTrial(db_experiment=self, **inputs)

        return self.trial

    def get_trial_for_user(self, user, inputs=None):
        return self.get_trial_for_user_id(user.id, inputs=inputs)

    def get_trial_for_user_id(self, user_id, inputs=None):
        if inputs is None:
            inputs = {}

        inputs['user_id'] = user_id
        inputs['user_identifier_type'] = DJANGO_USER_DB_ID

        return self.get_experiment_trial(**inputs)

    def save(self, *args, **kwargs):
        self.salt = self.name
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            'experiment-breakdown',
            kwargs={
                'pk': self.id
            }
        )

    def get_results_for_goal(self, goal):
        for variation in self.variations.all():
            result, created = ExperimentResult.objects.get_or_create(
                experiment=self,
                goal=goal,
                variation=variation
            )
            result.update_from_variation(variation)
            yield result

    def get_goal_results(self):
        for goal in self.goals.all():
            yield goal, self.get_results_for_goal(goal)

    @staticmethod
    def get_experiment(experiment_name, control_dict):
        experiment, created = Experiment.objects.get_or_create(
            name=experiment_name
        )

        if created:
            experiment.set_planout_from_control(control_dict)
            experiment.save()

        return experiment

    @staticmethod
    def get_experiment_value(
            experiment_name,
            key,
            user=None,
            user_identifier=None,
            user_identifier_type=None,
            control_value=None,
            inputs=None
    ):

        experiment = Experiment.get_experiment(experiment_name, {key: control_value})

        if user is None and (user_identifier is None or user_identifier_type is None):
            logger.warn(
                "get_experiment_value must provide user or user_identifier and user_idenfier type, returning control"
            )
            return control_value

        if inputs is None:
            inputs = {}

        if user is not None:
            trial = experiment.get_trial_for_user(user)
        else:
            trial = experiment.get_experiment_trial(
                inputs={
                    'user_id': user_identifier,
                    'user_identifier_type': user_identifier_type
                }
            )

        return trial.get(key)


class Variation(BaseModel):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='variations'
    )
    key = models.CharField(max_length=140)
    value = models.TextField()

    class Meta:
        unique_together = [
            ('experiment', 'key', 'value')
        ]

    def __str__(self):
        return "'{key}' = '{value}' on {experiment}".format(
            key=self.key,
            value=self.value,
            experiment=self.experiment
        )

    @property
    def num_exposures(self):
        num_exposures = self.exposures.count()

        if num_exposures is None:
            return 0
        else:
            return num_exposures

    def goal_achievements(self, goal):
        return GoalAchievement.objects.filter(
            goal=goal,
            event_user__experiments_exposure_related__variation=self
        )

    def success_value(self, goal):
        if self.goal_achievements(goal).count() == 0:
            return 0

        return self.goal_achievements(goal).aggregate(
            total_success=Sum('value')
        )['total_success']

    def success_rate(self, goal):
        if self.num_exposures == 0:
            return 0

        return self.success_value(goal) / self.num_exposures

    def success_percentage(self, goal):
        return self.success_rate(goal) * 100.0


class Exposure(FuzzyUserAppDataEvent):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='exposures'
    )
    variation = models.ForeignKey(
        Variation,
        on_delete=models.CASCADE,
        related_name='exposures'
    )

    def __str__(self):
        return "{} exposed to {}".format(
            self.fuzzy_user_str,
            self.variation
        )


class ExperimentLog(BaseModelNoHistory):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='experiment_logs'
    )
    data = JSONField()


class SingleTrial(SimpleInterpretedExperiment):
    def __init__(self, db_experiment, salt=None, **inputs):
        self.db_experiment = db_experiment

        self.inputs = inputs           # input data

        # True when assignments have been exposure logged
        self._exposure_logged = False
        self._salt = self.db_experiment.salt  # Experiment-level salt

        # Determines whether or not exposure should be logged
        self._in_experiment = True

        # use the name of the class as the default name
        self._name = self.db_experiment.name

        # auto-exposure logging is enabled by default
        self._auto_exposure_log = True

        self.setup()  # sets name, salt, etc.

        self._assignment = Assignment(self.salt)
        self._assigned = False

    def __str__(self):
        return f"Trial {self._salt} of {self._name}"

    def loadScript(self):
        self.script = self.db_experiment.get_planout_dict()

    def setup(self):
        self.name = self.db_experiment.name

    def configure_logger(self):
        pass

    def log_exposure(self, extras=None):
        """Logs exposure to treatment"""
        if not self._in_experiment:
            return

        for key, value in self._assignment.items():
            variation, created = Variation.objects.get_or_create(
                experiment=self.db_experiment,
                key=key,
                value=value
            )

            user_identifier_type = self.inputs.get('user_identifier_type')

            if user_identifier_type is not None:
                exposure = Exposure(
                    experiment=self.db_experiment,
                    variation=variation
                )

                if user_identifier_type == DJANGO_USER_DB_ID:
                    user = get_user_model().objects.get(id=self.inputs['user_id'])
                    exposure.event_user = user
                    exposure.event_user_identifier_type = DJANGO_USER_DB_ID
                else:
                    exposure.event_user_identifier = self.inputs['user_id']
                    exposure.event_user_identifier_type = user_identifier_type

                exposure.save()

        self._exposure_logged = True

    def log(self, data):
        ExperimentLog.objects.create(
            experiment=self.db_experiment,
            data=data
        )


class Goal(BaseModel):
    name = models.CharField(max_length=140)
    description = models.TextField()

    def __str__(self):
        return self.name

    @staticmethod
    def get_goal_by_name(name):
        goal, created = Goal.objects.get_or_create(
            name=name
        )

        return goal


class GoalAchievement(FuzzyUserAppDataEvent):
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='achivements'
    )
    value = models.FloatField(
        default=1.0,
        help_text="If the value isn't just binary it can be stored as a float here, positive values should be positive, 1.0 is assumed to be a 'true' positive goal achievement"  # NOQA
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_instance = GenericForeignKey('content_type', 'object_id')

    @staticmethod
    def log_achievement_for_user(self, goal_name, user, value=1.0, seen_at=None):
        goal = Goal.get_goal_by_name(goal_name)

        if seen_at is None:
            seen_at = now()

        GoalAchievement.objects.create(
            goal=goal,
            event_user=user,
            value=value
        )

    def __str__(self):
        return "{user} achieved {goal} {value}".format(
            user=self.fuzzy_user_str,
            goal=self.goal,
            value=self.value
        )


class ExperimentResult(BaseModel):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='results'
    )
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='results'
    )
    variation = models.ForeignKey(
        Variation,
        on_delete=models.CASCADE,
        related_name='results'
    )
    total_exposures = models.PositiveIntegerField(default=0)
    total_goal_achievements = models.PositiveIntegerField(default=0)
    success_value = models.FloatField(default=0)
    success_rate = models.FloatField(default=0)

    @property
    def success_percentage(self):
        self.success_rate * 100

    def update_from_variation(self):
        self.total_exposures = self.variation.num_variations
        self.total_goal_achievements = self.variation.goal_achievements(self.goal)
        self.success_value = self.variation.success_value(self.goal)
        self.success_rate = self.variation.success_rate(self.goal)
        self.save()
