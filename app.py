import os
import json
import vertexai

from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud.discoveryengine_v1 import SearchRequest
from google.cloud.discoveryengine_v1.services.search_service.pagers import SearchPager
from google.cloud import storage
from pypdf import PdfReader
from io import BytesIO
from flask import Flask, request, jsonify, render_template
from vertexai.generative_models import (
    GenerativeModel, 
    HarmCategory, 
    HarmBlockThreshold,
    GenerationConfig
)

app = Flask(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "global")
DATA_STORE_ID = os.environ.get("DATA_STORE_ID")
VERTEX_AI_LOCATION = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
MIN_KEYWORD_SCORE_THRESHOLD = float(os.environ.get("MIN_KEYWORD_SCORE_THRESHOLD", 1.0))

vertexai.init(project=PROJECT_ID, location=VERTEX_AI_LOCATION)

search_client = discoveryengine.SearchServiceClient()
serving_config = search_client.serving_config_path(
    project=PROJECT_ID,
    location=LOCATION,
    data_store=DATA_STORE_ID,
    serving_config="default_config",
)
storage_client = storage.Client(project=PROJECT_ID)

DUMMY_STUDENT_DB = {
    "jane_doe": {
        "student_name": "Jane Doe",
        "feedback_style_preference": "Direct and constructive, prefers bullet points.",
        "historical_performance_summary": "Jane struggles with integrating quotes smoothly and often writes weak thesis statements, but her analysis is usually very strong."
    },
    "john_smith": {
        "student_name": "John Smith",
        "feedback_style_preference": "Gentle and inquisitive. Prefers questions.",
        "historical_performance_summary": "John has excellent thesis statements but his analysis can be superficial. Needs to dig deeper."
    }
}
def get_student_profile(first_name, last_name):
    key = f"{first_name.lower()}_{last_name.lower()}"
    return DUMMY_STUDENT_DB.get(key)

def extract_metadata_from_essay(essay_text):
    try:
        model = GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        You are a literary assistant. Read the following essay and identify the primary novel being discussed.
        Return *ONLY* a valid JSON object with a single key: "topic".
        
        Example:
        Essay: "The green light in Gatsby..."
        Output: {{"topic": "The Great Gatsby"}}
        
        Essay: "Scout's journey..."
        Output: {{"topic": "To Kill a Mockingbird"}}
        
        Essay:
        {essay_text}
        """
        
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(response_mime_type="application/json")
        )
        
        metadata = json.loads(response.text)
        return metadata.get("topic")
        
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        print(f"[DEBUG] ERROR in Step 1 (extract_metadata): {e}")
        return None

def get_rubric_from_search(topic):
    if not topic:
        print("[DEBUG] Step 2 (get_rubric): Received no topic, returning None.")
        return None
        
    try:
        print(f"[DEBUG] Step 2 (get_rubric): Building request for query: 'Rubric for {topic}'")

        req = SearchRequest(
            serving_config=serving_config,
            query=f"Rubric for {topic}",
            page_size=1
        )
        
        response: SearchPager = search_client.search(req)
        
        print(f"[DEBUG] Step 2 (get_rubric): Raw Vertex AI Search response: {response}")
        
        if response.results:
            
            rank_signals = response.results[0].rank_signals
            keyword_score = rank_signals.keyword_similarity_score
                        
            print(f"[DEBUG] Step 2 (get_rubric): Found result with keyword_score: {keyword_score}")

            if keyword_score < MIN_KEYWORD_SCORE_THRESHOLD:
                print(f"[DEBUG] Step 2 (get_rubric): REJECTED. Score {keyword_score} is below threshold {MIN_KEYWORD_SCORE_THRESHOLD}.")
                return None
            
            print(f"[DEBUG] Step 2 (get_rubric): ACCEPTED. Score {keyword_score} is above threshold.")
            doc_data = response.results[0].document.derived_struct_data
            gcs_link = doc_data.get("link")

            if not gcs_link or not gcs_link.startswith("gs://"):
                print(f"[DEBUG] Step 2 (get_rubric): Found doc, but 'link' field is missing or invalid: {gcs_link}")
                return None
            
            print(f"[DEBUG] Step 2 (get_rubric): Found link. Fetching from GCS: {gcs_link}")
            
            bucket_name, blob_name = gcs_link[5:].split("/", 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            pdf_data = blob.download_as_bytes()
            pdf_file = BytesIO(pdf_data)
            
            reader = PdfReader(pdf_file)
            all_page_texts = []
            for page in reader.pages:
                page_text = page.extract_text()
                # Split all lines, strip whitespace, and filter out empty ones
                lines = [line.strip() for line in page_text.splitlines() if line.strip()]
                # Join the clean lines with a single space to "re-flow" the paragraph
                all_page_texts.append(" ".join(lines))
            
            # Join each page's text with a double newline
            full_text = "\n\n".join(all_page_texts)
                
            print(f"[DEBUG] Step 2 (get_rubric): Successfully extracted text (Length: {len(full_text)})")
            return full_text
            
        else:
            print("[DEBUG] Step 2 (get_rubric): Query successful but returned 0 results.")
            return None
            
    except Exception as e:
        print(f"Error querying or fetching rubric: {e}")
        print(f"[DEBUG] Step 2 (get_rubric): ERROR during API call: {e}")
        return None

MASTER_SYSTEM_PROMPT_TEMPLATE = """
**Persona:**
You are Ms. Eleanor Vance, an experienced and insightful high school literature teacher. Your tone is encouraging, constructive, and professional.

