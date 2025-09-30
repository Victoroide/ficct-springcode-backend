"""
Enterprise Transaction Management Mixins for ViewSets.

Professional-grade transaction management with atomic operations,
comprehensive error handling, and audit logging.
"""

import json
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import APIException, ValidationError
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

            resource_type = None
            resource_id = None
            
            if instance:
                resource_type = instance.__class__.__name__
                resource_id = getattr(instance, 'id', None) or getattr(instance, 'pk', None)

            audit_details = details or {}

            AuditService.log_user_action(
                user=self.request.user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=self.get_client_ip(self.request),
                details=audit_details
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

            instance = serializer.save()

            self.log_transaction_event(
                "CREATE_SUCCESS",
                instance=instance,
                details={'fields': list(request.data.keys())}
            )
            
            response_serializer = self.get_serializer(instance)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        except (ValidationError, DjangoValidationError) as e:
            logger.error(f"Validation error in {self.__class__.__name__} create: {str(e)}")
            self.log_transaction_event(
                "CREATE_VALIDATION_ERROR",
                details={'validation_errors': str(e)}
            )
            return Response(
                {'error': 'Validation failed', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid request data in {self.__class__.__name__} create: {str(e)}")
            self.log_transaction_event(
                "CREATE_BAD_REQUEST",
                details={'error': str(e)}
            )
            return Response(
                {'error': 'Invalid request data', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__} create: {str(e)}")
            self.log_transaction_event(
                "CREATE_ERROR",
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

            updated_instance = serializer.save()

            self.log_transaction_event(
                "UPDATE_SUCCESS",
                instance=updated_instance,
                details={
                    'updated_fields': list(request.data.keys()),
                    'original_values': original_values,
                    'partial': partial
                }
            )
            
            response_serializer = self.get_serializer(updated_instance)
            return Response(response_serializer.data)
            
        except (ValidationError, DjangoValidationError) as e:
            logger.error(f"Validation error in {self.__class__.__name__} update: {str(e)}")
            self.log_transaction_event(
                "UPDATE_VALIDATION_ERROR",
                instance=instance,
                details={'error': str(e), 'data': request.data}
            )
            return Response(
                {'error': 'Validation failed', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid request data in {self.__class__.__name__} update: {str(e)}")
            self.log_transaction_event(
                "UPDATE_BAD_REQUEST",
                instance=instance,
                details={'error': str(e)}
            )
            return Response(
                {'error': 'Invalid request data', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__} update: {str(e)}")
            self.log_transaction_event(
                "UPDATE_ERROR",
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

            if hasattr(instance, self.soft_delete_field):
                current_status = getattr(instance, self.soft_delete_field)
                if current_status == self.soft_delete_value:
                    return Response(
                        {'error': 'Resource is already deleted'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if hasattr(instance, self.soft_delete_field):
                setattr(instance, self.soft_delete_field, self.soft_delete_value)

            if hasattr(instance, 'deleted_at'):
                instance.deleted_at = timezone.now()

            if hasattr(instance, 'deleted_by'):
                instance.deleted_by = request.user
            
            instance.save()

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

        if getattr(self, 'swagger_fake_view', False):
            return queryset.none()

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

        if hasattr(serializer.Meta.model, 'created_by'):
            save_kwargs['created_by'] = self.request.user

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

        if hasattr(serializer.Meta.model, 'updated_by'):
            save_kwargs['updated_by'] = self.request.user

        if hasattr(serializer.Meta.model, 'updated_at'):
            save_kwargs['updated_at'] = timezone.now()
        
        return serializer.save(**save_kwargs)
