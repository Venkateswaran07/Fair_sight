import io
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_demographics_audit_valid_csv():
    # A simple synthetic CSV with a protected column 'gender'
    csv_content = (
        "gender,income,prediction\n"
        "male,50000,1\n"
        "female,60000,0\n"
        "male,40000,0\n"
    ).encode("utf-8")

    response = client.post(
        "/audit/demographics",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        data={"protected_columns": '["gender"]'},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["num_rows"] == 3
    assert data["columns_analyzed"] == ["gender"]
    assert "gender" in data["results"]

def test_invalid_csv_rejected():
    # Not a CSV
    response = client.post(
        "/audit/demographics",
        files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
        data={"protected_columns": '["gender"]'},
    )
    
    # 400 Bad Request because of filename extension validation
    assert response.status_code == 400
    assert "Only CSV files are accepted" in response.json()["detail"]
