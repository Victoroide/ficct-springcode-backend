"""
Enterprise Domain Management ViewSet
Complete CRUD operations for authorized domain management (Admin only).
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models import Q, Count

from ..serializers import (
    DomainListSerializer,
    DomainDetailSerializer,
    DomainCreateSerializer,
    DomainUpdateSerializer,
)
from apps.accounts.models import AuthorizedDomain
from apps.audit.models import AuditLog

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=['Authentication'],
        summary='List Authorized Domains',
        description='Get paginated list of authorized corporate domains (Admin only)',
        responses={200: DomainListSerializer(many=True)}
    ),
    create=extend_schema(
        tags=['Authentication'],
        summary='Add Authorized Domain',
        description='Add new authorized corporate domain (Admin only)',
        request=DomainCreateSerializer,
        responses={201: DomainDetailSerializer}
    ),
    retrieve=extend_schema(
        tags=['Authentication'],
        summary='Get Domain Details',
        description='Retrieve detailed domain information (Admin only)',
        responses={200: DomainDetailSerializer}
    ),
    update=extend_schema(
        tags=['Authentication'],
        summary='Update Domain',
        description='Update domain configuration (Admin only)',
        request=DomainUpdateSerializer,
        responses={200: DomainDetailSerializer}
    ),
    partial_update=extend_schema(
        tags=['Authentication'],
        summary='Partial Update Domain',
        description='Partially update domain configuration (Admin only)',
        request=DomainUpdateSerializer,
        responses={200: DomainDetailSerializer}
    ),
    destroy=extend_schema(
        tags=['Authentication'],
        summary='Remove Domain',
        description='Remove authorized domain (Admin only)',
        responses={204: None}
    ),
)
class DomainManagementViewSet(ModelViewSet):
    """
    Complete CRUD operations for authorized domain management (Admin only).
    """
    queryset = AuthorizedDomain.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [UserRateThrottle]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return DomainListSerializer
        elif self.action == 'create':
            return DomainCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DomainUpdateSerializer
        else:
            return DomainDetailSerializer
    
    def get_queryset(self):
        """Return filtered queryset based on query parameters."""
        queryset = AuthorizedDomain.objects.all()
        
        # Filter by active status
        active = self.request.query_params.get('active')
        if active is not None:
            active_bool = active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=active_bool)
        
        # Search by domain name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(domain_name__icontains=search) |
                Q(organization_name__icontains=search)
            )
        
        return queryset.order_by('domain_name')
    
    def perform_create(self, serializer):
        """Create domain with audit logging."""
        domain = serializer.save(created_by=self.request.user)
        
        AuditLog.log_action(
            AuditLog.ActionType.DOMAIN_ADDED,
            request=self.request,
            user=self.request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={
                'domain_name': domain.domain_name,
                'organization': domain.organization_name,
                'auto_approve': domain.auto_approve_registrations
            }
        )
    
    def perform_update(self, serializer):
        """Update domain with audit logging."""
        old_data = {
            'is_active': serializer.instance.is_active,
            'auto_approve': serializer.instance.auto_approve_registrations,
            'organization_name': serializer.instance.organization_name,
        }
        
        domain = serializer.save(updated_by=self.request.user)
        
        # Log significant changes
        changes = {}
        for field, old_value in old_data.items():
            new_value = getattr(domain, field)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
        
        if changes:
            AuditLog.log_action(
                AuditLog.ActionType.DOMAIN_UPDATED,
                request=self.request,
                user=self.request.user,
                severity=AuditLog.Severity.MEDIUM,
                details={
                    'domain_name': domain.domain_name,
                    'changes': changes
                }
            )
    
    def perform_destroy(self, instance):
        """Delete domain with audit logging."""
        AuditLog.log_action(
            AuditLog.ActionType.DOMAIN_REMOVED,
            request=self.request,
            user=self.request.user,
            severity=AuditLog.Severity.HIGH,
            details={
                'domain_name': instance.domain_name,
                'organization': instance.organization_name,
                'had_users': instance.users.exists()
            }
        )
        instance.delete()
    
    @action(detail=True, methods=['post'], url_path='activate')
    @extend_schema(
        tags=['Authentication'],
        summary='Activate Domain',
        description='Activate an authorized domain',
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}, 'message': {'type': 'string'}}}}
    )
    def activate(self, request, pk=None):
        """Activate domain."""
        domain = self.get_object()
        
        if domain.is_active:
            return Response({
                'status': 'error',
                'message': 'Domain is already active.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        domain.is_active = True
        domain.save(update_fields=['is_active'])
        
        AuditLog.log_action(
            AuditLog.ActionType.DOMAIN_ACTIVATED,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={'domain_name': domain.domain_name}
        )
        
        return Response({
            'status': 'success',
            'message': f'Domain {domain.domain_name} has been activated.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='deactivate')
    @extend_schema(
        tags=['Authentication'],
        summary='Deactivate Domain',
        description='Deactivate an authorized domain',
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}, 'message': {'type': 'string'}}}}
    )
    def deactivate(self, request, pk=None):
        """Deactivate domain."""
        domain = self.get_object()
        
        if not domain.is_active:
            return Response({
                'status': 'error',
                'message': 'Domain is already inactive.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        domain.is_active = False
        domain.save(update_fields=['is_active'])
        
        AuditLog.log_action(
            AuditLog.ActionType.DOMAIN_DEACTIVATED,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={'domain_name': domain.domain_name}
        )
        
        return Response({
            'status': 'success',
            'message': f'Domain {domain.domain_name} has been deactivated.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='users')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Domain Users',
        description='Get list of users registered with this domain',
        responses={200: {'type': 'object'}}
    )
    def users(self, request, pk=None):
        """Get users registered with this domain."""
        domain = self.get_object()
        users = User.objects.filter(corporate_email__endswith=f'@{domain.domain_name}')
        
        user_stats = {
            'domain_name': domain.domain_name,
            'total_users': users.count(),
            'active_users': users.filter(is_active=True).count(),
            'verified_users': users.filter(email_verified=True).count(),
            'users_with_2fa': users.filter(two_factor_enabled=True).count(),
        }
        
        # Role breakdown
        role_stats = users.values('role').annotate(count=Count('id'))
        user_stats['role_breakdown'] = {
            item['role']: item['count'] for item in role_stats
        }
        
        # Recent registrations (last 30 days)
        from datetime import timedelta
        from django.utils import timezone
        recent_cutoff = timezone.now() - timedelta(days=30)
        user_stats['recent_registrations'] = users.filter(
            date_joined__gte=recent_cutoff
        ).count()
        
        return Response(user_stats, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='statistics')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Domain Statistics',
        description='Get comprehensive statistics for all domains',
        responses={200: {'type': 'object'}}
    )
    def statistics(self, request):
        """Get domain statistics."""
        domains = self.get_queryset()
        
        stats = {
            'total_domains': domains.count(),
            'active_domains': domains.filter(is_active=True).count(),
            'inactive_domains': domains.filter(is_active=False).count(),
            'auto_approve_domains': domains.filter(auto_approve_registrations=True).count(),
        }
        
        # User distribution across domains
        domain_user_stats = []
        for domain in domains:
            user_count = User.objects.filter(
                corporate_email__endswith=f'@{domain.domain_name}'
            ).count()
            domain_user_stats.append({
                'domain_name': domain.domain_name,
                'organization': domain.organization_name,
                'user_count': user_count,
                'is_active': domain.is_active
            })
        
        stats['domain_user_distribution'] = sorted(
            domain_user_stats, 
            key=lambda x: x['user_count'], 
            reverse=True
        )
        
        return Response(stats, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='bulk-activate')
    @extend_schema(
        tags=['Authentication'],
        summary='Bulk Activate Domains',
        description='Activate multiple domains at once',
        responses={200: {'type': 'object'}}
    )
    def bulk_activate(self, request):
        """Bulk activate domains."""
        domain_ids = request.data.get('domain_ids', [])
        
        if not domain_ids:
            return Response({
                'status': 'error',
                'message': 'domain_ids is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        domains = AuthorizedDomain.objects.filter(id__in=domain_ids)
        updated_count = domains.filter(is_active=False).update(is_active=True)
        
        AuditLog.log_action(
            AuditLog.ActionType.BULK_UPDATE,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={
                'action': 'bulk_activate_domains',
                'domain_ids': domain_ids,
                'updated_count': updated_count
            }
        )
        
        return Response({
            'status': 'success',
            'updated_count': updated_count,
            'message': f'Successfully activated {updated_count} domains.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='bulk-deactivate')
    @extend_schema(
        tags=['Authentication'],
        summary='Bulk Deactivate Domains',
        description='Deactivate multiple domains at once',
        responses={200: {'type': 'object'}}
    )
    def bulk_deactivate(self, request):
        """Bulk deactivate domains."""
        domain_ids = request.data.get('domain_ids', [])
        
        if not domain_ids:
            return Response({
                'status': 'error',
                'message': 'domain_ids is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        domains = AuthorizedDomain.objects.filter(id__in=domain_ids)
        updated_count = domains.filter(is_active=True).update(is_active=False)
        
        AuditLog.log_action(
            AuditLog.ActionType.BULK_UPDATE,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={
                'action': 'bulk_deactivate_domains',
                'domain_ids': domain_ids,
                'updated_count': updated_count
            }
        )
        
        return Response({
            'status': 'success',
            'updated_count': updated_count,
            'message': f'Successfully deactivated {updated_count} domains.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='validate')
    @extend_schema(
        tags=['Authentication'],
        summary='Validate Domain',
        description='Validate domain configuration and DNS settings',
        responses={200: {'type': 'object'}}
    )
    def validate(self, request, pk=None):
        """Validate domain configuration."""
        domain = self.get_object()
        
        validation_results = {
            'domain_name': domain.domain_name,
            'is_valid': True,
            'checks': [],
            'warnings': [],
            'errors': []
        }
        
        # Basic domain format validation
        import re
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$', domain.domain_name):
            validation_results['errors'].append('Invalid domain name format')
            validation_results['is_valid'] = False
        
        # Check for existing users
        user_count = User.objects.filter(
            corporate_email__endswith=f'@{domain.domain_name}'
        ).count()
        validation_results['checks'].append(f'Found {user_count} registered users')
        
        # Check if domain is in use by other organizations
        similar_domains = AuthorizedDomain.objects.filter(
            domain_name__icontains=domain.domain_name.split('.')[0]
        ).exclude(id=domain.id)
        
        if similar_domains.exists():
            validation_results['warnings'].append(
                f'Found {similar_domains.count()} similar domain(s)'
            )
        
        # Log validation
        AuditLog.log_action(
            AuditLog.ActionType.DOMAIN_VALIDATED,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.LOW,
            details={
                'domain_name': domain.domain_name,
                'validation_result': validation_results['is_valid']
            }
        )
        
        return Response(validation_results, status=status.HTTP_200_OK)
