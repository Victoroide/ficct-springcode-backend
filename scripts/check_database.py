
"""
Script for checking database persistence issues in UML diagrams.
"""

import os
import sys
import logging
import django
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('database_check.log')
    ]
)
logger = logging.getLogger(__name__)

def check_diagram_table():
    """Check the UML diagram table structure and content."""
    from django.db import connection
    
    logger.info("🔍 Checking UML Diagram table...")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"📋 Database tables found: {len(tables)}")
        for table in tables:
            logger.info(f"  - {table}")

        diagram_tables = [t for t in tables if 'diagram' in t.lower()]
        logger.info(f"🖼️ Diagram-related tables found: {len(diagram_tables)}")
        for table in diagram_tables:
            logger.info(f"  - {table}")

            logger.info(f"📊 Checking structure of {table}...")
            cursor.execute(f"""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]}" + (f"({col[2]})" if col[2] else ""))

            logger.info(f"📝 Checking data in {table}...")
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            logger.info(f"  - Row count: {row_count}")
            
            if row_count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 10")
                sample_data = cursor.fetchall()
                for i, row in enumerate(sample_data):
                    logger.info(f"  - Row {i+1}: {str(row)[:100]}...")
            else:
                logger.warning(f"⚠️ Table {table} is empty!")

def check_uml_diagram_model():
    """Check the UML diagram model using Django ORM."""
    from apps.uml_diagrams.models import UMLDiagram
    
    logger.info("📊 Checking UML Diagram model using Django ORM...")

    diagram_count = UMLDiagram.objects.count()
    logger.info(f"📈 Total diagrams in database: {diagram_count}")

    recent_diagrams = UMLDiagram.objects.order_by('-created_at')[:5]
    logger.info(f"🕒 Recent diagrams: {len(recent_diagrams)}")
    
    for diagram in recent_diagrams:
        logger.info(f"  - ID: {diagram.id}")
        logger.info(f"    Title: {diagram.title}")
        logger.info(f"    Type: {diagram.diagram_type}")
        logger.info(f"    Created: {diagram.created_at}")
        logger.info(f"    Modified: {diagram.last_modified}")
        logger.info(f"    Session: {diagram.session_id}")
        logger.info(f"    Content Type: {type(diagram.content)}")
        logger.info(f"    Content Length: {len(str(diagram.content))}")

def test_diagram_creation():
    """Test creating a new diagram and verifying persistence."""
    from apps.uml_diagrams.models import UMLDiagram
    import uuid
    
    logger.info("🔧 Testing diagram creation and persistence...")

    test_id = uuid.uuid4()
    test_title = f"Test Diagram {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_content = {
        "classes": [
            {"id": "class1", "name": "TestClass", "attributes": ["attr1", "attr2"]}
        ],
        "relationships": []
    }

    try:
        diagram = UMLDiagram.objects.create(
            id=test_id,
            title=test_title,
            diagram_type='CLASS',
            content=test_content,
            session_id=str(uuid.uuid4()),
            active_sessions=[]
        )
        logger.info(f"✅ Created test diagram with ID: {diagram.id}")

        retrieved = UMLDiagram.objects.filter(id=test_id).first()
        if retrieved:
            logger.info(f"✅ Successfully retrieved diagram with ID: {retrieved.id}")
            logger.info(f"  - Title: {retrieved.title}")
            logger.info(f"  - Content matches: {retrieved.content == test_content}")
        else:
            logger.error(f"❌ Failed to retrieve created diagram with ID: {test_id}")
    
    except Exception as e:
        logger.error(f"❌ Failed to create test diagram: {str(e)}")

def main():
    """Run all database checks."""
    logger.info("🔎 Starting database persistence check...")
    
    try:
        check_diagram_table()
        check_uml_diagram_model()
        test_diagram_creation()
        
        logger.info("✅ Database check completed successfully!")
    
    except Exception as e:
        logger.error(f"❌ Database check failed: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
