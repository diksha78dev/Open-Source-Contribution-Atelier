import logging

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.security.models import AutoFixPR, ProjectDependency

logger = logging.getLogger(__name__)


@shared_task
def scan_project_dependencies():
    """
    Fetches real Dependabot alerts from GitHub to track dependency decay and auto-PRs.
    """
    token = getattr(settings, "GITHUB_TOKEN", None)
    if not token:
        logger.warning("GITHUB_TOKEN not set. Cannot fetch Dependabot alerts.")
        return "GITHUB_TOKEN missing."

    # Using the repository owner/name string. Normally this would be dynamic,
    # but for this specific repo, we can hardcode or get it from env.
    repo = getattr(
        settings, "GITHUB_REPO_NAME", "diksha78dev/Open-Source-Contribution-Atelier"
    )

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Fetch Dependabot alerts
    alerts_url = f"https://api.github.com/repos/{repo}/dependabot/alerts"
    try:
        response = requests.get(alerts_url, headers=headers)
        if response.status_code == 200:
            alerts = response.json()
            processed_count = 0
            for alert in alerts:
                if alert.get("state") != "open":
                    continue

                dependency = alert.get("dependency", {})
                package_name = dependency.get("package", {}).get("name", "unknown")
                ecosystem = dependency.get("package", {}).get("ecosystem", "unknown")

                # Dependabot might not always give full current/latest version info in alerts,
                # but we extract what we can.
                current_version = "unknown"
                latest_version = "unknown"  # Usually fixed in version X

                security_vulnerability = alert.get("security_vulnerability", {})
                first_patched_version = security_vulnerability.get(
                    "first_patched_version", {}
                )
                if first_patched_version and first_patched_version.get("identifier"):
                    latest_version = first_patched_version.get("identifier")

                # Estimate days outdated based on created_at
                created_at_str = alert.get("created_at")
                days_outdated = 0
                if created_at_str:
                    from dateutil.parser import parse

                    created_at = parse(created_at_str)
                    days_outdated = (timezone.now() - created_at).days

                # Decay rate is a simplified mock metric based on severity
                severity = security_vulnerability.get("severity", "low")
                decay_rate = {
                    "critical": 1.0,
                    "high": 0.8,
                    "medium": 0.5,
                    "low": 0.2,
                }.get(severity, 0.1)
                security_score = max(0, 100 - int(decay_rate * 100))

                ProjectDependency.objects.update_or_create(
                    package_name=package_name,
                    ecosystem=ecosystem,
                    defaults={
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "days_outdated": days_outdated,
                        "decay_rate": decay_rate,
                        "security_score": security_score,
                    },
                )
                processed_count += 1

            logger.info(f"Processed {processed_count} Dependabot alerts.")
        else:
            logger.error(
                f"Failed to fetch Dependabot alerts: {response.status_code} {response.text}"
            )
    except Exception as e:
        logger.error(f"Error fetching Dependabot alerts: {e}")

    # 2. Fetch Dependabot created PRs for auto-PR syncing
    pulls_url = f"https://api.github.com/repos/{repo}/pulls?state=open"
    try:
        response = requests.get(pulls_url, headers=headers)
        if response.status_code == 200:
            prs = response.json()
            for pr in prs:
                if pr.get("user", {}).get("login") == "dependabot[bot]":
                    pr_number = pr.get("number")
                    pr_url = pr.get("html_url")
                    title = pr.get("title", "")

                    AutoFixPR.objects.update_or_create(
                        pr_number=pr_number,
                        defaults={
                            "pr_url": pr_url,
                            "status": "OPEN",
                            "packages_updated": [title],  # Rough estimate
                        },
                    )
            logger.info("Synced Dependabot PRs.")
    except Exception as e:
        logger.error(f"Error syncing Dependabot PRs: {e}")

    return "Scan complete."
