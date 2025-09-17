"""
Security Alert Model - Enterprise security alert management and incident tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from .audit_log import AuditLog
from typing import Dict, Any, List


class SecurityAlert(models.Model):
    """
    Model for tracking security alerts generated from audit logs.
    
    Provides comprehensive security incident management including:
    - Automated alert generation from audit patterns
    - Alert prioritization and risk scoring
    - Investigation workflow management
    - Resolution tracking and reporting
    """
    
    class AlertType(models.TextChoices):
        BRUTE_FORCE = 'BRUTE_FORCE', 'Brute Force Attack'
        ACCOUNT_TAKEOVER = 'ACCOUNT_TAKEOVER', 'Account Takeover Attempt'
        SUSPICIOUS_LOCATION = 'SUSPICIOUS_LOCATION', 'Login from Suspicious Location'
        RATE_LIMITING = 'RATE_LIMITING', 'Rate Limit Violations'
        MULTIPLE_FAILURES = 'MULTIPLE_FAILURES', 'Multiple Authentication Failures'
        ANOMALOUS_BEHAVIOR = 'ANOMALOUS_BEHAVIOR', 'Anomalous User Behavior'
        PRIVILEGE_ESCALATION = 'PRIVILEGE_ESCALATION', 'Privilege Escalation Attempt'
        DATA_EXFILTRATION = 'DATA_EXFILTRATION', 'Potential Data Exfiltration'
        SESSION_ANOMALY = 'SESSION_ANOMALY', 'Session Anomaly Detected'
        API_ABUSE = 'API_ABUSE', 'API Abuse Detected'
    
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        INVESTIGATING = 'INVESTIGATING', 'Under Investigation'
        RESOLVED = 'RESOLVED', 'Resolved'
        FALSE_POSITIVE = 'FALSE_POSITIVE', 'False Positive'
        ESCALATED = 'ESCALATED', 'Escalated'
    
    alert_type = models.CharField(
        max_length=30,
        choices=AlertType.choices,
        help_text='Type of security alert'
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OPEN,
        help_text='Current status of the alert'
    )
    severity = models.CharField(
        max_length=10,
        choices=AuditLog.Severity.choices,
        default=AuditLog.Severity.MEDIUM,
        help_text='Alert severity level'
    )
    
    # Related entities
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='security_alerts',
        help_text='User associated with the alert'
    )
    audit_logs = models.ManyToManyField(
        AuditLog,
        related_name='security_alerts',
        help_text='Audit logs that triggered this alert'
    )
    
    # Alert details
    title = models.CharField(
        max_length=200,
        help_text='Alert title/summary'
    )
    description = models.TextField(
        help_text='Detailed description of the security event'
    )
    risk_score = models.PositiveIntegerField(
        default=0,
        help_text='Calculated risk score (0-100)'
    )
    
    # Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address associated with the alert'
    )
    user_agent = models.TextField(
        blank=True,
        help_text='User agent if applicable'
    )
    affected_resources = models.JSONField(
        default=list,
        blank=True,
        help_text='List of resources affected by this security event'
    )
    
    # Detection metadata
    detection_rules = models.JSONField(
        default=list,
        blank=True,
        help_text='Detection rules that triggered this alert'
    )
    confidence_score = models.PositiveIntegerField(
        default=50,
        help_text='Confidence in alert accuracy (0-100)'
    )
    
    # Investigation workflow
    assigned_to = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_alerts',
        help_text='Security analyst assigned to investigate'
    )
    investigation_notes = models.TextField(
        blank=True,
        help_text='Notes from security investigation'
    )
    
    # Resolution
    resolved_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts',
        help_text='Admin who resolved the alert'
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text='Notes about how the alert was resolved'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the alert was created'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When the alert was last updated'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the alert was resolved'
    )
    first_seen = models.DateTimeField(
        help_text='When the suspicious activity was first detected'
    )
    last_seen = models.DateTimeField(
        help_text='When the suspicious activity was last observed'
    )
    
    class Meta:
        app_label = 'audit'
        db_table = 'security_alerts'
        verbose_name = 'Security Alert'
        verbose_name_plural = 'Security Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['alert_type', 'created_at']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['severity', 'status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.alert_type} - {self.title} ({self.status})"
    
    def resolve(self, resolved_by, notes: str = '', status: str = None) -> None:
        """
        Mark the alert as resolved.
        
        Args:
            resolved_by: User who resolved the alert
            notes: Resolution notes
            status: Optional status override (defaults to RESOLVED)
        """
        self.status = status or self.Status.RESOLVED
        self.resolved_by = resolved_by
        self.resolution_notes = notes
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_by', 'resolution_notes', 'resolved_at'])
    
    def assign_to(self, analyst) -> None:
        """
        Assign alert to a security analyst.
        
        Args:
            analyst: User to assign the alert to
        """
        self.assigned_to = analyst
        self.status = self.Status.INVESTIGATING
        self.save(update_fields=['assigned_to', 'status'])
    
    def escalate(self, escalation_reason: str = '') -> None:
        """
        Escalate alert to higher priority.
        
        Args:
            escalation_reason: Reason for escalation
        """
        self.status = self.Status.ESCALATED
        if escalation_reason:
            self.investigation_notes += f"\n[ESCALATED] {escalation_reason}"
        self.save(update_fields=['status', 'investigation_notes'])
    
    def add_investigation_note(self, note: str, investigator=None) -> None:
        """
        Add a note to the investigation.
        
        Args:
            note: Investigation note to add
            investigator: User adding the note
        """
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        investigator_name = investigator.corporate_email if investigator else 'System'
        
        new_note = f"[{timestamp}] {investigator_name}: {note}"
        
        if self.investigation_notes:
            self.investigation_notes += f"\n{new_note}"
        else:
            self.investigation_notes = new_note
        
        self.save(update_fields=['investigation_notes'])
    
    def calculate_risk_score(self) -> int:
        """
        Calculate risk score based on alert properties and associated audit logs.
        
        Returns:
            int: Calculated risk score (0-100)
        """
        base_scores = {
            self.AlertType.BRUTE_FORCE: 60,
            self.AlertType.ACCOUNT_TAKEOVER: 90,
            self.AlertType.SUSPICIOUS_LOCATION: 40,
            self.AlertType.RATE_LIMITING: 30,
            self.AlertType.MULTIPLE_FAILURES: 50,
            self.AlertType.ANOMALOUS_BEHAVIOR: 45,
            self.AlertType.PRIVILEGE_ESCALATION: 85,
            self.AlertType.DATA_EXFILTRATION: 95,
            self.AlertType.SESSION_ANOMALY: 55,
            self.AlertType.API_ABUSE: 35,
        }
        
        severity_multipliers = {
            AuditLog.Severity.LOW: 1.0,
            AuditLog.Severity.MEDIUM: 1.2,
            AuditLog.Severity.HIGH: 1.5,
            AuditLog.Severity.CRITICAL: 1.8,
        }
        
        base_score = base_scores.get(self.alert_type, 30)
        severity_multiplier = severity_multipliers.get(self.severity, 1.0)
        
        # Factor in audit log count and patterns
        audit_count = self.audit_logs.count()
        if audit_count > 10:
            base_score += 10
        elif audit_count > 5:
            base_score += 5
        
        # Factor in confidence score
        confidence_factor = self.confidence_score / 100
        
        final_score = int(base_score * severity_multiplier * confidence_factor)
        
        return min(final_score, 100)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive alert summary for reporting.
        
        Returns:
            Dict containing alert summary
        """
        return {
            'alert_id': self.id,
            'type': self.get_alert_type_display(),
            'title': self.title,
            'severity': self.get_severity_display(),
            'status': self.get_status_display(),
            'risk_score': self.risk_score,
            'confidence_score': self.confidence_score,
            'user_email': self.user.corporate_email if self.user else None,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat(),
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'assigned_to': self.assigned_to.corporate_email if self.assigned_to else None,
            'resolved_by': self.resolved_by.corporate_email if self.resolved_by else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'audit_log_count': self.audit_logs.count(),
            'affected_resources': self.affected_resources,
            'detection_rules': self.detection_rules,
        }
    
    def get_timeline(self) -> List[Dict[str, Any]]:
        """
        Get chronological timeline of alert events.
        
        Returns:
            List of timeline events
        """
        timeline = []
        
        # Alert creation
        timeline.append({
            'timestamp': self.created_at,
            'event': 'Alert Created',
            'details': f'Security alert created: {self.title}',
            'actor': 'System'
        })
        
        # Assignment
        if self.assigned_to:
            timeline.append({
                'timestamp': self.updated_at,  # Approximation
                'event': 'Alert Assigned',
                'details': f'Assigned to {self.assigned_to.corporate_email}',
                'actor': 'System'
            })
        
        # Resolution
        if self.resolved_at:
            timeline.append({
                'timestamp': self.resolved_at,
                'event': 'Alert Resolved',
                'details': f'Resolved by {self.resolved_by.corporate_email if self.resolved_by else "Unknown"}',
                'actor': self.resolved_by.corporate_email if self.resolved_by else 'System'
            })
        
        return sorted(timeline, key=lambda x: x['timestamp'])
    
    @classmethod
    def create_from_audit_logs(
        cls,
        audit_logs: List[AuditLog],
        alert_type: str,
        title: str,
        description: str,
        **kwargs
    ) -> 'SecurityAlert':
        """
        Create security alert from a collection of audit logs.
        
        Args:
            audit_logs: List of AuditLog instances that triggered the alert
            alert_type: Type of alert from AlertType choices
            title: Alert title
            description: Alert description
            **kwargs: Additional alert fields
            
        Returns:
            Created SecurityAlert instance
        """
        if not audit_logs:
            raise ValueError("At least one audit log is required")
        
        # Determine primary context from audit logs
        first_log = audit_logs[0]
        latest_log = max(audit_logs, key=lambda log: log.timestamp)
        
        # Calculate severity based on audit log severities
        severities = [log.severity for log in audit_logs]
        if AuditLog.Severity.CRITICAL in severities:
            severity = AuditLog.Severity.CRITICAL
        elif AuditLog.Severity.HIGH in severities:
            severity = AuditLog.Severity.HIGH
        elif AuditLog.Severity.MEDIUM in severities:
            severity = AuditLog.Severity.MEDIUM
        else:
            severity = AuditLog.Severity.LOW
        
        # Extract common IP addresses and resources
        ip_addresses = list(set(log.ip_address for log in audit_logs if log.ip_address))
        resources = list(set(log.resource for log in audit_logs if log.resource))
        
        alert_data = {
            'alert_type': alert_type,
            'title': title,
            'description': description,
            'severity': severity,
            'user': first_log.user,
            'ip_address': ip_addresses[0] if ip_addresses else None,
            'user_agent': first_log.user_agent,
            'affected_resources': resources,
            'first_seen': first_log.timestamp,
            'last_seen': latest_log.timestamp,
            **kwargs
        }
        
        alert = cls.objects.create(**alert_data)
        
        # Associate audit logs
        alert.audit_logs.set(audit_logs)
        
        # Calculate and update risk score
        alert.risk_score = alert.calculate_risk_score()
        alert.save(update_fields=['risk_score'])
        
        return alert
    
    @classmethod
    def get_open_alerts_summary(cls) -> Dict[str, Any]:
        """
        Get summary of open security alerts.
        
        Returns:
            Dict containing open alerts summary
        """
        open_alerts = cls.objects.exclude(status__in=[cls.Status.RESOLVED, cls.Status.FALSE_POSITIVE])
        
        return {
            'total_open': open_alerts.count(),
            'critical_severity': open_alerts.filter(severity=AuditLog.Severity.CRITICAL).count(),
            'high_severity': open_alerts.filter(severity=AuditLog.Severity.HIGH).count(),
            'unassigned': open_alerts.filter(assigned_to__isnull=True).count(),
            'investigating': open_alerts.filter(status=cls.Status.INVESTIGATING).count(),
            'escalated': open_alerts.filter(status=cls.Status.ESCALATED).count(),
            'avg_risk_score': open_alerts.aggregate(
                avg_risk=models.Avg('risk_score')
            )['avg_risk'] or 0,
            'oldest_alert': open_alerts.order_by('created_at').first(),
            'by_type': {
                alert_type[0]: open_alerts.filter(alert_type=alert_type[0]).count()
                for alert_type in cls.AlertType.choices
            }
        }
    
    @classmethod
    def get_alert_trends(cls, days: int = 30) -> Dict[str, Any]:
        """
        Get alert trends over specified time period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict containing trend analysis
        """
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        alerts = cls.objects.filter(created_at__gte=start_date)
        
        # Daily alert counts
        daily_counts = {}
        current_date = start_date.date()
        while current_date <= end_date.date():
            count = alerts.filter(created_at__date=current_date).count()
            daily_counts[current_date.isoformat()] = count
            current_date += timedelta(days=1)
        
        return {
            'period_days': days,
            'total_alerts': alerts.count(),
            'daily_counts': daily_counts,
            'avg_per_day': round(alerts.count() / days, 2),
            'peak_day': max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None,
            'by_severity': {
                severity[0]: alerts.filter(severity=severity[0]).count()
                for severity in AuditLog.Severity.choices
            },
            'by_type': {
                alert_type[0]: alerts.filter(alert_type=alert_type[0]).count()
                for alert_type in cls.AlertType.choices
            },
            'resolution_rate': round(
                alerts.filter(status=cls.Status.RESOLVED).count() / alerts.count() * 100, 2
            ) if alerts.count() > 0 else 0
        }
