"""
GenerationHistory ViewSet for SpringBoot code generation history tracking.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from datetime import timedelta
import csv
from django.http import HttpResponse, JsonResponse

from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from base.swagger.enterprise_documentation import (
    CRUD_DOCUMENTATION, 
    get_custom_action_documentation,
    get_error_responses
)
from apps.audit.services import AuditService
from ..models import GenerationHistory
from ..serializers import GenerationHistorySerializer, GenerationHistoryListSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Code Generation - History"],
        summary="List Generation History",
        description="Retrieve a paginated list of generation history entries with advanced filtering, search, and date range capabilities.",
        parameters=[
            OpenApiParameter(
                name='generation_request',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by generation request ID"
            ),
            OpenApiParameter(
                name='action_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by action type (CREATE, START, COMPLETE, FAIL, CANCEL, etc.)"
            ),
            OpenApiParameter(
                name='performed_by',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by user ID who performed the action"
            ),
            OpenApiParameter(
                name='date_from',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter entries from this date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter entries to this date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in action details and execution context"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: timestamp, action_type (prefix with '-' for descending)"
            ),
        ],
        responses=CRUD_DOCUMENTATION['list']['responses']
    ),
    retrieve=extend_schema(
        tags=["Code Generation - History"],
        summary="Retrieve History Entry",
        description="Retrieve detailed information about a specific generation history entry including execution context and metadata.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    ),
    destroy=extend_schema(
        tags=["Code Generation - History"],
        summary="Delete History Entry",
        description="Delete a history entry (staff only). This action is logged for audit purposes.",
        responses=CRUD_DOCUMENTATION['destroy']['responses']
    )
)
class GenerationHistoryViewSet(EnterpriseViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Enterprise ViewSet for Generation History management with comprehensive audit logging,
    advanced analytics, and secure data export capabilities.
    
    Provides read-only access to generation history with enterprise-grade filtering,
    reporting, and data export features for business intelligence and compliance.
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['generation_request', 'action_type', 'performed_by']
    search_fields = ['action_details', 'execution_context']
    ordering_fields = ['timestamp', 'action_type']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """
        Enhanced queryset with optimized queries and enterprise permissions.
        """
        if getattr(self, 'swagger_fake_view', False):
            return GenerationHistory.objects.none()
            
        queryset = GenerationHistory.objects.select_related(
            'generation_request',
            'performed_by'
        ).prefetch_related(
            'generation_request__diagram',
            'generation_request__created_by'
        )
        
        # Apply permission-based filtering
        if not self.request.user.is_staff:
            # Non-staff users can only see history from their own generation requests
            queryset = queryset.filter(
                Q(generation_request__created_by=self.request.user) |
                Q(performed_by=self.request.user)
            )
        
        # Apply advanced date filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                from django.utils.dateparse import parse_date
                parsed_date = parse_date(date_from)
                if parsed_date:
                    queryset = queryset.filter(timestamp__date__gte=parsed_date)
            except (ValueError, TypeError):
                # Invalid date format - ignore silently for better UX
                pass
        
        if date_to:
            try:
                from django.utils.dateparse import parse_date
                parsed_date = parse_date(date_to)
                if parsed_date:
                    queryset = queryset.filter(timestamp__date__lte=parsed_date)
            except (ValueError, TypeError):
                # Invalid date format - ignore silently for better UX
                pass
        
        return queryset
    
    def get_serializer_class(self):
        """
        Dynamic serializer selection based on action and performance requirements.
        """
        if self.action == 'list':
            return GenerationHistoryListSerializer
        return GenerationHistorySerializer
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Enhanced deletion with enterprise audit logging and staff-only access.
        """
        try:
            if not request.user.is_staff:
                raise ValidationError({
                    'error': 'PERMISSION_DENIED',
                    'message': 'Only staff members can delete history entries',
                    'details': {'required_role': 'staff'}
                })
            
            instance = self.get_object()
            
            # Audit logging before deletion
            AuditService.log_user_action(
                user=request.user,
                action='DELETE',
                resource_type='GENERATION_HISTORY',
                resource_id=instance.id,
                details={
                    'deleted_entry': {
                        'action_type': instance.action_type,
                        'timestamp': instance.timestamp.isoformat(),
                        'generation_request_id': instance.generation_request.id if instance.generation_request else None,
                        'performed_by': instance.performed_by.id if instance.performed_by else None
                    }
                }
            )
            
            return super().destroy(request, *args, **kwargs)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'DELETE', 'GENERATION_HISTORY')
            raise
    
    @extend_schema(
        tags=["Code Generation - History"],
        summary="Get Activity Timeline",
        description="Retrieve a comprehensive timeline view of generation activities with advanced analytics and trend analysis.",
        parameters=[
            OpenApiParameter(
                name='generation_request',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by generation request ID"
            ),
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of days to include in timeline (default: 7, max: 365)"
            ),
            OpenApiParameter(
                name='granularity',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Timeline granularity: 'hour', 'day', 'week' (default: 'day')"
            ),
        ],
        responses={
            200: {
                'description': 'Timeline data retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'timeline': [
                                    {
                                        'date': '2024-01-15',
                                        'entries': [
                                            {
                                                'id': '123e4567-e89b-12d3-a456-426614174000',
                                                'timestamp': '2024-01-15T10:30:00Z',
                                                'action': 'START',
                                                'action_display': 'Generation Started',
                                                'generation_request_name': 'E-commerce API',
                                                'user': 'john_doe'
                                            }
                                        ],
                                        'entry_count': 8
                                    }
                                ],
                                'summary': {
                                    'total_entries': 45,
                                    'action_breakdown': {
                                        'START': 15,
                                        'COMPLETE': 12,
                                        'FAIL': 3
                                    },
                                    'most_active_day': '2024-01-15'
                                }
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400'])
        }
    )
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """Get comprehensive activity timeline with enterprise analytics."""
        try:
            # Validate and parse parameters
            days = min(int(request.query_params.get('days', 7)), 365)  # Cap at 1 year
            generation_request_id = request.query_params.get('generation_request')
            granularity = request.query_params.get('granularity', 'day').lower()
            
            if granularity not in ['hour', 'day', 'week']:
                raise ValidationError({
                    'error': 'INVALID_GRANULARITY',
                    'message': 'Granularity must be one of: hour, day, week',
                    'details': {'provided': granularity, 'valid_options': ['hour', 'day', 'week']}
                })
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            queryset = self.get_queryset().filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if generation_request_id:
                try:
                    generation_request_id = int(generation_request_id)
                    queryset = queryset.filter(generation_request_id=generation_request_id)
                except (ValueError, TypeError):
                    raise ValidationError({
                        'error': 'INVALID_GENERATION_REQUEST_ID',
                        'message': 'Generation request ID must be a valid integer',
                        'details': {'provided': generation_request_id}
                    })
            
            # Group entries by granularity
            timeline = {}
            action_counts = {}
            user_activity = {}
            
            for entry in queryset.order_by('timestamp'):
                # Determine the grouping key based on granularity
                if granularity == 'hour':
                    group_key = entry.timestamp.strftime('%Y-%m-%d %H:00')
                elif granularity == 'week':
                    week_start = entry.timestamp.date() - timedelta(days=entry.timestamp.weekday())
                    group_key = week_start.isoformat()
                else:  # day
                    group_key = entry.timestamp.date().isoformat()
                
                if group_key not in timeline:
                    timeline[group_key] = []
                
                timeline[group_key].append({
                    'id': str(entry.id),
                    'timestamp': entry.timestamp.isoformat(),
                    'action': entry.action_type,
                    'action_display': entry.get_action_type_display() if hasattr(entry, 'get_action_type_display') else entry.action_type,
                    'generation_request_id': entry.generation_request.id if entry.generation_request else None,
                    'generation_request_name': entry.generation_request.project_name if entry.generation_request else None,
                    'user': entry.performed_by.username if entry.performed_by else 'System',
                    'user_id': entry.performed_by.id if entry.performed_by else None
                })
                
                # Count actions and user activity
                action_counts[entry.action_type] = action_counts.get(entry.action_type, 0) + 1
                if entry.performed_by:
                    username = entry.performed_by.username
                    user_activity[username] = user_activity.get(username, 0) + 1
            
            # Convert to sorted list format
            timeline_list = []
            for group_key in sorted(timeline.keys()):
                timeline_list.append({
                    'period': group_key,
                    'entries': timeline[group_key],
                    'entry_count': len(timeline[group_key]),
                    'unique_users': len(set(entry['user'] for entry in timeline[group_key] if entry['user'])),
                    'action_summary': {}
                })
                
                # Add action summary for this period
                period_actions = {}
                for entry in timeline[group_key]:
                    period_actions[entry['action']] = period_actions.get(entry['action'], 0) + 1
                timeline_list[-1]['action_summary'] = period_actions
            
            response_data = {
                'timeline': timeline_list,
                'summary': {
                    'total_entries': queryset.count(),
                    'unique_users': len(user_activity),
                    'action_breakdown': action_counts,
                    'most_active_period': max(timeline.keys(), key=lambda d: len(timeline[d])) if timeline else None,
                    'most_active_user': max(user_activity.keys(), key=user_activity.get) if user_activity else None,
                    'average_daily_activity': round(queryset.count() / max(days, 1), 2)
                },
                'date_range': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.date().isoformat(),
                    'days_included': days,
                    'granularity': granularity
                }
            }
            
            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'GET_TIMELINE', 'GENERATION_HISTORY')
            raise
    
    @extend_schema(
        tags=["Code Generation - History"],
        summary="Get User Activity Statistics",
        description="Retrieve comprehensive user activity statistics with detailed breakdown and comparative analytics.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by specific user ID"
            ),
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Time period: 'week', 'month', 'quarter', 'year' (default: 'month')"
            ),
        ],
        responses={
            200: {
                'description': 'User activity statistics retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'user_stats': [
                                    {
                                        'user_id': 123,
                                        'username': 'john_doe',
                                        'total_actions': 45,
                                        'action_breakdown': {
                                            'START': 15,
                                            'COMPLETE': 12,
                                            'FAIL': 3
                                        },
                                        'most_common_action': 'START',
                                        'success_rate': 80.0
                                    }
                                ],
                                'period_info': {
                                    'period': 'month',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31'
                                }
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400'])
        }
    )
    @action(detail=False, methods=['get'])
    def user_activity(self, request):
        """Get comprehensive user activity statistics with enterprise validation."""
        try:
            period = request.query_params.get('period', 'month').lower()
            user_id = request.query_params.get('user_id')
            
            # Validate period parameter
            valid_periods = ['week', 'month', 'quarter', 'year']
            if period not in valid_periods:
                raise ValidationError({
                    'error': 'INVALID_PERIOD',
                    'message': f'Period must be one of: {", ".join(valid_periods)}',
                    'details': {'provided': period, 'valid_options': valid_periods}
                })
            
            # Calculate date range based on period
            end_date = timezone.now()
            if period == 'week':
                start_date = end_date - timedelta(weeks=1)
            elif period == 'month':
                start_date = end_date - timedelta(days=30)
            elif period == 'quarter':
                start_date = end_date - timedelta(days=90)
            elif period == 'year':
                start_date = end_date - timedelta(days=365)
            
            queryset = self.get_queryset().filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            # Validate and filter by user_id if provided
            if user_id:
                try:
                    user_id = int(user_id)
                    queryset = queryset.filter(performed_by_id=user_id)
                except (ValueError, TypeError):
                    raise ValidationError({
                        'error': 'INVALID_USER_ID',
                        'message': 'User ID must be a valid integer',
                        'details': {'provided': user_id}
                    })
            
            # Aggregate by user using optimized query
            user_activity = queryset.values(
                'performed_by__username', 
                'performed_by__id',
                'performed_by__first_name',
                'performed_by__last_name'
            ).annotate(
                total_actions=Count('id')
            ).order_by('-total_actions')
            
            # Get detailed breakdown for each user
            user_stats = []
            success_actions = ['COMPLETE', 'SUCCESS']  # Define success actions
            
            for user_data in user_activity:
                if not user_data['performed_by__id']:
                    continue  # Skip entries with no associated user
                
                user_queryset = queryset.filter(performed_by_id=user_data['performed_by__id'])
                
                # Calculate action breakdown
                action_breakdown = {}
                success_count = 0
                
                for entry in user_queryset:
                    action_type = entry.action_type
                    action_breakdown[action_type] = action_breakdown.get(action_type, 0) + 1
                    if action_type in success_actions:
                        success_count += 1
                
                total_actions = user_data['total_actions']
                success_rate = (success_count / total_actions * 100) if total_actions > 0 else 0
                
                # Get full name
                first_name = user_data['performed_by__first_name'] or ''
                last_name = user_data['performed_by__last_name'] or ''
                full_name = f"{first_name} {last_name}".strip() or user_data['performed_by__username']
                
                user_stats.append({
                    'user_id': user_data['performed_by__id'],
                    'username': user_data['performed_by__username'],
                    'full_name': full_name,
                    'total_actions': total_actions,
                    'action_breakdown': action_breakdown,
                    'most_common_action': max(action_breakdown.keys(), key=action_breakdown.get) if action_breakdown else None,
                    'success_rate': round(success_rate, 2),
                    'success_count': success_count,
                    'avg_actions_per_day': round(total_actions / max((end_date - start_date).days, 1), 2)
                })
            
            # Calculate comparative metrics
            if user_stats:
                avg_actions_per_user = sum(u['total_actions'] for u in user_stats) / len(user_stats)
                top_performer = max(user_stats, key=lambda x: x['total_actions'])
                most_successful_user = max(user_stats, key=lambda x: x['success_rate'])
            else:
                avg_actions_per_user = 0
                top_performer = None
                most_successful_user = None
            
            response_data = {
                'user_stats': user_stats,
                'period_info': {
                    'period': period,
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.date().isoformat(),
                    'days_included': (end_date - start_date).days
                },
                'totals': {
                    'total_entries': queryset.count(),
                    'unique_users': len(user_stats),
                    'avg_actions_per_user': round(avg_actions_per_user, 2),
                    'top_performer': {
                        'user_id': top_performer['user_id'],
                        'username': top_performer['username'],
                        'actions': top_performer['total_actions']
                    } if top_performer else None,
                    'most_successful_user': {
                        'user_id': most_successful_user['user_id'],
                        'username': most_successful_user['username'],
                        'success_rate': most_successful_user['success_rate']
                    } if most_successful_user else None
                }
            }
            
            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'GET_USER_ACTIVITY', 'GENERATION_HISTORY')
            raise
    
    @extend_schema(
        tags=["Code Generation - History"],
        summary="Get Action Statistics",
        description="Retrieve comprehensive statistics about different types of actions performed with trend analysis and comparative metrics.",
        responses={
            200: {
                'description': 'Action statistics retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'action_stats': [
                                    {
                                        'action': 'START',
                                        'action_display': 'Generation Started',
                                        'count': 45,
                                        'percentage': 35.7,
                                        'avg_per_day': 1.5
                                    }
                                ],
                                'totals': {
                                    'total_actions': 126,
                                    'unique_action_types': 6,
                                    'date_range': {
                                        'earliest': '2024-01-01T00:00:00Z',
                                        'latest': '2024-01-15T23:59:59Z'
                                    }
                                },
                                'trends': {
                                    'START': {
                                        'recent_count': 12,
                                        'previous_count': 8,
                                        'change_percent': 50.0,
                                        'trend': 'up'
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def action_statistics(self, request):
        """Get comprehensive action statistics with enterprise analytics."""
        try:
            queryset = self.get_queryset()
            
            if not queryset.exists():
                return Response({
                    'success': True,
                    'data': {
                        'action_stats': [],
                        'totals': {'total_actions': 0, 'unique_action_types': 0},
                        'trends': {},
                        'message': 'No history data available for analysis'
                    }
                }, status=status.HTTP_200_OK)
            
            # Overall action counts with optimized aggregation
            action_counts = queryset.values('action_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            total_count = queryset.count()
            earliest_entry = queryset.order_by('timestamp').first()
            latest_entry = queryset.order_by('-timestamp').first()
            
            # Calculate date span for average calculations
            if earliest_entry and latest_entry:
                date_span_days = max((latest_entry.timestamp.date() - earliest_entry.timestamp.date()).days, 1)
            else:
                date_span_days = 1
            
            # Recent trends (last 7 days vs previous 7 days)
            now = timezone.now()
            recent_week_start = now - timedelta(days=7)
            previous_week_start = now - timedelta(days=14)
            
            recent_actions = queryset.filter(timestamp__gte=recent_week_start)
            previous_actions = queryset.filter(
                timestamp__gte=previous_week_start,
                timestamp__lt=recent_week_start
            )
            
            # Use aggregation for better performance
            recent_counts = dict(recent_actions.values('action_type').annotate(
                count=Count('id')
            ).values_list('action_type', 'count'))
            
            previous_counts = dict(previous_actions.values('action_type').annotate(
                count=Count('id')
            ).values_list('action_type', 'count'))
            
            # Calculate trends with enhanced analytics
            trends = {}
            all_action_types = set(list(recent_counts.keys()) + list(previous_counts.keys()))
            
            for action in all_action_types:
                recent = recent_counts.get(action, 0)
                previous = previous_counts.get(action, 0)
                
                if previous > 0:
                    change_percent = ((recent - previous) / previous) * 100
                elif recent > 0:
                    change_percent = 100  # New activity
                else:
                    change_percent = 0
                
                # Determine trend direction with thresholds
                if change_percent > 10:
                    trend_direction = 'significantly_up'
                elif change_percent > 0:
                    trend_direction = 'up'
                elif change_percent < -10:
                    trend_direction = 'significantly_down'
                elif change_percent < 0:
                    trend_direction = 'down'
                else:
                    trend_direction = 'stable'
                
                trends[action] = {
                    'recent_count': recent,
                    'previous_count': previous,
                    'change_percent': round(change_percent, 2),
                    'trend': trend_direction,
                    'momentum': 'gaining' if recent > previous else 'losing' if recent < previous else 'steady'
                }
            
            # Build enhanced action statistics
            action_stats = []
            for item in action_counts:
                action_type = item['action_type']
                count = item['count']
                percentage = round((count / total_count) * 100, 2) if total_count > 0 else 0
                avg_per_day = round(count / date_span_days, 2)
                
                action_stats.append({
                    'action': action_type,
                    'action_display': getattr(GenerationHistory, 'ActionType', {}).get(action_type, action_type),
                    'count': count,
                    'percentage': percentage,
                    'avg_per_day': avg_per_day,
                    'trend_info': trends.get(action_type, {})
                })
            
            response_data = {
                'action_stats': action_stats,
                'totals': {
                    'total_actions': total_count,
                    'unique_action_types': len(action_counts),
                    'date_range': {
                        'earliest': earliest_entry.timestamp.isoformat() if earliest_entry else None,
                        'latest': latest_entry.timestamp.isoformat() if latest_entry else None,
                        'span_days': date_span_days
                    },
                    'avg_actions_per_day': round(total_count / date_span_days, 2)
                },
                'trends': trends,
                'analysis_period': {
                    'recent_week': recent_week_start.date().isoformat(),
                    'previous_week': previous_week_start.date().isoformat(),
                    'total_recent': sum(recent_counts.values()),
                    'total_previous': sum(previous_counts.values())
                }
            }
            
            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'GET_ACTION_STATISTICS', 'GENERATION_HISTORY')
            raise
    
    @extend_schema(
        tags=["Code Generation - History"],
        summary="Export History Data",
        description="Export generation history data as CSV or JSON with enterprise security, audit logging, and comprehensive filtering capabilities.",
        parameters=[
            OpenApiParameter(
                name='format',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Export format: 'csv' or 'json' (default: 'json')"
            ),
            OpenApiParameter(
                name='generation_request',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by generation request ID"
            ),
            OpenApiParameter(
                name='date_from',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Export from this date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Export to this date (YYYY-MM-DD)"
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries to export (default: 10000, max: 50000)"
            ),
        ],
        responses={
            200: {
                'description': 'Data exported successfully',
                'content': {
                    'text/csv': {
                        'example': 'CSV file download'
                    },
                    'application/json': {
                        'example': {
                            'export_info': {
                                'exported_at': '2024-01-15T15:30:00Z',
                                'exported_by': 'admin_user',
                                'total_entries': 1250,
                                'format': 'json'
                            },
                            'data': []
                        }
                    }
                }
            },
            **get_error_responses(['400', '403'])
        }
    )
    @transaction.atomic
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export history data with enterprise security and comprehensive audit logging."""
        try:
            # Validate user permissions for data export
            if not request.user.is_staff:
                raise ValidationError({
                    'error': 'EXPORT_PERMISSION_DENIED',
                    'message': 'Data export is restricted to staff members only',
                    'details': {'required_role': 'staff'}
                })
            
            # Parse and validate parameters
            export_format = request.query_params.get('format', 'json').lower()
            generation_request_id = request.query_params.get('generation_request')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            limit = min(int(request.query_params.get('limit', 10000)), 50000)  # Cap at 50k records
            
            # Validate export format
            if export_format not in ['csv', 'json']:
                raise ValidationError({
                    'error': 'INVALID_EXPORT_FORMAT',
                    'message': 'Export format must be either "csv" or "json"',
                    'details': {'provided': export_format, 'valid_options': ['csv', 'json']}
                })
            
            # Build filtered queryset
            queryset = self.get_queryset()
            filters_applied = {}
            
            # Apply generation request filter
            if generation_request_id:
                try:
                    generation_request_id = int(generation_request_id)
                    queryset = queryset.filter(generation_request_id=generation_request_id)
                    filters_applied['generation_request'] = generation_request_id
                except (ValueError, TypeError):
                    raise ValidationError({
                        'error': 'INVALID_GENERATION_REQUEST_ID',
                        'message': 'Generation request ID must be a valid integer'
                    })
            
            # Apply date filters
            if date_from:
                try:
                    from django.utils.dateparse import parse_date
                    parsed_date = parse_date(date_from)
                    if parsed_date:
                        queryset = queryset.filter(timestamp__date__gte=parsed_date)
                        filters_applied['date_from'] = date_from
                    else:
                        raise ValidationError({
                            'error': 'INVALID_DATE_FORMAT',
                            'message': 'date_from must be in YYYY-MM-DD format'
                        })
                except (ValueError, TypeError):
                    raise ValidationError({
                        'error': 'INVALID_DATE_FORMAT',
                        'message': 'date_from must be in YYYY-MM-DD format'
                    })
            
            if date_to:
                try:
                    from django.utils.dateparse import parse_date
                    parsed_date = parse_date(date_to)
                    if parsed_date:
                        queryset = queryset.filter(timestamp__date__lte=parsed_date)
                        filters_applied['date_to'] = date_to
                    else:
                        raise ValidationError({
                            'error': 'INVALID_DATE_FORMAT',
                            'message': 'date_to must be in YYYY-MM-DD format'
                        })
                except (ValueError, TypeError):
                    raise ValidationError({
                        'error': 'INVALID_DATE_FORMAT',
                        'message': 'date_to must be in YYYY-MM-DD format'
                    })
            
            # Apply limit and ordering
            queryset = queryset.order_by('-timestamp')[:limit]
            
            # Check if export would be empty
            if not queryset.exists():
                # Still log the export attempt
                AuditService.log_user_action(
                    user=request.user,
                    action='EXPORT_HISTORY_EMPTY',
                    resource_type='GENERATION_HISTORY',
                    resource_id=None,
                    details={
                        'format': export_format,
                        'filters': filters_applied,
                        'result': 'No data found matching criteria'
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'No data found matching the specified criteria',
                    'export_info': {
                        'exported_at': timezone.now().isoformat(),
                        'exported_by': request.user.username,
                        'total_entries': 0,
                        'format': export_format,
                        'filters_applied': filters_applied
                    }
                }, status=status.HTTP_200_OK)
            
            # Prepare export data with enhanced fields
            export_data = []
            for entry in queryset:
                export_data.append({
                    'id': str(entry.id),
                    'timestamp': entry.timestamp.isoformat(),
                    'date': entry.timestamp.date().isoformat(),
                    'time': entry.timestamp.time().isoformat(),
                    'generation_request_id': str(entry.generation_request.id) if entry.generation_request else '',
                    'generation_request_name': entry.generation_request.project_name if entry.generation_request else '',
                    'user_id': entry.performed_by.id if entry.performed_by else '',
                    'username': entry.performed_by.username if entry.performed_by else 'System',
                    'user_full_name': f"{entry.performed_by.first_name} {entry.performed_by.last_name}".strip() if entry.performed_by else '',
                    'action': entry.action_type,
                    'action_display': entry.get_action_type_display() if hasattr(entry, 'get_action_type_display') else entry.action_type,
                    'details': str(entry.action_details) if entry.action_details else '',
                    'execution_context': str(entry.execution_context) if hasattr(entry, 'execution_context') and entry.execution_context else '',
                    'ip_address': getattr(entry, 'ip_address', '') or '',
                    'user_agent': getattr(entry, 'user_agent', '') or ''
                })
            
            # Audit logging for export
            AuditService.log_user_action(
                user=request.user,
                action='EXPORT_HISTORY',
                resource_type='GENERATION_HISTORY',
                resource_id=None,
                details={
                    'format': export_format,
                    'total_entries': len(export_data),
                    'filters_applied': filters_applied,
                    'export_timestamp': timezone.now().isoformat()
                }
            )
            
            # Generate export response based on format
            if export_format == 'csv':
                response = HttpResponse(content_type='text/csv')
                filename = f"generation_history_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                if export_data:
                    writer = csv.DictWriter(response, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    writer.writerows(export_data)
                
                return response
            
            else:  # JSON format
                response_data = {
                    'export_info': {
                        'exported_at': timezone.now().isoformat(),
                        'exported_by': request.user.username,
                        'total_entries': len(export_data),
                        'format': export_format,
                        'filters_applied': filters_applied,
                        'query_limit': limit
                    },
                    'data': export_data
                }
                
                return JsonResponse(response_data, safe=False)
                
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'EXPORT_HISTORY', 'GENERATION_HISTORY')
            raise
