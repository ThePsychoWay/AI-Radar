"""
Tests for GitHub Actions Workflow Configuration.

Covers:
- Workflow definitions and triggers
- Cron schedule management
- Environment configuration
- Job definitions
- Metrics tracking
- Workflow status tracking
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.workflows.workflow_config import (
    WorkflowType,
    TriggerType,
    CronSchedule,
    WorkflowEnvironment,
    WorkflowJob,
    Workflow,
    WorkflowStatus,
    WorkflowMetrics,
    WorkflowConfigurationManager,
)


class TestCronSchedule:
    """Tests for CronSchedule."""

    def test_creation(self):
        """CronSchedule should initialize correctly."""
        schedule = CronSchedule(minute="0", hour="8")

        assert schedule.minute == "0"
        assert schedule.hour == "8"

    def test_cron_expression(self):
        """Should generate valid cron expression."""
        schedule = CronSchedule(minute="0", hour="8", day_of_month="*", month="*", day_of_week="*")

        assert schedule.cron_expression == "0 8 * * *"

    def test_daily_at(self):
        """Should create daily schedule."""
        schedule = CronSchedule.daily_at(hour=8, minute=30)

        assert schedule.cron_expression == "30 8 * * *"

    def test_every_hours(self):
        """Should create hourly schedule."""
        schedule = CronSchedule.every_hours(6)

        assert schedule.cron_expression == "0 */6 * * *"

    def test_every_days(self):
        """Should create daily interval schedule."""
        schedule = CronSchedule.every_days(3)

        assert schedule.cron_expression == "0 0 */3 * *"

    def test_weekdays_at(self):
        """Should create weekday schedule."""
        schedule = CronSchedule.weekdays_at(hour=9, minute=0)

        assert schedule.cron_expression == "0 9 * * 1-5"


class TestWorkflowEnvironment:
    """Tests for WorkflowEnvironment."""

    def test_default_environment(self):
        """Environment should have sensible defaults."""
        env = WorkflowEnvironment()

        assert env.python_version == "3.12"
        assert env.os == "ubuntu-latest"
        assert env.cache_enabled
        assert env.artifact_retention_days == 30

    def test_custom_environment(self):
        """Should support custom environment."""
        env = WorkflowEnvironment(
            python_version="3.11",
            os="macos-latest",
            cache_enabled=False,
        )

        assert env.python_version == "3.11"
        assert env.os == "macos-latest"
        assert not env.cache_enabled

    def test_environment_vars(self):
        """Should support environment variables."""
        env = WorkflowEnvironment(
            env_vars={"DEBUG": "true", "LOG_LEVEL": "INFO"},
        )

        assert env.env_vars["DEBUG"] == "true"

    def test_to_dict(self):
        """Should convert to dictionary."""
        env = WorkflowEnvironment()
        d = env.to_dict()

        assert d["python_version"] == "3.12"
        assert d["os"] == "ubuntu-latest"


class TestWorkflowJob:
    """Tests for WorkflowJob."""

    def test_creation(self):
        """WorkflowJob should initialize correctly."""
        job = WorkflowJob(name="test")

        assert job.name == "test"
        assert len(job.steps) == 0

    def test_add_step_run(self):
        """Should add run step."""
        job = WorkflowJob(name="test")
        job.add_step(name="Run tests", run="pytest tests/")

        assert len(job.steps) == 1
        assert job.steps[0]["name"] == "Run tests"
        assert job.steps[0]["run"] == "pytest tests/"

    def test_add_step_uses(self):
        """Should add uses step."""
        job = WorkflowJob(name="test")
        job.add_step(name="Checkout", uses="actions/checkout@v4")

        assert job.steps[0]["uses"] == "actions/checkout@v4"

    def test_add_step_with_params(self):
        """Should add step with parameters."""
        job = WorkflowJob(name="test")
        job.add_step(
            name="Setup Python",
            uses="actions/setup-python@v4",
            with_params={"python-version": "3.12"},
        )

        assert job.steps[0]["with"]["python-version"] == "3.12"

    def test_multiple_steps(self):
        """Should support multiple steps."""
        job = WorkflowJob(name="build")
        job.add_step(name="Checkout", uses="actions/checkout@v4")
        job.add_step(name="Install", run="pip install -r requirements.txt")
        job.add_step(name="Test", run="pytest")

        assert len(job.steps) == 3

    def test_fluent_interface(self):
        """Should support method chaining."""
        job = (
            WorkflowJob(name="test")
            .add_step(name="Checkout", uses="actions/checkout@v4")
            .add_step(name="Test", run="pytest")
        )

        assert len(job.steps) == 2


class TestWorkflow:
    """Tests for Workflow."""

    def test_creation(self):
        """Workflow should initialize correctly."""
        workflow = Workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        assert workflow.name == "CI"
        assert workflow.workflow_type == WorkflowType.CI_PIPELINE

    def test_add_job(self):
        """Should add jobs."""
        workflow = Workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        job = WorkflowJob(name="test")
        workflow.add_job(job)

        assert len(workflow.jobs) == 1

    def test_scheduled_workflow(self):
        """Should support scheduled triggers."""
        workflow = Workflow(
            name="Daily Digest",
            workflow_type=WorkflowType.DAILY_DIGEST,
            trigger_type=TriggerType.SCHEDULE,
            schedule=CronSchedule.daily_at(8, 0),
        )

        assert workflow.schedule is not None
        assert workflow.schedule.cron_expression == "0 8 * * *"

    def test_to_dict(self):
        """Should convert to dictionary."""
        workflow = Workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        d = workflow.to_dict()

        assert d["name"] == "CI"
        assert "on" in d

    def test_build_trigger_push(self):
        """Should build push trigger."""
        workflow = Workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        config = workflow._build_trigger_config()

        assert "push" in config

    def test_build_trigger_schedule(self):
        """Should build schedule trigger."""
        workflow = Workflow(
            name="Collection",
            workflow_type=WorkflowType.SCHEDULED_COLLECTION,
            trigger_type=TriggerType.SCHEDULE,
            schedule=CronSchedule.every_hours(6),
        )

        config = workflow._build_trigger_config()

        assert "schedule" in config

    def test_manual_trigger(self):
        """Should include manual trigger when enabled."""
        workflow = Workflow(
            name="Test",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
            allow_manual_trigger=True,
        )

        config = workflow._build_trigger_config()

        assert "workflow_dispatch" in config


class TestWorkflowStatus:
    """Tests for WorkflowStatus."""

    def test_creation(self):
        """WorkflowStatus should initialize correctly."""
        status = WorkflowStatus(
            workflow_id="123",
            run_id="456",
            status="completed",
            conclusion="success",
        )

        assert status.workflow_id == "123"
        assert status.is_success

    def test_is_success(self):
        """Should detect successful status."""
        status = WorkflowStatus(
            workflow_id="1",
            run_id="1",
            status="completed",
            conclusion="success",
        )

        assert status.is_success
        assert not status.is_failed
        assert not status.is_running

    def test_is_failed(self):
        """Should detect failed status."""
        status = WorkflowStatus(
            workflow_id="1",
            run_id="1",
            status="completed",
            conclusion="failure",
        )

        assert status.is_failed
        assert not status.is_success

    def test_is_running(self):
        """Should detect running status."""
        status = WorkflowStatus(
            workflow_id="1",
            run_id="1",
            status="in_progress",
        )

        assert status.is_running
        assert not status.is_success


class TestWorkflowMetrics:
    """Tests for WorkflowMetrics."""

    def test_creation(self):
        """WorkflowMetrics should initialize correctly."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)

        assert metrics.workflow_type == WorkflowType.CI_PIPELINE
        assert metrics.total_runs == 0
        assert metrics.success_rate == 0.0

    def test_record_run_success(self):
        """Should record successful run."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)
        metrics.record_run(duration=120, success=True)

        assert metrics.total_runs == 1
        assert metrics.successful_runs == 1
        assert metrics.failed_runs == 0
        assert metrics.success_rate == 1.0

    def test_record_run_failure(self):
        """Should record failed run."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)
        metrics.record_run(duration=60, success=False)

        assert metrics.total_runs == 1
        assert metrics.successful_runs == 0
        assert metrics.failed_runs == 1
        assert metrics.success_rate == 0.0

    def test_multiple_runs(self):
        """Should track multiple runs."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)

        metrics.record_run(duration=100, success=True)
        metrics.record_run(duration=120, success=True)
        metrics.record_run(duration=90, success=False)

        assert metrics.total_runs == 3
        assert metrics.successful_runs == 2
        assert metrics.failed_runs == 1
        assert metrics.success_rate == pytest.approx(0.667, rel=0.01)

    def test_average_duration(self):
        """Should calculate average duration."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)

        metrics.record_run(duration=100, success=True)
        metrics.record_run(duration=200, success=True)

        assert metrics.average_duration_seconds == pytest.approx(150.0)

    def test_last_run_timestamp(self):
        """Should track last run time."""
        metrics = WorkflowMetrics(workflow_type=WorkflowType.CI_PIPELINE)

        before = datetime.now(timezone.utc)
        metrics.record_run(duration=100, success=True)
        after = datetime.now(timezone.utc)

        assert before <= metrics.last_run_at <= after


