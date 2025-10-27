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

---

## Project Setup & Deployment

This project uses a hybrid approach: **Terraform** provisions the core infrastructure (GCS, IAM), the **Cloud Console** is used to manually create the data store, and a **Bash script** deploys the application code.

### Prerequisites

1.  [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated:
    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```
2.  [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) installed.
3.  Your project must have the following structure:
    ```
    ├── app.py             <-- Your application code
    ├── Dockerfile
    ├── requirements.txt
    ├── deploy.sh          <-- The deployment script
    ├── ...
    └── terraform/         <-- Your Terraform files
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        ├── terraform.tfvars.example
        └── rubrics/       <-- Your rubric PDFs go here
            ├── gatsby.pdf
            └── mockingbird.pdf
    ```
### Step 1: Provision Core Infrastructure (Terraform)

First, we will use Terraform to create the GCS bucket, upload the rubrics, and set up the service account.

From within the `terraform/` directory:

1.  **Create your variables file:**
    ```bash
    cp terraform.tfvars.example terraform.tfvars
    ```
2.  **Edit `terraform.tfvars`** and add your GCP project ID and a unique bucket name.
    ```hcl
    # terraform.tfvars
    gcp_project_id      = "your-gcp-project-id"
    rubrics_bucket_name = "your-unique-bucket-name-12345"
    ```
3.  **Run Terraform:**
    ```bash
    terraform init
    terraform apply
    ```
    This will create the bucket, upload your PDFs, and create the `essay-bot-sa` service account.
    
### Step 2: Create Data Store (Manual Console Step)

This is the critical manual step to create the **unstructured** data store.

1.  In the Google Cloud Console, go to **Vertex AI Search**.
2.  Select **"Create a new app"** (or use an existing one).
3.  Select **"Create new data store"**.
4.  Choose the **"Cloud Storage"** option (this is the one for unstructured data).
5.  **Enter the GCS Bucket path** that Terraform created (e.g., `gs://your-unique-bucket-name-12345`).
6.  Give your data store a **Data store name** (e.g., `essay-feedback-bot-ds`).
7.  Set the location to **`global`**.
8.  Click **"Create"**. The console will begin indexing your PDFs.
9.  After it's created, go to the data store's "Data" page and **copy the `Data store ID`** (it will look something like `essay-feedback-bot-ds_1234567890123`). You will need this for the next step.

### Step 3: Deploy Application (Bash Script)

Now that your infrastructure is ready and your data is indexed, you can deploy the application.

1.  **Set the Environment Variable:** In your terminal, set the `DATA_STORE_ID` you just copied.
    ```bash
    export DATA_STORE_ID="your-data-store-id-from-gcp-console"
    ```
2.  **Make the script executable:**
    ```bash
    chmod +x deploy.sh
    ```
3.  **Run the script:**
    ```bash
    ./deploy.sh
    ```
The script will automatically fetch all the other required values from your Terraform outputs and deploy your application to Cloud Run. Your application is now live.