**Core Task:**
Evaluate the student's essay (`{{ESSAY_TEXT}}`) rigorously against the provided `{{RUBRIC_TEXT}}`. You must also incorporate the student's profile (`{{STUDENT_PROFILE_JSON}}`).

**Process & Instructions:**

**0. Input Validation:**
* **If `{{ESSAY_TEXT}}` is blank, gibberish, or not a discernible essay,** you MUST respond *only* with the `InvalidSubmission` JSON format.
* **If `{{RUBRIC_TEXT}}` is "MISSING",** you MUST respond *only* with the `MissingRubric` JSON format.

**1. Evaluation (If Inputs are Valid):**
* Read the `{{RUBRIC_TEXT}}` to identify all grading categories.
* Go through the `{{ESSAY_TEXT}}`, evaluating it against each of those categories.
* Assign a numeric `score` and a `max_score` (which you will find in the rubric) for each category.
* Write a `justification` for each score.
* Use the `{{STUDENT_PROFILE_JSON}}` to identify 2-3 key `strengths` and 2-3 `areas_for_improvement`.
* Write an `opening` and `concluding_remarks`.

**CRITICAL RULE: You MUST NOT calculate the "Total Score".** The application will calculate the total.

**Output Formats:**

**1. On Success, use this JSON format:**
{
  "feedback_type": "StructuredFeedback",
  "opening": "Hello [Student Name], I've had the pleasure of reading your insightful essay on...",
  "strengths": [
    "A specific strength, (e.g., 'Clear Thesis: Your essay's central argument was...')",
    "Another specific strength..."
  ],
  "areas_for_improvement": [
    "A specific area for improvement with actionable advice, (e.g., 'Use of Evidence: While your points were strong, they would be more persuasive if...')",
    "Another specific area for improvement..."
  ],
  "rubric_assessment": [
    {
      "category": "[Category 1 Name from Rubric, e.g., 'Thesis and Argument']",
      "score": 3,
      "max_score": 4,
      "justification": "Your thesis is clear, but could be more argumentative..."
    },
    {
      "category": "[Category 2 Name from Rubric, e.g., 'Analysis of Characters']",
      "score": 4,
      "max_score": 4,
      "justification": "Excellent and nuanced analysis of the main character's motivations..."
    }
  ],
  "concluding_remarks": "Overall, this is a strong draft... Keep up the fantastic work! Best, Ms. Eleanor Vance."
}

If {{RUBRIC_TEXT}} is "MISSING", use this JSON format:
{
  "feedback_type": "MissingRubric",
  "message": "Hello [Student Name], please make sure you uploaded the right essay. I'm sorry, but we don't cover the rubrics for that topic at the moment. Please contact your teacher for more details. Best, Ms. Eleanor Vance."
}

If {{ESSAY_TEXT}} is invalid, use this JSON format:
{
  "feedback_type": "InvalidSubmission",
  "message": "Hello [Student Name], it seems there was an issue with your submission, as the text appears to be empty or incomplete. Please try uploading or recording your essay again. I'm here to help when you're ready! Best, Ms. Eleanor Vance."
}
"""

def generate_final_feedback(essay, rubric, profile):
    """
    CORRECTED: Uses the Vertex AI SDK, not 'genai'.
    Uses the Gemini 2.5 Pro model you requested.
    """
    
    model = GenerativeModel(
        "gemini-2.5-pro",
        system_instruction=MASTER_SYSTEM_PROMPT_TEMPLATE
    )
    
    final_user_prompt = f"""
Here is the data:

{{ESSAY_TEXT}}:
{essay}

{{RUBRIC_TEXT}}:
{rubric if rubric else "MISSING"}

{{STUDENT_PROFILE_JSON}}:
{json.dumps(profile) if profile else "MISSING"}

