#!/usr/bin/env python3
"""
Manual test script for the POST /api/apitest/v1/predict/lesion endpoint
This script demonstrates how to call the endpoint with proper formatting
"""

import requests
import io

# Configuration
API_URL = "http://localhost:8000/api/apitest/v1/predict/lesion"
# In production, use a valid JWT token
AUTH_TOKEN = "Bearer test_token_replace_with_real_jwt"

def test_lesion_prediction():
    """Test the lesion prediction endpoint"""
    
    # Create a mock .mha file (in production, use actual medical images)
    mock_mha_content = b"Mock MHA file content for testing"
    
    # Prepare the multipart form data
    files = {
        'file': ('test_scan.mha', io.BytesIO(mock_mha_content), 'application/octet-stream')
    }
    
    # Prepare the form fields
    data = {
        'seriesInstanceUID': '1.2.840.113654.2.55.323804676332963457174235140303454945005',
        'lesionID': 1,
        'coordX': 61.14,
        'coordY': -163.28,
        'coordZ': -177.75,
        'patientID': '100570',
        'studyDate': '19990102',
        'ageAtStudyDate': 63,
        'gender': 'Male'
    }
    
    # Prepare headers
    headers = {
        'Authorization': AUTH_TOKEN
    }
    
    print("Testing POST /api/v1/predict/lesion endpoint...")
    print(f"URL: {API_URL}")
    print(f"Request data: {data}")
    print()
    
    try:
        # Make the request
        response = requests.post(API_URL, files=files, data=data, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        print("Response Body:")
        print(response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print()
        
        # Validate response structure if successful
        if response.status_code == 200:
            result = response.json()
            assert result.get('status') == 'success', "Expected status='success'"
            assert 'data' in result, "Expected 'data' field in response"
            data_obj = result['data']
            assert 'seriesInstanceUID' in data_obj, "Expected seriesInstanceUID in data"
            assert 'lesionID' in data_obj, "Expected lesionID in data"
            assert 'probability' in data_obj, "Expected probability in data"
            assert 'predictionLabel' in data_obj, "Expected predictionLabel in data"
            assert 'processingTimeMs' in data_obj, "Expected processingTimeMs in data"
            assert 0 <= data_obj['probability'] <= 1, "Probability must be between 0 and 1"
            assert data_obj['predictionLabel'] in [0, 1], "Prediction label must be 0 or 1"
            print("✓ Response structure is valid!")
        
        return response
        
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to the API server.")
        print("  Make sure the server is running on http://localhost:8000")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_error_cases():
    """Test various error scenarios"""
    
    print("\n" + "="*60)
    print("Testing Error Cases")
    print("="*60 + "\n")
    
    # Test 1: Missing authorization
    print("Test 1: Missing Authorization Header")
    files = {'file': ('test.mha', io.BytesIO(b"test"), 'application/octet-stream')}
    data = {
        'seriesInstanceUID': '1.2.840.113654.2.55.323804676332963457174235140303454945005',
        'lesionID': 1,
        'coordX': 61.14,
        'coordY': -163.28,
        'coordZ': -177.75,
    }
    try:
        response = requests.post(API_URL, files=files, data=data)
        print(f"  Status: {response.status_code} (Expected: 401)")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")
    print()
    
    # Test 2: Invalid file format
    print("Test 2: Invalid File Format (.txt instead of .mha)")
    files = {'file': ('test.txt', io.BytesIO(b"test"), 'text/plain')}
    headers = {'Authorization': AUTH_TOKEN}
    try:
        response = requests.post(API_URL, files=files, data=data, headers=headers)
        print(f"  Status: {response.status_code} (Expected: 400)")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")
    print()
    
    # Test 3: Invalid gender
    print("Test 3: Invalid Gender Value")
    files = {'file': ('test.mha', io.BytesIO(b"test"), 'application/octet-stream')}
    data_invalid = {**data, 'gender': 'InvalidGender'}
    try:
        response = requests.post(API_URL, files=files, data=data_invalid, headers=headers)
        print(f"  Status: {response.status_code} (Expected: 400)")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  Error: {e}")
    print()


if __name__ == '__main__':
    print("="*60)
    print("LUNA 2025 - Lesion Prediction API Test")
    print("="*60)
    print()
    
    # Test successful case
    test_lesion_prediction()
    
    # Test error cases
    test_error_cases()
    
    print("\n" + "="*60)
    print("Test completed")
    print("="*60)
