# AI Literary Feedback Assistant

This is a serverless web application that provides students with sophisticated, persona-driven feedback on their literature essays.

The app is built in Python using a Flask backend and is designed to be deployed on **Google Cloud Run**. It leverages a full **Retrieval-Augmented Generation (RAG)** pipeline using **Vertex AI Search** and **Google Cloud Storage** to retrieve the *exact* grading rubric, which is then used by **Gemini 2.5 Pro** to generate and score the feedback.

## Core Architecture & Flow

This application uses a hybrid, multi-step AI approach to ensure high-quality, accurate feedback.

1.  **Frontend:** A student enters their name and essay text into a simple HTML/JS webpage.
2.  **API (Cloud Run):** The Flask app receives the request at the `/grade` endpoint.
3.  **Step 1: Topic Extraction (AI):** The essay text is sent to **Gemini 2.5 Flash** to quickly and cheaply extract the essay's topic (e.g., `"The Great Gatsby"`).
4.  **Step 2: Rubric Retrieval (RAG):**
    * The topic is used to query **Vertex AI Search**.
    * A **score-based guardrail** (e.g., `keyword_similarity_score > 1.0`) ensures a high-quality match and rejects off-topic essays.
    * Vertex AI Search returns the document metadata, which includes a GCS URI (e.g., `gs://my-bucket/gatsby.pdf`).
    * The app fetches this PDF from **Google Cloud Storage**, parses the full text, and cleans it.
5.  **Step 3: Profile Retrieval (Mocked):** The app simulates a SQL call to a dummy database to fetch the student's learning preferences.
6.  **Step 4: Feedback Generation (AI):** The full essay, the *exact* rubric text, and the student's profile are combined into a master system prompt and sent to **Gemini 2.5 Pro**.
7.  **Step 5: Hybrid Scoring (Python):**
    * The AI is instructed **not to do math**. It returns a structured JSON "report card" with scores and justifications for each category.
    * The Python app parses this JSON, calculates the `Total Score` itself (ensuring 100% accuracy), and formats the final report into beautiful Markdown.
8.  **Response:** The final, formatted Markdown is sent to the frontend and rendered for the student.

## Project Setup & Deployment

### 1. Google Cloud Prerequisites

1.  **Create a GCS Bucket:**
    * Create a new Google Cloud Storage bucket.
    * Upload your rubric `.pdf` files (e.g., `the_great_gastby_rubric.pdf`) to this bucket.
2.  **Create a Vertex AI Search Data Store:**
    * Go to the Vertex AI Search console.
    * Create a new "Data Store" and link it to your GCS bucket.
    * Go to the **"Configurations"** tab and **enable "Enterprise edition features"** and **"Generative Responses"**. (This can take 5-10 minutes to provision).
    * Note your `DATA_STORE_ID`.
3.  **Create a Service Account:**
    * Create a service account (e.g., `essay-bot-sa`) to give Cloud Run permission to access other services.
    * Assign the following IAM roles to this service account:
        * `Vertex AI User` (to call Gemini)
        * `Discovery Engine Viewer` (to use Vertex AI Search)
        * `Storage Object Viewer` (to read the PDFs from GCS)
        * `Cloud Run Invoker` (to be run)
        * `Logs Writer` (for logging)

### 2. Local Development

1.  Clone this repository.
2.  Install dependencies:
    ```
    pip install -r requirements.txt
    ```
3.  Authenticate your local machine:
    ```
    gcloud auth application-default login
    ```
4.  Set your environment variables:
    ```
    export PROJECT_ID="your-gcp-project-id"
    export DATA_STORE_ID="your-vertex-ai-datastore-id"
    export LOCATION="global"
    export VERTEX_AI_LOCATION="us-central1"
    export MIN_KEYWORD_SCORE_THRESHOLD="1.0"
    ```
5.  Run the app:
    ```
    python app.py
    ```

### 3. Cloud Run Deployment

This project includes a `Dockerfile` and `requirements.txt` for easy deployment.

Run the following command, replacing the values with your own:
```
gcloud run deploy essay-feedback-bot
--source .
--region "us-central1"
--allow-unauthenticated
--port 8080
--timeout "120"
--service-account "essay-bot-sa@your-gcp-project-id.iam.gserviceaccount.com"
--set-env-vars "PROJECT_ID=your-gcp-project-id"
--set-env-vars "DATA_STORE_ID=your-vertex-ai-datastore-id"
--set-env-vars "LOCATION=global"
--set-env-vars "VERTEX_AI_LOCATION=us-central1"
--set-env-vars "MIN_KEYWORD_SCORE_THRESHOLD=1.0"
```