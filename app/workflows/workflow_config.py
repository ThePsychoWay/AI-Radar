"""
GitHub Actions Workflow Configuration Management.

Handles:
- Workflow definitions and triggers
- Schedule management (cron expressions)
- Environment variable configuration
- Secret management patterns
- Workflow status tracking
- Log aggregation
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Type of GitHub Actions workflow."""
    CI_PIPELINE = "ci"
    SCHEDULED_COLLECTION = "collection"
    DAILY_DIGEST = "digest"
    DEPLOYMENT = "deploy"
    MAINTENANCE = "maintenance"


class TriggerType(Enum):
    """Workflow trigger type."""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    SCHEDULE = "schedule"
    WORKFLOW_DISPATCH = "workflow_dispatch"
    REPOSITORY_DISPATCH = "repository_dispatch"


@dataclass
class CronSchedule:
    """Cron schedule definition."""

    minute: str = "*"
    hour: str = "*"
    day_of_month: str = "*"
    month: str = "*"
    day_of_week: str = "*"

    @property
    def cron_expression(self) -> str:
        """Generate cron expression."""
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week}"

    @classmethod
    def daily_at(cls, hour: int, minute: int = 0) -> "CronSchedule":
        """Create daily schedule at specific time (UTC)."""
        return cls(minute=str(minute), hour=str(hour))

    @classmethod
    def every_hours(cls, hours: int) -> "CronSchedule":
        """Create schedule that runs every N hours."""
        return cls(minute="0", hour=f"*/{hours}")

    @classmethod
    def every_days(cls, days: int) -> "CronSchedule":
        """Create schedule that runs every N days."""
        return cls(minute="0", hour="0", day_of_month=f"*/{days}")

    @classmethod
    def weekdays_at(cls, hour: int, minute: int = 0) -> "CronSchedule":
        """Create schedule for weekdays only (Monday-Friday)."""
        return cls(minute=str(minute), hour=str(hour), day_of_week="1-5")


@dataclass
class WorkflowEnvironment:
    """Workflow environment configuration."""

    python_version: str = "3.12"
    os: str = "ubuntu-latest"
    env_vars: Dict[str, str] = field(default_factory=dict)
    secrets: Dict[str, str] = field(default_factory=dict)
    cache_enabled: bool = True
    artifact_retention_days: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "python_version": self.python_version,
            "os": self.os,
            "env_vars": self.env_vars,
            "secrets": self.secrets,
            "cache_enabled": self.cache_enabled,
            "artifact_retention_days": self.artifact_retention_days,
        }


