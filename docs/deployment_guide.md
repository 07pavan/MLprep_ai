# 🚀 Cloud Deployment & Setup Guide

This guide describes how to deploy the AI Data Analyst Agent in production using **Firebase** (Database & Auth), **Render** (Backend API), and **Netlify** (Frontend SPA).

---

## 🛠️ System Architecture Overview

```
 ┌────────────────┐               ┌────────────────┐
 │  Netlify SPA   │ ────────────> │ Render Backend │
 │ (React + Vite) │  (REST API)   │ (FastAPI + LG) │
 └────────────────┘               └────────────────┘
         │                                 │
         │ (ID Token)                      │ (Admin SDK)
         ▼                                 ▼
┌──────────────────┐             ┌──────────────────┐
│  Firebase Auth   │             │ Firebase/Firestore│
│  (User Sign-in)  │             │ (Graph State)    │
└──────────────────┘             └──────────────────┘
```

---

## 1. 🔥 Firebase Setup (Auth & Database)

Firebase handles client-side registration/login and provides the state database for the LangGraph orchestrator.

### Step 1.1: Create a Firebase Project
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Click **Add Project**, enter a name (e.g., `ai-data-analyst`), and create the project.

### Step 1.2: Enable Authentication
1. Go to the **Build > Authentication** section.
2. Click **Get Started**.
3. Under **Sign-in method**, enable:
   *   **Email/Password**
   *   **Google** (Optional, but supported by the frontend)

### Step 1.3: Enable Cloud Firestore
1. Go to **Build > Firestore Database**.
2. Click **Create Database**.
3. Select a location near your Render backend servers (e.g., `us-east` or `us-central`).
4. Select **Start in Production Mode** (or Test Mode for quick initialization).

### Step 1.4: Configure Firestore Collection Group Index (CRITICAL)
Because the chat persistence layer uses collection group queries to fetch threads without needing parent dataset parameters first, you must create a Collection Group Index in Firestore:
1. In the Firebase Console, go to **Build > Firestore Database** and click the **Indexes** tab.
2. Click **Single Field**, then click **Add Exemption**.
3. Configure the following properties:
   *   **Collection ID**: `threads`
   *   **Field Path**: `thread_id`
   *   **Query Scope**: Choose **Collection Group** (or check both Collection and Collection Group).
   *   Under the exemption settings, enable both **Ascending** and **Descending** indexes.
4. Alternatively, once the backend is running, attempt a chat query. If the index is missing, the application logs will show a Google API exception containing a direct link. You can click that link in the server logs to automatically generate and build the index.

### Step 1.5: Obtain Frontend Client Configurations
1. Go to **Project Settings** (gear icon in the sidebar).
2. Under **Your apps**, click the Web icon (`</>`) to register a web app.
3. Name it (e.g., `analyst-web`), and click register.
4. Copy the `firebaseConfig` object values. You will need these for Netlify environment variables:
   *   `apiKey`
   *   `authDomain`
   *   `projectId`
   *   `storageBucket`
   *   `messagingSenderId`
   *   `appId`

### Step 1.6: Obtain Backend Admin SDK Credentials
1. Under **Project Settings**, go to the **Service Accounts** tab.
2. Click **Generate New Private Key** (button at the bottom).
3. Save the downloaded JSON file. You will need to base64-encode this file content or paste it into Render.
   *   *Recommended (Base64 Injection)*: Run `[Convert]::ToBase64String([System.IO.File]::ReadAllBytes('path_to_json_file'))` in PowerShell to convert this JSON file to a single-line string.


---

## 2. 🎛️ Render Setup (FastAPI Backend)

Render will compile and host the FastAPI application in a Docker container.

