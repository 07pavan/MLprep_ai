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

### Step 1.4: Obtain Frontend Client Configurations
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

### Step 1.5: Obtain Backend Admin SDK Credentials
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
   *   **Instance Type**: `Starter` (or Free - note that Free services spin down when idle).

### Step 2.2: Add Environment Variables
Under the **Environment** tab, click **Add Environment Variable** and configure:

| Variable Name | Description | Value Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Primary LLM Key | `gsk_...` |
| `GOOGLE_API_KEY` | Backup LLM Key | `AIzaSy...` |
| `ENABLE_AUTH` | Enforces Firebase ID Verification | `true` |
| `FIREBASE_PROJECT_ID` | Firestore Project Identifier | `your-firebase-project-id` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Service Key Json | `/app/firebase-key.json` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Base64-encoded credential JSON (we will write a script to decode this) | *Base64 string from Step 1.5* |
| `FAST_MODEL` | Cheap Model for Classifier | `llama-3.1-8b-instant` |
| `FAST_PROVIDER` | Provider for cheap model | `groq` |
| `SMART_MODEL` | Smarter Model for Code Gen | `llama-3.3-70b-versatile` |
| `SMART_PROVIDER` | Provider for smart model | `groq` |
| `CORS_ORIGINS` | Allowed frontend domains | `["https://your-netlify-domain.netlify.app"]` |

---

## 3. 🌐 Netlify Setup (Vite Frontend)

Netlify compiles the React single-page application and hosts it statically.

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