class TestWorkflowConfigurationManager:
    """Tests for WorkflowConfigurationManager."""

    def test_creation(self):
        """Manager should initialize correctly."""
        manager = WorkflowConfigurationManager()

        assert len(manager.workflows) == 0
        assert len(manager.metrics) == 0

    def test_create_workflow(self):
        """Should create workflow."""
        manager = WorkflowConfigurationManager()

        workflow = manager.create_workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        assert workflow is not None
        assert manager.get_workflow("CI") is not None

    def test_get_workflow(self):
        """Should retrieve workflow."""
        manager = WorkflowConfigurationManager()
        manager.create_workflow(
            name="Test",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )

        workflow = manager.get_workflow("Test")

        assert workflow.name == "Test"

    def test_get_workflows_by_type(self):
        """Should filter workflows by type."""
        manager = WorkflowConfigurationManager()

        manager.create_workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )
        manager.create_workflow(
            name="Digest",
            workflow_type=WorkflowType.DAILY_DIGEST,
            trigger_type=TriggerType.SCHEDULE,
        )

        ci_workflows = manager.get_workflows_by_type(WorkflowType.CI_PIPELINE)
        digest_workflows = manager.get_workflows_by_type(WorkflowType.DAILY_DIGEST)

        assert len(ci_workflows) == 1
        assert len(digest_workflows) == 1

    def test_get_scheduled_workflows(self):
        """Should filter scheduled workflows."""
        manager = WorkflowConfigurationManager()

        manager.create_workflow(
            name="CI",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
        )
        collection = manager.create_workflow(
            name="Collection",
            workflow_type=WorkflowType.SCHEDULED_COLLECTION,
            trigger_type=TriggerType.SCHEDULE,
        )
        collection.schedule = CronSchedule.every_hours(6)

        scheduled = manager.get_scheduled_workflows()

        assert len(scheduled) == 1
        assert scheduled[0].name == "Collection"

    def test_register_metrics(self):
        """Should register metrics."""
        manager = WorkflowConfigurationManager()

        metrics = manager.register_metrics(WorkflowType.CI_PIPELINE)

        assert metrics.workflow_type == WorkflowType.CI_PIPELINE
        assert manager.get_metrics(WorkflowType.CI_PIPELINE) is not None

    def test_record_run(self):
        """Should record workflow run."""
        manager = WorkflowConfigurationManager()

        manager.record_run(WorkflowType.CI_PIPELINE, duration_seconds=120, success=True)

        metrics = manager.get_metrics(WorkflowType.CI_PIPELINE)
        assert metrics.successful_runs == 1

    def test_export_metrics_summary(self):
        """Should export metrics summary."""
        manager = WorkflowConfigurationManager()

        manager.record_run(WorkflowType.CI_PIPELINE, duration_seconds=100, success=True)
        manager.record_run(WorkflowType.CI_PIPELINE, duration_seconds=120, success=True)
        manager.record_run(WorkflowType.CI_PIPELINE, duration_seconds=90, success=False)

        summary = manager.export_metrics_summary()

        assert "ci" in summary
        assert summary["ci"]["total_runs"] == 3
        assert summary["ci"]["successful_runs"] == 2

    def test_get_all_workflows(self):
        """Should get all workflows."""
        manager = WorkflowConfigurationManager()

        for i in range(3):
            manager.create_workflow(
                name=f"Workflow{i}",
                workflow_type=WorkflowType.CI_PIPELINE,
                trigger_type=TriggerType.PUSH,
            )

        all_workflows = manager.get_all_workflows()

        assert len(all_workflows) == 3