Please generate the feedback JSON now.
"""
    print("[DEBUG] Step 4 (generate_feedback): Assembled final prompt for Gemini 2.5 Pro.") # <-- ADD THIS
    print("--------------------------------------------------")
    print(final_user_prompt)
    print("--------------------------------------------------")

    try:
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        response = model.generate_content(
            final_user_prompt,
            safety_settings=safety_settings,
            generation_config=GenerationConfig(response_mime_type="application/json")
        )
        
        return response.text
        
    except Exception as e:
        print(f"Error calling Gemini 2.5 Pro: {e}")
        return json.dumps({
            "feedback_type": "ErrorFeedback",
            "message": f"An internal error occurred while generating feedback: {e}"
        })
def format_feedback_as_markdown(ai_data, student_name):
    """
    Takes the structured JSON from the AI and formats it into
    the final, human-readable Markdown.
    This is where we do the math.
    """
    try:
        feedback_type = ai_data.get("feedback_type")
        
        if feedback_type in ("MissingRubric", "InvalidSubmission", "InternalError"):
            default_msg = "An unexpected error occurred."
            return ai_data.get("message", default_msg).replace("[Student Name]", student_name)

        if feedback_type != "StructuredFeedback":
            print(f"Unknown feedback_type received: {feedback_type}")
            return "An unexpected error occurred while formatting the feedback."

        opening = ai_data.get('opening', '').replace("[Student Name]", student_name)
        strengths = ai_data.get('strengths', [])
        improvements = ai_data.get('areas_for_improvement', [])
        rubric_data = ai_data.get('rubric_assessment', [])
        conclusion = ai_data.get('concluding_remarks', '')

        md_parts = [f"{opening}\n"]
        
        md_parts.append("### Overall Feedback")
        md_parts.append("\n**Strengths:**")
        for s in strengths:
            md_parts.append(f"* {s}")
        
        md_parts.append("\n**Areas for Improvement:**")
        for i in improvements:
            md_parts.append(f"* {i}")
        
        md_parts.append("\n### Grading Rubric")
        
        md_parts.append("| Category | Score | Comments |")
        md_parts.append("| :--- | :--- | :--- |")
        
        total_score = 0
        max_total_score = 0
        
        for item in rubric_data:
            category = item.get('category', 'N/A')
            score = item.get('score', 0)
            max_score = item.get('max_score', 0)
            justification = item.get('justification', 'No comment.')
            
            total_score += score
            max_total_score += max_score
            
            md_parts.append(f"| **{category}** | **{score} / {max_score}** | {justification} |")
        
        md_parts.append(f"\n**Total Score: {total_score} / {max_total_score}**")
        
        md_parts.append(f"\n{conclusion}")
        
        return "\n".join(md_parts)

    except Exception as e:
        print(f"Error in format_feedback_as_markdown: {e}")
        print(f"Data that caused error: {ai_data}")
        return "An error occurred while formatting the feedback."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/grade', methods=['POST'])
def grade_essay():
    """The main API endpoint for the Hybrid approach."""
    print("\n\n--- NEW REQUEST RECEIVED ---")
    data = request.json
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    essay_text = data.get('essayText')
    student_name = first_name
    
    print(f"[DEBUG] Student: {first_name} {last_name}")
    print(f"[DEBUG] Essay (snippet): {essay_text[:100]}...")
    
    print("[DEBUG] Calling Step 1: extract_metadata_from_essay...")
    topic = extract_metadata_from_essay(essay_text)
    print(f"[DEBUG] >>> Step 1 Result (topic): {topic}")
    
    print(f"[DEBUG] Calling Step 2: get_rubric_from_search...")
    rubric = get_rubric_from_search(topic)
    if rubric:
        print(f"[DEBUG] >>> Step 2 Result (rubric): Found! (Length: {len(rubric)})")
    else:
        print("[DEBUG] >>> Step 2 Result (rubric): NOT FOUND (None)")
    
    print("[DEBUG] Calling Step 3: get_student_profile...")
    profile = get_student_profile(first_name, last_name)
    print(f"[DEBUG] >>> Step 3 Result (profile): {profile is not None}")

    print("[DEBUG] Calling Step 4: generate_final_feedback (Getting JSON)...")
    ai_json_string = generate_final_feedback(essay_text, rubric, profile)
    
    try:
        ai_data = json.loads(ai_json_string)
        print(f"[DEBUG] Step 5a: Received AI JSON: {ai_data}")
        
        print("[DEBUG] Calling Step 5b: format_feedback_as_markdown...")
        final_markdown = format_feedback_as_markdown(ai_data, student_name)
        
        final_output_json = {
            "feedback_type": "TextFeedback",
            "feedback_text": final_markdown
        }
        
        return jsonify(final_output_json)
        
    except json.JSONDecodeError:
        print(f"[DEBUG] ERROR: Final output from AI was not valid JSON. Raw text: {ai_json_string}")
        return jsonify({
            "feedback_type": "ErrorFeedback",
            "feedback_text": "The AI returned an invalid response. Please try again."
        })

    except Exception as e:
        print(f"An error occurred in grade_essay: {e}")
        return jsonify({
            "feedback_type": "ErrorFeedback",
            "feedback_text": "An internal server error occurred."
        })