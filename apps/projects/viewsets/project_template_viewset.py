"""
ProjectTemplate ViewSet for project template management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from django.db.models import Q, Avg, Count

from ..models import ProjectTemplate
from ..serializers import (
    ProjectTemplateSerializer,
    ProjectTemplateCreateSerializer,
    ProjectTemplateListSerializer,
    ProjectTemplateUpdateSerializer,
    ProjectTemplateCloneSerializer,
    ProjectTemplateRatingSerializer,
    ProjectTemplateSearchSerializer,
    ProjectTemplateStatisticsSerializer
)


@extend_schema_view(
    list=extend_schema(
        summary="List project templates",
        description="Retrieve a list of project templates with filtering and pagination support.",
        tags=["Project Templates"],
        parameters=[
            OpenApiParameter("category", OpenApiTypes.STR, description="Filter by template category"),
            OpenApiParameter("template_type", OpenApiTypes.STR, description="Filter by template type"),
            OpenApiParameter("is_public", OpenApiTypes.BOOL, description="Filter by public/private templates"),
            OpenApiParameter("is_featured", OpenApiTypes.BOOL, description="Filter by featured templates"),
            OpenApiParameter("author", OpenApiTypes.INT, description="Filter by author user ID"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in template name and description"),
        ]
    ),
    create=extend_schema(
        summary="Create project template",
        description="Create a new project template.",
        tags=["Project Templates"]
    ),
    retrieve=extend_schema(
        summary="Get template details",
        description="Retrieve detailed information about a specific project template.",
        tags=["Project Templates"]
    ),
    update=extend_schema(
        summary="Update project template",
        description="Update project template configuration and content.",
        tags=["Project Templates"]
    ),
    partial_update=extend_schema(
        summary="Partially update project template",
        description="Partially update project template configuration.",
        tags=["Project Templates"]
    ),
    destroy=extend_schema(
        summary="Delete project template",
        description="Delete a project template (only for template authors).",
        tags=["Project Templates"]
    )
)
class ProjectTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project templates.
    
    Provides CRUD operations and template management functionality.
    """
    
    queryset = ProjectTemplate.objects.all()
    serializer_class = ProjectTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'template_type', 'is_public', 'is_featured', 'author']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'name', 'usage_count', 'rating_average', 'last_used_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == 'create':
            return ProjectTemplateCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectTemplateUpdateSerializer
        elif self.action == 'list':
            return ProjectTemplateListSerializer
        return ProjectTemplateSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if user.is_staff:
            return ProjectTemplate.objects.filter(is_deleted=False)
        
        # Users can see public templates and their own templates
        return ProjectTemplate.objects.filter(
            Q(is_public=True) | Q(author=user),
            is_deleted=False
        ).distinct()
    
    def perform_create(self, serializer):
        """Create template with current user as author."""
        serializer.save(author=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete template."""
        if instance.author != self.request.user and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to delete this template")
        
        instance.soft_delete()
    
    @extend_schema(
        summary="Clone project template",
        description="Create a copy of an existing template.",
        tags=["Project Templates"],
        request=ProjectTemplateCloneSerializer,
        responses={
            201: ProjectTemplateSerializer,
            400: {"description": "Invalid clone data"}
        }
    )
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing template."""
        source_template = self.get_object()
        
        if not source_template.is_accessible_by_user(request.user):
            return Response(
                {"error": "You don't have permission to clone this template"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ProjectTemplateCloneSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            clone_data = serializer.validated_data
            
            # Determine SpringBoot config
            if clone_data.get('customize_config') and clone_data.get('custom_springboot_config'):
                springboot_config = clone_data['custom_springboot_config']
            else:
                springboot_config = source_template.springboot_config.copy()
            
            cloned_template = ProjectTemplate.objects.create(
                name=clone_data['name'],
                description=clone_data.get('description', f"Cloned from: {source_template.name}"),
                category=source_template.category,
                template_type=source_template.template_type,
                is_public=clone_data['is_public'],
                author=request.user,
                springboot_config=springboot_config,
                uml_template_data=source_template.uml_template_data.copy() if source_template.uml_template_data else {},
                collaboration_settings=source_template.collaboration_settings.copy() if source_template.collaboration_settings else {},
                tags=source_template.tags.copy(),
                required_features=source_template.required_features.copy() if source_template.required_features else []
            )
            
            # Increment clone count on source template
            source_template.clone_count += 1
            source_template.save(update_fields=['clone_count'])
            
            response_serializer = self.get_serializer(cloned_template)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Rate project template",
        description="Rate and review a project template.",
        tags=["Project Templates"],
        request=ProjectTemplateRatingSerializer,
        responses={
            201: {"description": "Rating submitted successfully"},
            400: {"description": "Invalid rating data"}
        }
    )
    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        """Rate a project template."""
        template = self.get_object()
        
        serializer = ProjectTemplateRatingSerializer(
            data=request.data,
            context={'template': template, 'request': request}
        )
        
        if serializer.is_valid():
            rating = serializer.validated_data['rating']
            comment = serializer.validated_data.get('comment', '')
            
            # Create or update rating (implement TemplateRating model if needed)
            # For now, update template rating statistics directly
            
            # Simple rating calculation (in real implementation, use separate Rating model)
            current_total = template.rating_average * template.rating_count
            new_total = current_total + rating
            template.rating_count += 1
            template.rating_average = new_total / template.rating_count
            template.save(update_fields=['rating_average', 'rating_count'])
            
            return Response({
                "message": "Rating submitted successfully",
                "rating": rating,
                "new_average": template.rating_average,
                "total_ratings": template.rating_count
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Search project templates",
        description="Advanced search for project templates with multiple criteria.",
        tags=["Project Templates"],
        request=ProjectTemplateSearchSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "total_count": {"type": "integer"},
                    "search_metadata": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Advanced template search."""
        serializer = ProjectTemplateSearchSerializer(data=request.data)
        
        if serializer.is_valid():
            search_params = serializer.validated_data
            
            queryset = self.get_queryset()
            
            # Apply search filters
            if search_params.get('query'):
                query = search_params['query']
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(tags__icontains=query)
                )
            
            if search_params.get('category'):
                queryset = queryset.filter(category=search_params['category'])
            
            if search_params.get('template_type'):
                queryset = queryset.filter(template_type=search_params['template_type'])
            
            if search_params.get('tags'):
                for tag in search_params['tags']:
                    queryset = queryset.filter(tags__icontains=tag)
            
            if search_params.get('java_version'):
                queryset = queryset.filter(
                    springboot_config__java_version=search_params['java_version']
                )
            
            if search_params.get('springboot_version'):
                queryset = queryset.filter(
                    springboot_config__springboot_version=search_params['springboot_version']
                )
            
            if search_params.get('is_public') is not None:
                queryset = queryset.filter(is_public=search_params['is_public'])
            
            if search_params.get('min_rating'):
                queryset = queryset.filter(rating_average__gte=search_params['min_rating'])
            
            # Apply sorting
            sort_by = search_params.get('sort_by', 'created_at')
            sort_order = search_params.get('sort_order', 'desc')
            
            if sort_order == 'desc':
                sort_by = f'-{sort_by}'
            
            queryset = queryset.order_by(sort_by)
            
            # Paginate results
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = ProjectTemplateListSerializer(page, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            
            serializer = ProjectTemplateListSerializer(queryset, many=True, context={'request': request})
            
            return Response({
                "results": serializer.data,
                "total_count": queryset.count(),
                "search_metadata": {
                    "query": search_params.get('query', ''),
                    "filters_applied": len([k for k, v in search_params.items() if v]),
                    "sort_by": sort_by,
                    "timestamp": timezone.now().isoformat()
                }
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get featured templates",
        description="Get list of featured project templates.",
        tags=["Project Templates"],
        parameters=[
            OpenApiParameter("limit", OpenApiTypes.INT, description="Number of templates to return (default: 10)"),
        ],
        responses={
            200: {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ProjectTemplateList"}
            }
        }
    )
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured templates."""
        limit = int(request.query_params.get('limit', 10))
        
        featured_templates = self.get_queryset().filter(
            is_featured=True,
            is_public=True
        ).order_by('-rating_average', '-usage_count')[:limit]
        
        serializer = ProjectTemplateListSerializer(
            featured_templates, many=True, context={'request': request}
        )
        
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get popular templates",
        description="Get list of most popular project templates.",
        tags=["Project Templates"],
        parameters=[
            OpenApiParameter("limit", OpenApiTypes.INT, description="Number of templates to return (default: 10)"),
            OpenApiParameter("period", OpenApiTypes.STR, description="Time period: 'week', 'month', 'all' (default: 'month')"),
        ],
        responses={
            200: {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ProjectTemplateList"}
            }
        }
    )
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular templates based on usage."""
        limit = int(request.query_params.get('limit', 10))
        period = request.query_params.get('period', 'month')
        
        queryset = self.get_queryset().filter(is_public=True)
        
        # Filter by period if needed
        if period != 'all':
            if period == 'week':
                date_threshold = timezone.now() - timezone.timedelta(weeks=1)
            else:  # month
                date_threshold = timezone.now() - timezone.timedelta(days=30)
            
            queryset = queryset.filter(last_used_at__gte=date_threshold)
        
        popular_templates = queryset.order_by(
            '-usage_count', '-rating_average'
        )[:limit]
        
        serializer = ProjectTemplateListSerializer(
            popular_templates, many=True, context={'request': request}
        )
        
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get template statistics",
        description="Get comprehensive statistics for project templates.",
        tags=["Project Templates"],
        request=ProjectTemplateStatisticsSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "overview": {"type": "object"},
                    "category_distribution": {"type": "object"},
                    "usage_trends": {"type": "object"},
                    "rating_statistics": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def statistics(self, request):
        """Get template statistics."""
        serializer = ProjectTemplateStatisticsSerializer(data=request.data)
        
        if serializer.is_valid():
            period = serializer.validated_data['period']
            include_usage = serializer.validated_data['include_usage']
            include_ratings = serializer.validated_data['include_ratings']
            include_clones = serializer.validated_data['include_clones']
            
            queryset = self.get_queryset()
            
            stats = {
                "overview": {
                    "total_templates": queryset.count(),
                    "public_templates": queryset.filter(is_public=True).count(),
                    "featured_templates": queryset.filter(is_featured=True).count(),
                    "user_templates": queryset.filter(author=request.user).count() if not request.user.is_staff else None
                }
            }
            
            # Category distribution
            category_stats = queryset.values('category').annotate(count=Count('id'))
            stats["category_distribution"] = {
                item['category']: item['count'] for item in category_stats
            }
            
            if include_usage:
                # Usage statistics
                total_usage = queryset.aggregate(total=models.Sum('usage_count'))['total'] or 0
                avg_usage = queryset.aggregate(avg=Avg('usage_count'))['avg'] or 0
                
                stats["usage_statistics"] = {
                    "total_usage": total_usage,
                    "average_usage": round(avg_usage, 2),
                    "most_used": queryset.order_by('-usage_count').first().name if queryset.exists() else None
                }
            
            if include_ratings:
                # Rating statistics
                rated_templates = queryset.filter(rating_count__gt=0)
                avg_rating = rated_templates.aggregate(avg=Avg('rating_average'))['avg'] or 0
                
                stats["rating_statistics"] = {
                    "templates_with_ratings": rated_templates.count(),
                    "average_rating": round(avg_rating, 2),
                    "highest_rated": rated_templates.order_by('-rating_average').first().name if rated_templates.exists() else None
                }
            
            if include_clones:
                # Clone statistics
                total_clones = queryset.aggregate(total=models.Sum('clone_count'))['total'] or 0
                
                stats["clone_statistics"] = {
                    "total_clones": total_clones,
                    "most_cloned": queryset.order_by('-clone_count').first().name if queryset.exists() else None
                }
            
            return Response(stats)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Use template",
        description="Mark template as used and increment usage count.",
        tags=["Project Templates"],
        responses={
            200: {"description": "Template usage recorded"},
            403: {"description": "Template not accessible"}
        }
    )
    @action(detail=True, methods=['post'])
    def use_template(self, request, pk=None):
        """Mark template as used."""
        template = self.get_object()
        
        if not template.is_accessible_by_user(request.user):
            return Response(
                {"error": "You don't have access to use this template"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Increment usage count
        template.increment_usage()
        
        return Response({
            "message": "Template usage recorded",
            "usage_count": template.usage_count,
            "last_used_at": template.last_used_at.isoformat()
        })
    
    @extend_schema(
        summary="Get template categories",
        description="Get list of available template categories with counts.",
        tags=["Project Templates"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "categories": {"type": "array"},
                    "total_categories": {"type": "integer"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get template categories with counts."""
        categories = self.get_queryset().values('category').annotate(
            count=Count('id'),
            avg_rating=Avg('rating_average')
        ).order_by('category')
        
        category_data = []
        for cat in categories:
            category_data.append({
                "category": cat['category'],
                "display_name": dict(ProjectTemplate.CATEGORY_CHOICES).get(cat['category'], cat['category']),
                "count": cat['count'],
                "average_rating": round(cat['avg_rating'] or 0, 2)
            })
        
        return Response({
            "categories": category_data,
            "total_categories": len(category_data)
        })
    
    @extend_schema(
        summary="Validate template",
        description="Validate template configuration and structure.",
        tags=["Project Templates"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "validation_errors": {"type": "array"},
                    "warnings": {"type": "array"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def validate(self, request, pk=None):
        """Validate template configuration."""
        template = self.get_object()
        
        validation_result = {
            "is_valid": True,
            "validation_errors": [],
            "warnings": []
        }
        
        try:
            template.validate_template()
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append(str(e))
        
        # Additional validation checks
        if not template.springboot_config:
            validation_result["warnings"].append("No SpringBoot configuration provided")
        
        if not template.uml_template_data:
            validation_result["warnings"].append("No UML template data provided")
        
        if not template.tags:
            validation_result["warnings"].append("No tags specified for discoverability")
        
        return Response(validation_result)
