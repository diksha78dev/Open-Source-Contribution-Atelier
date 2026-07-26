from celery import shared_task
from django.utils import timezone
from .models import ProjectDependency


@shared_task
def scan_project_dependencies():
    # Mock data for demonstration and testing purposes
    # In a real implementation, this would call Snyk or Dependabot APIs.
    mock_dependencies = [
        {
            "package_name": "django",
            "ecosystem": "python",
            "current_version": "3.2.19",
            "latest_version": "4.2.11",
            "days_outdated": 340,
            "decay_rate": 0.85,
            "security_score": 40,
        },
        {
            "package_name": "react",
            "ecosystem": "npm",
            "current_version": "18.2.0",
            "latest_version": "18.2.0",
            "days_outdated": 0,
            "decay_rate": 0.0,
            "security_score": 100,
        },
        {
            "package_name": "requests",
            "ecosystem": "python",
            "current_version": "2.28.1",
            "latest_version": "2.31.0",
            "days_outdated": 120,
            "decay_rate": 0.45,
            "security_score": 75,
        },
    ]

    for dep_data in mock_dependencies:
        ProjectDependency.objects.update_or_create(
            package_name=dep_data["package_name"],
            ecosystem=dep_data["ecosystem"],
            defaults={
                "current_version": dep_data["current_version"],
                "latest_version": dep_data["latest_version"],
                "days_outdated": dep_data["days_outdated"],
                "decay_rate": dep_data["decay_rate"],
                "security_score": dep_data["security_score"],
            },
        )

    return f"Processed {len(mock_dependencies)} dependencies."
