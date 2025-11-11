"""
Tests for bilingual incremental command processor.

Tests all 9 command types in both English and Spanish (18 tests total).
"""

import pytest
from apps.ai_assistant.services import IncrementalCommandProcessor


@pytest.fixture
def processor():
    """Create command processor instance."""
    return IncrementalCommandProcessor()


@pytest.fixture
def sample_diagram():
    """Sample diagram with User and Order classes."""
    return {
        "nodes": [
            {
                "id": "user-123",
                "data": {
                    "label": "User",
                    "attributes": [
                        {"id": "attr-1", "name": "id", "type": "Long", "visibility": "private"},
                        {"id": "attr-2", "name": "password", "type": "String", "visibility": "private"},
                        {"id": "attr-3", "name": "age", "type": "Integer", "visibility": "private"},
                    ],
                    "methods": [
                        {"id": "method-1", "name": "save", "returnType": "void", "visibility": "public"},
                        {"id": "method-2", "name": "delete", "returnType": "void", "visibility": "public"},
                    ],
                },
            },
            {
                "id": "order-456",
                "data": {
                    "label": "Order",
                    "attributes": [],
                    "methods": [],
                },
            },
        ],
        "edges": [],
    }


class TestAddAttribute:
    """Test add attribute command (English and Spanish)."""
    
    def test_add_attribute_english(self, processor, sample_diagram):
        command = "add attribute email (String) to class User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert "email" in result["description"]
        assert result["changes"]["data.attributes"]["operation"] == "append"
    
    def test_add_attribute_spanish(self, processor, sample_diagram):
        command = "agregar atributo email (String) a clase User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert "email" in result["description"]


class TestRemoveAttribute:
    """Test remove attribute command (English and Spanish)."""
    
    def test_remove_attribute_english(self, processor, sample_diagram):
        command = "remove attribute password from class User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.attributes"]["operation"] == "remove"
        assert result["changes"]["data.attributes"]["filter"]["name"] == "password"
    
    def test_remove_attribute_spanish(self, processor, sample_diagram):
        command = "eliminar atributo password de clase User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert "password" in result["description"]


class TestChangeAttribute:
    """Test change attribute command (English and Spanish)."""
    
    def test_change_attribute_english(self, processor, sample_diagram):
        command = "change attribute age in class User to birthDate (Date)"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.attributes"]["operation"] == "update"
        assert result["changes"]["data.attributes"]["value"]["name"] == "birthDate"
        assert result["changes"]["data.attributes"]["value"]["type"] == "Date"
    
    def test_change_attribute_spanish(self, processor, sample_diagram):
        command = "cambiar atributo age en clase User a birthDate (Date)"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert "birthDate" in result["description"]


class TestAddMethod:
    """Test add method command (English and Spanish)."""
    
    def test_add_method_english(self, processor, sample_diagram):
        command = "add method login() returning void to class User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.methods"]["operation"] == "append"
        assert result["changes"]["data.methods"]["value"]["name"] == "login"
        assert result["changes"]["data.methods"]["value"]["returnType"] == "void"
    
    def test_add_method_spanish(self, processor, sample_diagram):
        command = "agregar método login() retornando void a clase User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert "login" in result["description"]


class TestRemoveMethod:
    """Test remove method command (English and Spanish)."""
    
    def test_remove_method_english(self, processor, sample_diagram):
        command = "remove method delete from class User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.methods"]["operation"] == "remove"
        assert result["changes"]["data.methods"]["filter"]["name"] == "delete"
    
    def test_remove_method_spanish(self, processor, sample_diagram):
        command = "eliminar método delete de clase User"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"


class TestAddRelationship:
    """Test add relationship command (English and Spanish)."""
    
    def test_add_relationship_english(self, processor, sample_diagram):
        command = "add association from User to Order with multiplicity 1..*"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "add_edge"
        assert result["changes"]["edge"]["operation"] == "create"
        assert result["changes"]["edge"]["value"]["data"]["relationshipType"] == "ASSOCIATION"
    
    def test_add_relationship_spanish(self, processor, sample_diagram):
        command = "agregar asociación de User a Order con multiplicidad 1..*"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "add_edge"


class TestRemoveRelationship:
    """Test remove relationship command (English and Spanish)."""
    
    def test_remove_relationship_english(self, processor, sample_diagram):
        diagram_with_edge = sample_diagram.copy()
        diagram_with_edge["edges"] = [
            {"id": "edge-1", "source": "user-123", "target": "order-456"}
        ]
        
        command = "remove relationship between User and Order"
        result = processor.process_command(command, "test-diagram", diagram_with_edge)
        
        assert result["action"] == "delete_edge"
        assert result["changes"]["edge"]["operation"] == "delete"
    
    def test_remove_relationship_spanish(self, processor, sample_diagram):
        diagram_with_edge = sample_diagram.copy()
        diagram_with_edge["edges"] = [
            {"id": "edge-1", "source": "user-123", "target": "order-456"}
        ]
        
        command = "eliminar relación entre User y Order"
        result = processor.process_command(command, "test-diagram", diagram_with_edge)
        
        assert result["action"] == "delete_edge"


class TestRenameClass:
    """Test rename class command (English and Spanish)."""
    
    def test_rename_class_english(self, processor, sample_diagram):
        command = "rename class User to Customer"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.label"]["operation"] == "replace"
        assert result["changes"]["data.label"]["value"] == "Customer"
    
    def test_rename_class_spanish(self, processor, sample_diagram):
        command = "renombrar clase User a Customer"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert "Customer" in result["description"]


class TestChangeVisibility:
    """Test change visibility command (English and Spanish)."""
    
    def test_change_visibility_english(self, processor, sample_diagram):
        command = "change visibility of id in class User to public"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert result["node_id"] == "user-123"
        assert result["changes"]["data.attributes"]["operation"] == "update"
        assert result["changes"]["data.attributes"]["value"]["visibility"] == "public"
    
    def test_change_visibility_spanish(self, processor, sample_diagram):
        command = "cambiar visibilidad de id en clase User a público"
        result = processor.process_command(command, "test-diagram", sample_diagram)
        
        assert result["action"] == "update_node"
        assert "public" in str(result["changes"])