class TestIntegration:
    """Integration tests."""

    def test_full_workflow_creation(self):
        """Full workflow creation and configuration."""
        manager = WorkflowConfigurationManager()

        # Create CI workflow
        ci = manager.create_workflow(
            name="CI Pipeline",
            workflow_type=WorkflowType.CI_PIPELINE,
            trigger_type=TriggerType.PUSH,
            description="Automated testing",
        )

        job = WorkflowJob(name="test")
        job.add_step(name="Checkout", uses="actions/checkout@v4")
        job.add_step(name="Install", run="pip install -r requirements.txt")
        job.add_step(name="Test", run="pytest tests/")

        ci.add_job(job)

        # Create scheduled collection
        collection = manager.create_workflow(
            name="Scheduled Collection",
            workflow_type=WorkflowType.SCHEDULED_COLLECTION,
            trigger_type=TriggerType.SCHEDULE,
        )
        collection.schedule = CronSchedule.every_hours(6)

        # Verify
        assert len(manager.get_all_workflows()) == 2
        assert len(manager.get_workflows_by_type(WorkflowType.CI_PIPELINE)) == 1
        assert len(manager.get_scheduled_workflows()) == 1

    def test_metrics_tracking(self):
        """Metrics tracking across multiple runs."""
        manager = WorkflowConfigurationManager()

        # Simulate multiple runs (succeeds unless i is divisible by 3)
        # i=0,3,6,9 fail (4 failures), i=1,2,4,5,7,8 succeed (6 successes)
        for i in range(10):
            success = i % 3 != 0
            manager.record_run(
                WorkflowType.CI_PIPELINE,
                duration_seconds=100 + i * 10,
                success=success,
            )

        metrics = manager.get_metrics(WorkflowType.CI_PIPELINE)

        assert metrics.total_runs == 10
        assert metrics.successful_runs == 6
        assert metrics.success_rate == pytest.approx(0.6)
