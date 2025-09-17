from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from base.swagger.enterprise_documentation import (
    CRUD_DOCUMENTATION, 
    get_custom_action_documentation,
    get_error_responses
)
from apps.audit.services import AuditService
from ..models import UMLChangeEvent
from ..serializers import (
    UMLChangeEventListSerializer,
    UMLChangeEventDetailSerializer,
    UMLChangeEventCreateSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=['Collaboration'],
        summary="List UML Change Events",
        description="Retrieve a paginated list of UML change events with advanced filtering, ordering, and search capabilities for collaboration tracking.",
        parameters=[
            OpenApiParameter(
                name='event_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by event type (create, update, delete, move, resize)"
            ),
            OpenApiParameter(
                name='session',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by collaboration session ID"
            ),
            OpenApiParameter(
                name='user',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by user who performed the change"
            ),
            OpenApiParameter(
                name='element_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by affected element type (class, interface, relationship, etc.)"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in event descriptions and change details"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: timestamp, event_type (prefix with '-' for descending)"
            ),
            OpenApiParameter(
                name='date_from',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter events from this date/time"
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter events until this date/time"
            ),
        ],
        responses=CRUD_DOCUMENTATION['list']['responses']
    ),
    create=extend_schema(
        tags=['Collaboration'],
        summary="Create UML Change Event",
        description="Record a new UML change event during collaboration sessions with validation and real-time tracking.",
        responses=CRUD_DOCUMENTATION['create']['responses']
    ),
    retrieve=extend_schema(
        tags=['Collaboration'],
        summary="Retrieve UML Change Event",
        description="Retrieve detailed information about a specific UML change event including before/after state and metadata.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    )
)
class UMLChangeEventViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for UML Change Event tracking with atomic transactions,
    real-time collaboration monitoring, comprehensive filtering, and audit logging.
    
    This ViewSet provides read-only access plus creation for tracking changes
    during collaborative editing sessions.
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['event_type', 'session', 'user', 'element_type']
    ordering_fields = ['timestamp', 'event_type']
    ordering = ['-timestamp']
    search_fields = ['description', 'change_details']
    # Read-only ViewSet with creation allowed for event tracking
    http_method_names = ['get', 'post', 'head', 'options']
    
    def get_queryset(self):
        """
        Enhanced queryset with optimized database queries and date filtering.
        """
        if getattr(self, 'swagger_fake_view', False):
            return UMLChangeEvent.objects.none()
            
        queryset = UMLChangeEvent.objects.filter(
            session__diagram__project__workspace__owner=self.request.user
        ).select_related(
            'session', 
            'user',
            'session__diagram'
        ).prefetch_related(
            'session__participants',
            'user__profile'
        )
        
        # Apply date range filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                from django.utils.dateparse import parse_datetime
                date_from_parsed = parse_datetime(date_from)
                if date_from_parsed:
                    queryset = queryset.filter(timestamp__gte=date_from_parsed)
            except ValueError:
                pass
        
        if date_to:
            try:
                from django.utils.dateparse import parse_datetime
                date_to_parsed = parse_datetime(date_to)
                if date_to_parsed:
                    queryset = queryset.filter(timestamp__lte=date_to_parsed)
            except ValueError:
                pass
        
        return queryset
    
    def get_serializer_class(self):
        """
        Dynamic serializer class selection based on action.
        """
        if self.action == 'list':
            return UMLChangeEventListSerializer
        elif self.action == 'create':
            return UMLChangeEventCreateSerializer
        return UMLChangeEventDetailSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Enhanced creation with validation and audit logging for change events.
        """
        try:
            session = serializer.validated_data.get('session')
            
            # Validate session is active
            if not session.is_active:
                raise ValidationError({
                    'error': 'SESSION_NOT_ACTIVE',
                    'message': 'Cannot record events for inactive session',
                    'details': {'session_id': session.id}
                })
            
            # Validate user is participant
            if not session.participants.filter(
                user=self.request.user,
                is_active=True,
                status='ACTIVE'
            ).exists():
                raise ValidationError({
                    'error': 'NOT_SESSION_PARTICIPANT',
                    'message': 'User is not an active participant in this session',
                    'details': {'session_id': session.id}
                })
            
            change_event = serializer.save(
                user=self.request.user,
                timestamp=timezone.now()
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE',
                resource_type='UML_CHANGE_EVENT',
                resource_id=change_event.id,
                details={
                    'event_type': change_event.event_type,
                    'session_id': session.id,
                    'element_type': change_event.element_type,
                    'diagram_id': session.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE', 'UML_CHANGE_EVENT')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Event Timeline",
        description="Get a chronological timeline of UML change events with filtering and pagination for collaboration history visualization.",
        parameters=[
            OpenApiParameter(
                name='session',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter timeline by specific session ID"
            ),
            OpenApiParameter(
                name='user',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter timeline by specific user ID"
            ),
            OpenApiParameter(
                name='event_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter timeline by event type"
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Limit number of events in timeline"
            ),
        ],
        responses={
            200: {
                'description': 'Timeline events retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'events': [
                                    {
                                        'id': 123,
                                        'event_type': 'create',
                                        'timestamp': '2024-01-15T10:30:00Z',
                                        'user': 'john_doe',
                                        'description': 'Created new class diagram',
                                        'element_type': 'class'
                                    }
                                ],
                                'total_events': 45,
                                'session_info': {
                                    'session_id': 789,
                                    'active_participants': 3
                                }
                            },
                            'message': 'Timeline retrieved successfully'
                        }
                    }
                }
            },
            **get_error_responses(['400'])
        }
    )
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """
        Get chronological timeline of change events for collaboration visualization.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply additional timeline-specific filtering
            limit = request.query_params.get('limit')
            if limit:
                try:
                    limit_int = int(limit)
                    queryset = queryset[:limit_int]
                except ValueError:
                    pass
            
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated_response = self.get_paginated_response(serializer.data)
                
                # Enhance response with timeline metadata
                response_data = paginated_response.data
                response_data.update({
                    'success': True,
                    'message': 'Timeline retrieved successfully',
                    'metadata': {
                        'total_events': queryset.count(),
                        'timeline_span': self._get_timeline_span(queryset),
                        'event_type_distribution': self._get_event_type_distribution(queryset)
                    }
                })
                
                # Audit logging for timeline access
                AuditService.log_user_action(
                    user=request.user,
                    action='VIEW',
                    resource_type='UML_CHANGE_TIMELINE',
                    details={
                        'events_count': len(serializer.data),
                        'filters_applied': dict(request.query_params)
                    }
                )
                
                return Response(response_data, status=status.HTTP_200_OK)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Timeline retrieved successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW', 'UML_CHANGE_TIMELINE')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Event Statistics",
        description="Get statistical analysis of UML change events including activity patterns, user contributions, and event type distributions.",
        parameters=[
            OpenApiParameter(
                name='session',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Calculate statistics for specific session"
            ),
            OpenApiParameter(
                name='date_from',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Calculate statistics from this date"
            ),
            OpenApiParameter(
                name='date_to',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Calculate statistics until this date"
            ),
        ],
        responses={
            200: {
                'description': 'Event statistics',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'total_events': 127,
                                'events_by_type': {
                                    'create': 45,
                                    'update': 62,
                                    'delete': 15,
                                    'move': 5
                                },
                                'events_by_user': {
                                    'john_doe': 78,
                                    'jane_smith': 49
                                },
                                'activity_timeline': [
                                    {'hour': '10:00', 'event_count': 15},
                                    {'hour': '11:00', 'event_count': 23}
                                ],
                                'avg_events_per_session': 42.3
                            },
                            'message': 'Statistics calculated successfully'
                        }
                    }
                }
            },
            **get_error_responses(['400'])
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get comprehensive statistics about UML change events.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Calculate various statistics
            total_events = queryset.count()
            
            # Events by type
            events_by_type = dict(
                queryset.values('event_type')
                .annotate(count=Count('id'))
                .values_list('event_type', 'count')
            )
            
            # Events by user
            events_by_user = dict(
                queryset.values('user__username')
                .annotate(count=Count('id'))
                .values_list('user__username', 'count')
            )
            
            # Events by element type
            events_by_element = dict(
                queryset.values('element_type')
                .annotate(count=Count('id'))
                .values_list('element_type', 'count')
            )
            
            # Session activity
            session_stats = queryset.values('session').annotate(
                event_count=Count('id')
            ).aggregate(
                total_sessions=Count('session', distinct=True),
                avg_events_per_session=Count('id') / Count('session', distinct=True) if queryset.exists() else 0
            )
            
            statistics_data = {
                'total_events': total_events,
                'events_by_type': events_by_type,
                'events_by_user': events_by_user,
                'events_by_element_type': events_by_element,
                'session_statistics': {
                    'total_sessions': session_stats['total_sessions'],
                    'avg_events_per_session': round(session_stats['avg_events_per_session'], 1)
                },
                'time_range': self._get_timeline_span(queryset)
            }
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='VIEW',
                resource_type='UML_CHANGE_STATISTICS',
                details={
                    'total_events_analyzed': total_events,
                    'filters_applied': dict(request.query_params)
                }
            )
            
            return Response({
                'success': True,
                'data': statistics_data,
                'message': 'Statistics calculated successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW', 'UML_CHANGE_STATISTICS')
            raise
    
    def _get_timeline_span(self, queryset):
        """
        Calculate the time span of events in the queryset.
        """
        if not queryset.exists():
            return None
        
        first_event = queryset.order_by('timestamp').first()
        last_event = queryset.order_by('-timestamp').first()
        
        return {
            'start': first_event.timestamp.isoformat(),
            'end': last_event.timestamp.isoformat(),
            'duration_hours': (last_event.timestamp - first_event.timestamp).total_seconds() / 3600
        }
    
    def _get_event_type_distribution(self, queryset):
        """
        Get distribution of event types as percentages.
        """
        total = queryset.count()
        if total == 0:
            return {}
        
        distribution = {}
        for event_type, count in queryset.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count'):
            distribution[event_type] = {
                'count': count,
                'percentage': round((count / total) * 100, 1)
            }
        
        return distribution
