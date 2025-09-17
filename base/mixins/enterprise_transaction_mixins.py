"""
Enterprise Transaction Management Mixins for ViewSets.

Professional-grade transaction management with atomic operations,
comprehensive error handling, and audit logging.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from apps.audit.services import AuditService
import logging

logger = logging.getLogger('enterprise_transactions')


class EnterpriseTransactionMixin:
    """
    Enterprise-grade transaction management mixin.
    
    Provides atomic transaction decorators with comprehensive error handling,
    audit logging, and consistent response formatting.
    """
    
    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or '127.0.0.1'
    
    def log_transaction_event(self, action, instance=None, details=None):
        """Log transaction events for audit purposes."""
        try:
            audit_service = AuditService()
            audit_service.log_user_action(
                user=self.request.user,
                action=action,
                ip_address=self.get_client_ip(self.request),
                details=details or {},
                resource=instance
            )
        except Exception as e:
            logger.warning(f"Failed to log transaction event: {str(e)}")
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Enterprise create operation with atomic transaction.
        
        Includes validation, audit logging, and comprehensive error handling.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Perform create operation
            instance = serializer.save()
            
            # Log successful creation
            self.log_transaction_event(
                f"{self.__class__.__name__}_CREATE_SUCCESS",
                instance=instance,
                details={'fields': list(request.data.keys())}
            )
            
            response_serializer = self.get_serializer(instance)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except ValidationError as e:
            logger.error(f"Validation error in {self.__class__.__name__} create: {str(e)}")
            self.log_transaction_event(
                f"{self.__class__.__name__}_CREATE_VALIDATION_ERROR",
                details={'error': str(e), 'data': request.data}
            )
            return Response(
                {'error': 'Validation failed', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__} create: {str(e)}")
            self.log_transaction_event(
                f"{self.__class__.__name__}_CREATE_ERROR",
                details={'error': str(e)}
            )
            return Response(
                {'error': 'Internal server error during creation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Enterprise update operation with atomic transaction.
        
        Supports both PUT and PATCH operations with comprehensive validation.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        try:
            # Store original values for audit
            original_values = {}
            for field in request.data.keys():
                if hasattr(instance, field):
                    original_values[field] = getattr(instance, field)
            
            serializer = self.get_serializer(
                instance, 
                data=request.data, 
                partial=partial
            )
            serializer.is_valid(raise_exception=True)
            
            # Perform update operation
            updated_instance = serializer.save()
            
            # Log successful update
            self.log_transaction_event(
                f"{self.__class__.__name__}_UPDATE_SUCCESS",
                instance=updated_instance,
                details={
                    'updated_fields': list(request.data.keys()),
                    'original_values': original_values,
                    'partial': partial
                }
            )
            
            response_serializer = self.get_serializer(updated_instance)
            return Response(response_serializer.data)
            
        except ValidationError as e:
            logger.error(f"Validation error in {self.__class__.__name__} update: {str(e)}")
            self.log_transaction_event(
                f"{self.__class__.__name__}_UPDATE_VALIDATION_ERROR",
                instance=instance,
                details={'error': str(e), 'data': request.data}
            )
            return Response(
                {'error': 'Validation failed', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__} update: {str(e)}")
            self.log_transaction_event(
                f"{self.__class__.__name__}_UPDATE_ERROR",
                instance=instance,
                details={'error': str(e)}
            )
            return Response(
                {'error': 'Internal server error during update'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnterpriseSoftDeleteMixin:
    """
    Enterprise soft delete implementation.
    
    Provides standardized soft delete functionality with audit logging
    and status field management.
    """
    
    soft_delete_field = 'status'  # Override in subclasses if different
    soft_delete_value = 'DELETED'  # Override in subclasses if different
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Enterprise soft delete operation.
        
        Marks resource as deleted instead of permanent removal,
        with comprehensive audit logging.
        """
        instance = self.get_object()
        
        try:
            # Check if already soft deleted
            if hasattr(instance, self.soft_delete_field):
                current_status = getattr(instance, self.soft_delete_field)
                if current_status == self.soft_delete_value:
                    return Response(
                        {'error': 'Resource is already deleted'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Perform soft delete
            if hasattr(instance, self.soft_delete_field):
                setattr(instance, self.soft_delete_field, self.soft_delete_value)
            
            # Set deletion timestamp if field exists
            if hasattr(instance, 'deleted_at'):
                instance.deleted_at = timezone.now()
            
            # Set deleted_by if field exists
            if hasattr(instance, 'deleted_by'):
                instance.deleted_by = request.user
            
            instance.save()
            
            # Log successful deletion
            audit_service = AuditService()
            audit_service.log_user_action(
                user=request.user,
                action=f"{self.__class__.__name__}_SOFT_DELETE_SUCCESS",
                ip_address=self.get_client_ip(request),
                details={
                    'resource_id': str(instance.pk),
                    'soft_delete_field': self.soft_delete_field,
                    'delete_value': self.soft_delete_value
                },
                resource=instance
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__} soft delete: {str(e)}")
            
            # Log deletion error
            try:
                audit_service = AuditService()
                audit_service.log_user_action(
                    user=request.user,
                    action=f"{self.__class__.__name__}_SOFT_DELETE_ERROR",
                    ip_address=self.get_client_ip(request),
                    details={'error': str(e), 'resource_id': str(instance.pk)},
                    resource=instance
                )
            except:
                pass
            
            return Response(
                {'error': 'Failed to delete resource'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or '127.0.0.1'


class EnterpriseViewSetMixin(EnterpriseTransactionMixin, EnterpriseSoftDeleteMixin):
    """
    Comprehensive enterprise ViewSet mixin.
    
    Combines transaction management, soft delete, and additional
    enterprise-grade features for production-ready ViewSets.
    """
    
    def get_queryset(self):
        """
        Enterprise queryset with automatic soft delete filtering.
        
        Excludes soft-deleted records by default unless explicitly included.
        """
        queryset = super().get_queryset()
        
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return queryset.none()
        
        # Filter out soft-deleted records by default
        if hasattr(queryset.model, self.soft_delete_field):
            exclude_filter = {self.soft_delete_field: self.soft_delete_value}
            queryset = queryset.exclude(**exclude_filter)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Enterprise create performance with user assignment.
        
        Automatically assigns current user to created_by field if available.
        """
        save_kwargs = {}
        
        # Set created_by if field exists
        if hasattr(serializer.Meta.model, 'created_by'):
            save_kwargs['created_by'] = self.request.user
        
        # Set owner if field exists and not provided
        if (hasattr(serializer.Meta.model, 'owner') and 
            'owner' not in serializer.validated_data):
            save_kwargs['owner'] = self.request.user
        
        return serializer.save(**save_kwargs)
    
    def perform_update(self, serializer):
        """
        Enterprise update performance with user tracking.
        
        Automatically tracks last modified user and timestamp.
        """
        save_kwargs = {}
        
        # Set updated_by if field exists
        if hasattr(serializer.Meta.model, 'updated_by'):
            save_kwargs['updated_by'] = self.request.user
        
        # Set updated_at if field exists (though Django should handle this)
        if hasattr(serializer.Meta.model, 'updated_at'):
            save_kwargs['updated_at'] = timezone.now()
        
        return serializer.save(**save_kwargs)
