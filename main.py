import streamlit as st
import subprocess
import os
import requests
import time
from collections import Counter
import re

# Function to download audio from YouTube
def download_audio(youtube_url):
    try:
        output_file = "podcast_audio.mp3"
        # Use yt-dlp to download audio
        subprocess.run(
            ["yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", output_file, youtube_url],
            check=True
        )
        return output_file
    except Exception as e:
        st.error(f"Error downloading audio: {e}")
        return None

# Function to upload audio to AssemblyAI
def upload_audio(file_path, api_key):
    try:
        with open(file_path, "rb") as f:
            headers = {"authorization": api_key}
            response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
            response.raise_for_status()
            return response.json()["upload_url"]
    except Exception as e:
        st.error(f"Error uploading audio: {e}")
        return None

# Function to transcribe audio using AssemblyAI
def transcribe_audio(upload_url, api_key):
    try:
        headers = {"authorization": api_key, "content-type": "application/json"}
        payload = {"audio_url": upload_url}

        # Send transcription request
        response = requests.post("https://api.assemblyai.com/v2/transcript", headers=headers, json=payload)
        response.raise_for_status()
        transcript_id = response.json()["id"]

        # Poll for transcription completion
        st.info("Transcribing... This may take a few minutes.")
        while True:
            status_response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
            status_response.raise_for_status()
            status = status_response.json()["status"]
            if status == "completed":
                return status_response.json()["text"]
            elif status == "failed":
                st.error("Transcription failed.")
                return None
            time.sleep(5)
    except Exception as e:
        st.error(f"Error during transcription: {e}")
        return None

def preprocess_text(text):
    """Helper function to clean and preprocess text"""
    # Remove special characters and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text.lower())
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text

def extract_key_topics(text, num_topics=3):
    """Extract key topics from text using word frequency"""
    # List of common stop words to exclude
    stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'is', 'are', 'was', 'were'])
    
    # Preprocess text
    cleaned_text = preprocess_text(text)
    words = cleaned_text.split()
    
    # Remove stop words
    words = [word for word in words if word not in stop_words and len(word) > 3]
    
    # Count word frequencies
    word_freq = Counter(words)
    
    # Get most common words
    return [word for word, _ in word_freq.most_common(num_topics)]

def generate_questions_from_text(transcript):
    """
    Generate meaningful quiz questions from the transcript using more sophisticated text analysis.
    """
    try:
        if not transcript:
            return []

        questions = []
        
        # Split transcript into sentences and paragraphs
        paragraphs = [p.strip() for p in transcript.split('\n') if p.strip()]
        sentences = [s.strip() for s in transcript.split('.') if len(s.strip()) > 20]
        
        # Extract key topics
        key_topics = extract_key_topics(transcript)
        
        # 1. Main Topic Question
        if key_topics:
            main_topic = key_topics[0]
            questions.append({
                "question": f"What is the main topic discussed that relates to '{main_topic}'?",
                "type": "short_answer",
                "answer": f"The main topic discusses {main_topic} in the context of {' and '.join(key_topics[1:3])}",
                "context": "main topic"
            })

        # 2. Key Concepts Questions
        if len(sentences) >= 2:
            important_sentence = sentences[1]
            questions.append({
                "question": f"True or False: The following statement is discussed: '{important_sentence[:100]}...'",
                "type": "true_false",
                "answer": "True",
                "context": "concept verification"
            })

        # 3. Detailed Questions
        for topic in key_topics[1:3]:
            relevant_sentences = [s for s in sentences if topic in s.lower()]
            if relevant_sentences:
                questions.append({
                    "question": f"What key point is made about {topic}?",
                    "type": "short_answer",
                    "answer": relevant_sentences[0][:100] + "...",
                    "context": "specific detail"
                })

        # 4. Summary Question
        if paragraphs:
            questions.append({
                "question": "Which of the following best summarizes a key takeaway from the discussion?",
                "type": "multiple_choice",
                "answer": paragraphs[0][:100] + "...",
                "context": "summary"
            })

        # Ensure we have at least 3 questions
        while len(questions) < 3 and sentences:
            questions.append({
                "question": f"What is being discussed in this segment: '{sentences.pop()[:50]}...'?",
                "type": "short_answer",
                "answer": "This segment discusses " + key_topics[0] if key_topics else "key concepts from the transcript",
                "context": "general understanding"
            })

        return questions

    except Exception as e:
        st.error(f"Error generating questions: {e}")
        return []

# Initialize session state variables
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'quiz_questions' not in st.session_state:
    st.session_state.quiz_questions = None
if 'show_answers' not in st.session_state:
    st.session_state.show_answers = {}

# Streamlit app
def main():
    st.title("Podcast Quiz Generator")
    
    # Add custom CSS for better styling
    st.markdown("""
        <style>
        .quiz-question {
            background-color:rgb(39, 39, 39);
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .answer-button {
            margin: 10px 0;
        }
        .answer-text {
            color: #0066cc;
            font-style: italic;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Input field for YouTube link
    youtube_url = st.text_input("Enter the YouTube link of the podcast:")
    
    # Get API key from secrets
    if "ASSEMBLYAI_API_KEY" not in st.secrets:
        st.error("Please set the ASSEMBLYAI_API_KEY in your Streamlit secrets.")
        return
    
    api_key = st.secrets["ASSEMBLYAI_API_KEY"]

    if st.button("Process Podcast"):
        if not youtube_url:
            st.error("Please enter a valid YouTube link.")
            return
            
        with st.spinner("Processing podcast..."):
            # Download audio
            st.info("Downloading audio from YouTube...")
            audio_file = download_audio(youtube_url)

            if not audio_file:
                st.error("Failed to download audio. Please check the YouTube link.")
                return

            st.success("Audio downloaded successfully!")

            # Upload audio
            st.info("Uploading audio to AssemblyAI...")
            upload_url = upload_audio(audio_file, api_key)

            if not upload_url:
                st.error("Failed to upload audio.")
                return

            st.success("Audio uploaded successfully!")

            # Transcribe audio
            st.info("Transcribing audio...")
            st.session_state.transcript = transcribe_audio(upload_url, api_key)

            if not st.session_state.transcript:
                st.error("Transcription failed.")
                return

            st.success("Transcription completed!")
            
            # Generate quiz
            st.info("Generating quiz questions...")
            st.session_state.quiz_questions = generate_questions_from_text(st.session_state.transcript)
            st.session_state.show_answers = {i: False for i in range(len(st.session_state.quiz_questions))}

            # Cleanup
            if os.path.exists("podcast_audio.mp3"):
                os.remove("podcast_audio.mp3")

    # Display transcript and quiz if available
    if st.session_state.transcript:
        st.subheader("Transcript")
        st.text_area("Podcast Transcript", st.session_state.transcript, height=300)

    if st.session_state.quiz_questions:
        st.subheader("Quiz Questions")
        for idx, question in enumerate(st.session_state.quiz_questions):
            with st.container():
                st.markdown(f"""
                    <div class="quiz-question">
                        <p><strong>Question {idx + 1}</strong> ({question['type']})</p>
                        <p>{question['question']}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Create a unique key for each button
                button_key = f"show_answer_{idx}"
                if st.button("Show Answer", key=button_key):
                    st.session_state.show_answers[idx] = True
                
                # Show answer if button was clicked
                if st.session_state.show_answers.get(idx):
                    st.markdown(f"""
                        <div class="answer-text">
                            <p><strong>Answer:</strong> {question['answer']}</p>
                            <p><em>Context: {question['context']}</em></p>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("---")

if __name__ == "__main__":
    main()