@dataclass
class WorkflowJob:
    """GitHub Actions job configuration."""

    name: str
    run_on: str = "ubuntu-latest"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    environment: Optional[WorkflowEnvironment] = None
    timeout_minutes: int = 60
    continue_on_error: bool = False

    def add_step(
        self,
        name: str,
        run: Optional[str] = None,
        uses: Optional[str] = None,
        with_params: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowJob":
        """Add step to job."""
        step = {"name": name}

        if run:
            step["run"] = run
        elif uses:
            step["uses"] = uses

        if with_params:
            step["with"] = with_params

        self.steps.append(step)
        return self


@dataclass
class Workflow:
    """GitHub Actions workflow definition."""

    name: str
    workflow_type: WorkflowType
    trigger_type: TriggerType
    jobs: List[WorkflowJob] = field(default_factory=list)
    schedule: Optional[CronSchedule] = None
    environment: Optional[WorkflowEnvironment] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    concurrency: int = 1
    allow_manual_trigger: bool = True
    description: str = ""

    def add_job(self, job: WorkflowJob) -> "Workflow":
        """Add job to workflow."""
        self.jobs.append(job)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary for YAML serialization."""
        result = {
            "name": self.name,
            "description": self.description,
            "on": self._build_trigger_config(),
        }

        if self.jobs:
            result["jobs"] = {
                job.name: self._serialize_job(job) for job in self.jobs
            }

        return result

    def _build_trigger_config(self) -> Dict[str, Any]:
        """Build 'on' trigger configuration."""
        config = {}

        if self.trigger_type == TriggerType.SCHEDULE and self.schedule:
            config["schedule"] = [{"cron": self.schedule.cron_expression}]

        elif self.trigger_type == TriggerType.PUSH:
            config["push"] = {"branches": ["master", "main", "develop"]}

        elif self.trigger_type == TriggerType.PULL_REQUEST:
            config["pull_request"] = {"branches": ["master", "main", "develop"]}

        if self.allow_manual_trigger:
            config["workflow_dispatch"] = {}

        return config

    def _serialize_job(self, job: WorkflowJob) -> Dict[str, Any]:
        """Serialize job to dictionary."""
        result = {
            "runs-on": job.run_on,
            "steps": job.steps,
        }

        if job.timeout_minutes != 60:
            result["timeout-minutes"] = job.timeout_minutes

        if job.continue_on_error:
            result["continue-on-error"] = True

        return result


@dataclass
class WorkflowStatus:
    """Status of a workflow run."""

    workflow_id: str
    run_id: str
    status: str  # queued, in_progress, completed
    conclusion: Optional[str] = None  # success, failure, cancelled, skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: int = 0
    jobs_status: Dict[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if workflow succeeded."""
        return self.conclusion == "success"

    @property
    def is_failed(self) -> bool:
        """Check if workflow failed."""
        return self.conclusion == "failure"

    @property
    def is_running(self) -> bool:
        """Check if workflow is running."""
        return self.status == "in_progress"


@dataclass
class WorkflowMetrics:
    """Metrics for workflow performance."""

    workflow_type: WorkflowType
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    average_duration_seconds: float = 0
    last_run_at: Optional[datetime] = None
    success_rate: float = 0.0

    def update_success_rate(self) -> None:
        """Calculate success rate."""
        if self.total_runs > 0:
            self.success_rate = self.successful_runs / self.total_runs
        else:
            self.success_rate = 0.0

    def record_run(self, duration: int, success: bool) -> None:
        """Record workflow run."""
        self.total_runs += 1
        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1

        # Update average duration
        self.average_duration_seconds = (
            (self.average_duration_seconds * (self.total_runs - 1) + duration)
            / self.total_runs
        )

        self.last_run_at = datetime.now(timezone.utc)
        self.update_success_rate()


class WorkflowConfigurationManager:
    """Manage GitHub Actions workflows."""

    def __init__(self, repo_path: str = "."):
        """
        Initialize workflow configuration manager.

        Args:
            repo_path: Path to repository root.
        """
        self.repo_path = repo_path
        self.workflows: Dict[str, Workflow] = {}
        self.metrics: Dict[WorkflowType, WorkflowMetrics] = {}

    def create_workflow(
        self,
        name: str,
        workflow_type: WorkflowType,
        trigger_type: TriggerType,
        description: str = "",
    ) -> Workflow:
        """Create new workflow."""
        workflow = Workflow(
            name=name,
            workflow_type=workflow_type,
            trigger_type=trigger_type,
            description=description,
        )

        self.workflows[name] = workflow
        return workflow

    def get_workflow(self, name: str) -> Optional[Workflow]:
        """Get workflow by name."""
        return self.workflows.get(name)

    def register_metrics(self, workflow_type: WorkflowType) -> WorkflowMetrics:
        """Register metrics for workflow type."""
        if workflow_type not in self.metrics:
            self.metrics[workflow_type] = WorkflowMetrics(workflow_type=workflow_type)

        return self.metrics[workflow_type]

    def get_metrics(self, workflow_type: WorkflowType) -> Optional[WorkflowMetrics]:
        """Get metrics for workflow type."""
        return self.metrics.get(workflow_type)

    def record_run(
        self,
        workflow_type: WorkflowType,
        duration_seconds: int,
        success: bool,
    ) -> None:
        """Record workflow run for metrics."""
        metrics = self.register_metrics(workflow_type)
        metrics.record_run(duration_seconds, success)

    def get_all_workflows(self) -> Dict[str, Workflow]:
        """Get all workflows."""
        return self.workflows

    def get_workflows_by_type(self, workflow_type: WorkflowType) -> List[Workflow]:
        """Get workflows by type."""
        return [w for w in self.workflows.values() if w.workflow_type == workflow_type]

    def get_scheduled_workflows(self) -> List[Workflow]:
        """Get all scheduled workflows."""
        return [
            w
            for w in self.workflows.values()
            if w.trigger_type == TriggerType.SCHEDULE
        ]

    def export_metrics_summary(self) -> Dict[str, Any]:
        """Export metrics summary."""
        summary = {}

        for workflow_type, metrics in self.metrics.items():
            summary[workflow_type.value] = {
                "total_runs": metrics.total_runs,
                "successful_runs": metrics.successful_runs,
                "failed_runs": metrics.failed_runs,
                "success_rate": f"{metrics.success_rate:.2%}",
                "average_duration_seconds": f"{metrics.average_duration_seconds:.1f}",
                "last_run": metrics.last_run_at.isoformat()
                if metrics.last_run_at
                else None,
            }

        return summary

    def print_summary(self) -> None:
        """Print workflow configuration summary."""
        print(f"\n📊 Workflow Configuration Summary")
        print(f"{'=' * 60}")
        print(f"Total workflows: {len(self.workflows)}")
        print(f"By type:")

        for workflow_type in WorkflowType:
            workflows = self.get_workflows_by_type(workflow_type)
            if workflows:
                print(f"  {workflow_type.value}: {len(workflows)}")

        print(f"\nScheduled workflows:")
        for workflow in self.get_scheduled_workflows():
            print(f"  - {workflow.name}")
            if workflow.schedule:
                print(f"    Cron: {workflow.schedule.cron_expression}")

        print(f"\nMetrics:")
        metrics_summary = self.export_metrics_summary()
        for wf_type, stats in metrics_summary.items():
            print(f"  {wf_type}:")
            print(f"    Success rate: {stats['success_rate']}")
            print(f"    Avg duration: {stats['average_duration_seconds']}s")


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    # Create manager
    manager = WorkflowConfigurationManager()

    # Create CI workflow
    ci = manager.create_workflow(
        name="CI Pipeline",
        workflow_type=WorkflowType.CI_PIPELINE,
        trigger_type=TriggerType.PUSH,
        description="Automated testing and code quality checks",
    )

    ci_job = WorkflowJob(name="test")
    ci_job.add_step(name="Checkout", uses="actions/checkout@v4")
    ci_job.add_step(name="Setup Python", uses="actions/setup-python@v4")
    ci_job.add_step(name="Install dependencies", run="pip install -r requirements.txt")
    ci_job.add_step(name="Run tests", run="pytest tests/")

    ci.add_job(ci_job)

    # Create scheduled collection
    collection = manager.create_workflow(
        name="Scheduled Collection",
        workflow_type=WorkflowType.SCHEDULED_COLLECTION,
        trigger_type=TriggerType.SCHEDULE,
        description="Collect data every 6 hours",
    )
    collection.schedule = CronSchedule.every_hours(6)

    # Print summary
    manager.print_summary()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
