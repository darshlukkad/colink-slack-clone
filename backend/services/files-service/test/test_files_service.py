import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime
import io
import sys
import os

# Add files-service directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from dependencies import get_db, get_current_user
from shared.database.models import User, UserStatus, UserRole

# Mock User
MOCK_USER_ID = uuid4()
MOCK_USER = User(
    id=MOCK_USER_ID,
    keycloak_id="test-keycloak-id",
    email="test@example.com",
    username="testuser",
    status=UserStatus.ACTIVE,
    role=UserRole.MEMBER
)

# Mock File Record
def create_mock_file_record(file_id=None, user_id=None):
    return MagicMock(
        id=file_id or uuid4(),
        filename="test_image.jpg",
        original_filename="test_image.jpg",
        storage_key="test_key",
        url="http://minio/test_image.jpg",
        thumbnail_url="http://minio/thumb_test_image.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        uploaded_by_id=user_id or MOCK_USER_ID,
        channel_id=None,
        message_id=None,
        scan_status="clean",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_file_manager():
    with patch("routers.files.file_manager") as mock:
        yield mock

@pytest.fixture
def mock_minio_service():
    with patch("routers.files.minio_service") as mock:
        yield mock

@pytest.fixture
def mock_kafka_producer():
    with patch("main.kafka_producer") as mock:
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        yield mock

@pytest.fixture
def mock_minio_startup():
    with patch("main.minio_service") as mock:
        mock.initialize_buckets = MagicMock()
        yield mock

@pytest.fixture
def client(mock_db, mock_kafka_producer, mock_minio_startup):
    async def override_get_db():
        yield mock_db

    async def override_get_current_user():
        return MOCK_USER

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()

# ============================================================================
# Positive Tests
# ============================================================================

def test_upload_file_success(client, mock_file_manager):
    # Setup
    mock_file = create_mock_file_record()
    mock_file_manager.upload_file = AsyncMock(return_value=mock_file)
    mock_file_manager.classify_file.return_value = (True, False, False)

    # Execute
    files = {'file': ('test_image.jpg', b'fake content', 'image/jpeg')}
    response = client.post("/api/v1/files/upload", files=files)

    # Verify
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test_image.jpg"
    assert data["is_image"] is True
    assert data["uploaded_by"] == str(MOCK_USER_ID)

def test_get_file_success(client, mock_file_manager):
    # Setup
    file_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id)
    mock_uploader = MagicMock(username="testuser")
    mock_file_manager.get_file_with_uploader = AsyncMock(return_value=(mock_file, mock_uploader))
    mock_file_manager.classify_file.return_value = (True, False, False)

    # Execute
    response = client.get(f"/api/v1/files/{file_id}")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(file_id)
    assert data["uploader_username"] == "testuser"

def test_download_file_success(client, mock_file_manager, mock_minio_service):
    # Setup
    file_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id)
    mock_file_manager.get_file = AsyncMock(return_value=mock_file)
    mock_minio_service.download_file.return_value = b"file content"

    # Execute
    response = client.get(f"/api/v1/files/{file_id}/download")

    # Verify
    assert response.status_code == 200
    assert response.content == b"file content"
    assert response.headers["content-type"] == "image/jpeg"

def test_delete_file_success(client, mock_file_manager):
    # Setup
    file_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id, user_id=MOCK_USER_ID)
    mock_file_manager.get_file = AsyncMock(return_value=mock_file)
    mock_file_manager.delete_file = AsyncMock(return_value=True)

    # Execute
    response = client.delete(f"/api/v1/files/{file_id}")

    # Verify
    assert response.status_code == 204

def test_list_files_success(client, mock_file_manager):
    # Setup
    mock_file = create_mock_file_record()
    mock_uploader = MagicMock(username="testuser")
    mock_file_manager.list_files = AsyncMock(return_value=([(mock_file, mock_uploader)], 1))
    mock_file_manager.classify_file.return_value = (True, False, False)

    # Execute
    response = client.get("/api/v1/files")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 1
    assert data["total_count"] == 1

def test_generate_signed_url_success(client, mock_file_manager, mock_minio_service):
    # Setup
    file_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id)
    mock_file_manager.get_file = AsyncMock(return_value=mock_file)
    mock_minio_service.generate_presigned_url.return_value = "http://signed-url"

    # Execute
    response = client.post(
        f"/api/v1/files/{file_id}/signed-url",
        json={"expiry_seconds": 3600}
    )

    # Verify
    assert response.status_code == 200
    assert response.json()["url"] == "http://signed-url"

# ============================================================================
# Negative Tests
# ============================================================================

def test_upload_file_invalid_request(client):
    # Execute - Missing file
    response = client.post("/api/v1/files/upload")
    
    # Verify
    assert response.status_code == 422  # Validation error

def test_get_file_not_found(client, mock_file_manager):
    # Setup
    mock_file_manager.get_file_with_uploader = AsyncMock(return_value=None)
    
    # Execute
    response = client.get(f"/api/v1/files/{uuid4()}")
    
    # Verify
    assert response.status_code == 404

def test_download_file_not_found(client, mock_file_manager):
    # Setup
    mock_file_manager.get_file = AsyncMock(return_value=None)
    
    # Execute
    response = client.get(f"/api/v1/files/{uuid4()}/download")
    
    # Verify
    assert response.status_code == 404

def test_delete_file_forbidden(client, mock_file_manager):
    # Setup
    file_id = uuid4()
    other_user_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id, user_id=other_user_id)
    mock_file_manager.get_file = AsyncMock(return_value=mock_file)
    
    # Execute
    response = client.delete(f"/api/v1/files/{file_id}")
    
    # Verify
    assert response.status_code == 403

def test_delete_file_failure(client, mock_file_manager):
    # Setup
    file_id = uuid4()
    mock_file = create_mock_file_record(file_id=file_id, user_id=MOCK_USER_ID)
    mock_file_manager.get_file = AsyncMock(return_value=mock_file)
    mock_file_manager.delete_file = AsyncMock(return_value=False)
    
    # Execute
    response = client.delete(f"/api/v1/files/{file_id}")
    
    # Verify
    assert response.status_code == 500

def test_generate_signed_url_not_found(client, mock_file_manager):
    # Setup
    mock_file_manager.get_file = AsyncMock(return_value=None)
    
    # Execute
    response = client.post(
        f"/api/v1/files/{uuid4()}/signed-url",
        json={"expiry_seconds": 3600}
    )
    
    # Verify
    assert response.status_code == 404
