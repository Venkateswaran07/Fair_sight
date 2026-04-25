# FairSight Deployment Guide (Google Cloud Run)

This guide explains how to deploy the FairSight platform to Google Cloud.

## Prerequisites
1.  **Google Cloud SDK** (gcloud) installed and authenticated.
2.  **Project ID**: `fairsight-494322`
3.  **Region**: `us-central1`

---

## 1. Enable Cloud APIs
Run this command to ensure all required Google services are active:
```bash
gcloud services enable run.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com \
                       aiplatform.googleapis.com \
                       firestore.googleapis.com
```

---

## 2. Deploy Backend (FastAPI)
The backend handles data processing, Vertex AI mapping, and Firestore persistence.

1.  **Build and Push**:
    ```bash
    gcloud builds submit --tag gcr.io/fairsight-494322/fairsight-backend .
    ```

2.  **Deploy to Cloud Run**:
    ```bash
    gcloud run deploy fairsight-backend \
      --image gcr.io/fairsight-494322/fairsight-backend \
      --platform managed \
      --region us-central1 \
      --allow-unauthenticated \
      --memory 1Gi
    ```
    **Note the Service URL** provided after deployment (e.g., `https://fairsight-backend-xxx.run.app`).

---

## 3. Deploy Frontend (React/Vite)
The frontend must be built with the backend URL injected as an environment variable.

1.  **Build and Push**:
    ```bash
    cd fairsight-ui
    gcloud builds submit --tag gcr.io/fairsight-494322/fairsight-frontend .
    ```

2.  **Deploy to Cloud Run**:
    *Replace `YOUR_BACKEND_URL` with the URL from Step 2.*
    ```bash
    gcloud run deploy fairsight-frontend \
      --image gcr.io/fairsight-494322/fairsight-frontend \
      --platform managed \
      --region us-central1 \
      --allow-unauthenticated \
      --set-env-vars="VITE_API_URL=YOUR_BACKEND_URL"
    ```

---

## 4. Final IAM Permissions (Vertex AI Fix)
To resolve the `403 Permission Denied` error seen in logs:
1.  Go to the [GCP IAM Console](https://console.cloud.google.com/iam-admin/iam).
2.  Find the **Compute Engine default service account**.
3.  Assign the **Vertex AI User** role to this account.

---

## Local Testing with Docker
If you want to test the exact production setup on your own machine:
```bash
docker-compose up --build
```
This will start the backend on `localhost:8000` and the frontend on `localhost:80`.