### Step 2.1: Deploy Backend Web Service
1. Sign in to [Render](https://render.com/).
2. Click **New + > Web Service**.
3. Connect your GitHub repository containing the codebase.
4. Set the following basic parameters:
   *   **Name**: `ai-analyst-backend`
   *   **Root Directory**: `backend` (Points to the `backend/` subfolder)
   *   **Runtime**: `Docker` (Render will automatically detect the `Dockerfile` inside `backend/`)
   *   **Instance Type**: `Starter` (Do NOT use the Free tier because it spins down when idle, causing storage loss unless a persistent disk is configured).
5. **Configure a Persistent Disk (CRITICAL)**:
   *   Go to the **Disks** tab of your Web Service settings in the Render Dashboard.
   *   Click **Add Disk**.
   *   Name the disk: `storage-volume`
   *   Mount Path: `/app/storage` (This ensures uploaded datasets are preserved across restarts and scaling).
   *   Size: `1 GB` (or larger depending on your dataset requirements).

### Step 2.2: Add Environment Variables
Under the **Environment** tab, click **Add Environment Variable** and configure:

| Variable Name | Description | Value Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Primary LLM Key | `gsk_...` |
| `GOOGLE_API_KEY` | Backup LLM Key | `AIzaSy...` |
| `ENABLE_AUTH` | Enforces Firebase ID Verification | `true` |
| `FIREBASE_PROJECT_ID` | Firestore Project Identifier | `your-firebase-project-id` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Base64-encoded credential JSON | *Base64 string from Step 1.5* |
| `STORAGE_DIR` | Absolute path to mounted persistent storage volume | `/app/storage` |
| `FAST_MODEL` | Cheap Model for Classifier | `llama-3.1-8b-instant` |
| `FAST_PROVIDER` | Provider for cheap model | `groq` |
| `SMART_MODEL` | Smarter Model for Code Gen | `llama-3.3-70b-versatile` |
| `SMART_PROVIDER` | Provider for smart model | `groq` |
| `CORS_ORIGINS` | Allowed frontend domains | `["https://your-netlify-domain.netlify.app"]` |

> [!NOTE]
> Do NOT set `GOOGLE_APPLICATION_CREDENTIALS` manually in the Render dashboard. The application will automatically decode `FIREBASE_SERVICE_ACCOUNT_JSON` and set the credentials path internally.

---

## 3. 🌐 Netlify Setup (Vite Frontend)

Netlify compiles the React single-page application and hosts it statically.

> [!IMPORTANT]
> Because Vite embeds environment variables during compilation (`build time`), any updates to `VITE_*` environment variables in the Netlify dashboard will NOT take effect until a manual deployment/rebuild is triggered.

### Step 3.1: Create Netlify Site
1. Sign in to [Netlify](https://www.netlify.com/).
2. Click **Add new site > Import an existing project**.
3. Connect your GitHub repository.
4. Set the following build settings:
   *   **Base directory**: `frontend`
   *   **Build command**: `npm run build`
   *   **Publish directory**: `frontend/dist`

### Step 3.2: Configure Environment Variables
Under **Site configuration > Environment variables**, add:

| Variable Name | Value Description |
| :--- | :--- |
| `VITE_API_URL` | Your Render Web Service URL (e.g., `https://ai-analyst-backend.onrender.com`) |
| `VITE_FIREBASE_API_KEY` | Firebase Client Web Key (`apiKey`) |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase Domain (`authDomain`) |
| `VITE_FIREBASE_PROJECT_ID` | Firebase Project ID (`projectId`) |
| `VITE_FIREBASE_STORAGE_BUCKET` | Storage Bucket (`storageBucket`) |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Sender ID (`messagingSenderId`) |
| `VITE_FIREBASE_APP_ID` | App ID (`appId`) |

---

## ⚡ Production Verification Checklist

1.  **Backend Startup Check**: Visit your Render backend health endpoint `https://<your-backend-url>/health` in the browser. It should return:
    ```json
    {
      "status": "ok",
      "version": "2.0.0",
      "engine": "LangGraph + Vega-Lite"
    }
    ```
2.  **Auth Token Flow Check**: Sign up a new user via the Netlify login UI. Check the browser Console/Network logs to confirm that the `Authorization: Bearer <ID_TOKEN>` header is sent in client requests.
3.  **Firestore States Check**: Run a session chat query, and then go to the Firebase Console Firestore page. You should see a collection representing checkpointer state threads populated dynamically.

---

## 💾 Backup, Snapshots & Disaster Recovery Procedures

To ensure production reliability and prevent data loss, establish the following backup and recovery protocols.

### 1. 🐘 PostgreSQL Database Backup (State Store & Registry)
If using PostgreSQL (`DATABASE_URL`) instead of Firestore, schedule periodic database snapshots:

*   **Automated Backups on Render**:
    *   If using a Render Managed PostgreSQL database, automated daily backups are enabled by default (with a 7-day retention period on the Starter tier).
*   **Manual CLI Backup (pg_dump)**:
    *   Run the following command to generate a compressed backup of your database:
        ```bash
        pg_dump -H <host> -U <user> -d <database_name> -F c -b -v -f analyst_db_backup.dump
        ```
*   **Restore Procedure (pg_restore)**:
    *   To restore from a backup file, run:
        ```bash
        pg_restore -H <host> -U <user> -d <database_name> -c -v analyst_db_backup.dump
        ```

### 2. 🔥 Firestore Database Export (NoSQL States & Threads)
If utilizing Firestore for LangGraph checkpoint states and chat logs, schedule automatic exports:

*   **Export via Google Cloud CLI**:
    *   To manually trigger a database export to a Google Cloud Storage bucket:
        ```bash
        gcloud firestore export gs://<your-backup-bucket-name>
        ```
*   **Import / Restore Procedure**:
    *   To restore from a specific snapshot in Cloud Storage:
        ```bash
        gcloud firestore import gs://<your-backup-bucket-name>/<export-timestamp>/
        ```
*   **Automated Scheduled Exports**:
    *   Set up a Google Cloud Function triggered by Cloud Scheduler (cron) to run the export command daily.

### 3. 📂 Persistent Volume Storage Backup (Parquet Datasets)
Render Persistent Disks attached to `/app/storage` are secure, but you should run independent directory snapshots to recover from disk corruption or user accidents:

*   **Command Line Snapshot (tar)**:
    *   Run a scheduled cron job on the container to package and copy the storage folder to an external cloud bucket (e.g. AWS S3 or Google Cloud Storage):
        ```bash
        tar -czf dataset_storage_backup.tar.gz -C /app/storage .
        # Upload using AWS CLI or gsutil:
        aws s3 cp dataset_storage_backup.tar.gz s3://<your-backup-bucket>/backups/
        ```
*   **Disaster Recovery Restore**:
    *   To restore the files to a new volume, retrieve the tarball and unpack it:
        ```bash
        aws s3 cp s3://<your-backup-bucket>/backups/dataset_storage_backup.tar.gz .
        tar -xzf dataset_storage_backup.tar.gz -C /app/storage
        ```

