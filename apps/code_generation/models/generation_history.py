"""
GenerationHistory model for tracking code generation audit trail.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class GenerationHistory(models.Model):
    """
    Audit trail for code generation activities with comprehensive tracking.
    """
    
    class ActionType(models.TextChoices):
        GENERATION_STARTED = 'GENERATION_STARTED', 'Generation Started'
        GENERATION_COMPLETED = 'GENERATION_COMPLETED', 'Generation Completed'
        GENERATION_FAILED = 'GENERATION_FAILED', 'Generation Failed'
        GENERATION_CANCELLED = 'GENERATION_CANCELLED', 'Generation Cancelled'
        PROJECT_DOWNLOADED = 'PROJECT_DOWNLOADED', 'Project Downloaded'
        PROJECT_ARCHIVED = 'PROJECT_ARCHIVED', 'Project Archived'
        PROJECT_DELETED = 'PROJECT_DELETED', 'Project Deleted'
        TEMPLATE_APPLIED = 'TEMPLATE_APPLIED', 'Template Applied'
        CONFIG_UPDATED = 'CONFIG_UPDATED', 'Configuration Updated'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation_request = models.ForeignKey(
        'code_generation.GenerationRequest',
        on_delete=models.CASCADE,
        related_name='history_entries'
    )
    action_type = models.CharField(
        max_length=25,
        choices=ActionType.choices
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='generation_actions'
    )
    action_details = models.JSONField(
        default=dict,
        help_text="Detailed information about the action"
    )
    execution_context = models.JSONField(
        default=dict,
        help_text="Context information when action was performed"
    )
    execution_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duration of the action execution"
    )
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'generation_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['generation_request', 'timestamp']),
            models.Index(fields=['performed_by', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.timestamp}"
    
    @classmethod
    def log_action(cls, generation_request, action_type: str, user: User,
                   details: dict = None, context: dict = None, 
                   success: bool = True, error_message: str = None,
                   duration=None, ip_address: str = None, 
                   user_agent: str = None) -> 'GenerationHistory':
        """Log generation action with comprehensive details."""
        
        return cls.objects.create(
            generation_request=generation_request,
            action_type=action_type,
            performed_by=user,
            action_details=details or {},
            execution_context=context or {},
            execution_duration=duration,
            success=success,
            error_message=error_message or '',
            ip_address=ip_address,
            user_agent=user_agent or ''
        )
    
    def get_formatted_details(self) -> dict:
        """Get formatted action details for display."""
        base_info = {
            'action': self.get_action_type_display(),
            'user': self.performed_by.full_name,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success
        }
        
        if self.execution_duration:
            base_info['duration'] = str(self.execution_duration)
        
        if not self.success:
            base_info['error'] = self.error_message
        
        # Merge with action-specific details
        base_info.update(self.action_details)
        
        return base_info
    
    @classmethod
    def get_generation_timeline(cls, generation_request) -> list:
        """Get chronological timeline of generation activities."""
        history_entries = cls.objects.filter(
            generation_request=generation_request
        ).order_by('timestamp')
        
        timeline = []
        for entry in history_entries:
            timeline.append({
                'id': str(entry.id),
                'action': entry.get_action_type_display(),
                'timestamp': entry.timestamp.isoformat(),
                'user': entry.performed_by.full_name,
                'success': entry.success,
                'details': entry.action_details,
                'duration': str(entry.execution_duration) if entry.execution_duration else None
            })
        
        return timeline
    
    @classmethod
    def get_user_statistics(cls, user: User, days: int = 30) -> dict:
        """Get generation statistics for user over specified period."""
        from django.utils import timezone
        
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        user_actions = cls.objects.filter(
            performed_by=user,
            timestamp__gte=start_date
        )
        
        stats = {
            'total_actions': user_actions.count(),
            'successful_actions': user_actions.filter(success=True).count(),
            'failed_actions': user_actions.filter(success=False).count(),
            'generations_started': user_actions.filter(
                action_type=cls.ActionType.GENERATION_STARTED
            ).count(),
            'generations_completed': user_actions.filter(
                action_type=cls.ActionType.GENERATION_COMPLETED
            ).count(),
            'projects_downloaded': user_actions.filter(
                action_type=cls.ActionType.PROJECT_DOWNLOADED
            ).count(),
            'action_breakdown': {}
        }
        
        # Get breakdown by action type
        action_counts = user_actions.values('action_type').annotate(
            count=models.Count('action_type')
        )
        
        for action in action_counts:
            action_type = action['action_type']
            stats['action_breakdown'][action_type] = action['count']
        
        # Calculate success rate
        if stats['total_actions'] > 0:
            stats['success_rate'] = (stats['successful_actions'] / stats['total_actions']) * 100
        else:
            stats['success_rate'] = 0
        
        return stats
    
    @classmethod
    def get_system_statistics(cls, days: int = 30) -> dict:
        """Get system-wide generation statistics."""
        from django.utils import timezone
        
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        all_actions = cls.objects.filter(timestamp__gte=start_date)
        
        stats = {
            'total_actions': all_actions.count(),
            'unique_users': all_actions.values('performed_by').distinct().count(),
            'total_generations': all_actions.filter(
                action_type__in=[
                    cls.ActionType.GENERATION_STARTED,
                    cls.ActionType.GENERATION_COMPLETED,
                    cls.ActionType.GENERATION_FAILED
                ]
            ).count(),
            'success_rate': 0,
            'most_active_users': [],
            'daily_activity': []
        }
        
        # Calculate success rate
        completed = all_actions.filter(action_type=cls.ActionType.GENERATION_COMPLETED).count()
        started = all_actions.filter(action_type=cls.ActionType.GENERATION_STARTED).count()
        
        if started > 0:
            stats['success_rate'] = (completed / started) * 100
        
        # Get most active users
        user_activity = all_actions.values('performed_by__full_name').annotate(
            action_count=models.Count('id')
        ).order_by('-action_count')[:10]
        
        stats['most_active_users'] = [
            {'user': user['performed_by__full_name'], 'actions': user['action_count']}
            for user in user_activity
        ]
        
        # Get daily activity breakdown
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        daily_activity = all_actions.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        stats['daily_activity'] = [
            {'date': activity['date'].isoformat(), 'count': activity['count']}
            for activity in daily_activity
        ]
        
        return stats
