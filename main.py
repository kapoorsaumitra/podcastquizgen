import streamlit as st
import subprocess
import os
import requests
import time
import json
import markdown2
from weasyprint import HTML

# Load API keys securely from secrets.toml
ASSEMBLYAI_API_KEY = st.secrets["ASSEMBLYAI_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Function to download audio from YouTube
def download_audio(youtube_url):
    try:
        output_file = "podcast_audio.mp3"
        subprocess.run(
            ["yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", output_file, youtube_url],
            check=True
        )
        return output_file
    except Exception as e:
        st.error(f"Error downloading audio: {e}")
        return None

# Function to upload audio to AssemblyAI
def upload_audio(file_path):
    try:
        with open(file_path, "rb") as f:
            headers = {"authorization": ASSEMBLYAI_API_KEY}
            response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
            response.raise_for_status()
            return response.json()["upload_url"]
    except Exception as e:
        st.error(f"Error uploading audio: {e}")
        return None

# Function to transcribe audio using AssemblyAI
def transcribe_audio(upload_url):
    try:
        headers = {"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"}
        payload = {"audio_url": upload_url}
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

# Function to generate markdown notes using Gemini API
def generate_markdown_notes(transcript):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Generate well-structured markdown notes for this podcast transcript:\n\n{transcript}"
                        }
                    ]
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        markdown_notes = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return markdown_notes
    except Exception as e:
        st.error(f"Error generating notes: {e}")
        return None

# Function to convert Markdown to a beautiful PDF
def generate_pdf(markdown_text):
    html_content = markdown2.markdown(markdown_text)
    pdf_file = "Podcast_Notes.pdf"

    # CSS Styling
    css = """
    <style>
        body { font-family: 'Arial', sans-serif; line-height: 1.6; margin: 20px; }
        h1 { color: #333366; font-size: 24px; }
        h2 { color: #444488; font-size: 20px; }
        p { font-size: 14px; }
        ul { padding-left: 20px; }
        li { margin-bottom: 5px; }
    </style>
    """

    # Generate and save the PDF
    HTML(string=css + html_content).write_pdf(pdf_file)
    return pdf_file

# Streamlit App
def main():
    st.title("Podcast Notes Generator 🎙️📜")

    youtube_url = st.text_input("Enter the YouTube link of the podcast:")

    if st.button("Generate Notes"):
        if not youtube_url:
            st.error("Please enter a valid YouTube link.")
            return

        with st.spinner("Processing..."):
            st.info("Downloading audio...")
            audio_file = download_audio(youtube_url)
            if not audio_file:
                return

            st.success("Audio downloaded successfully!")

            st.info("Uploading audio to AssemblyAI...")
            upload_url = upload_audio(audio_file)
            if not upload_url:
                return

            st.success("Audio uploaded successfully!")

            st.info("Transcribing audio...")
            transcript = transcribe_audio(upload_url)
            if not transcript:
                return

            st.success("Transcription completed!")

            st.info("Generating Markdown notes...")
            markdown_notes = generate_markdown_notes(transcript)
            if not markdown_notes:
                return

            st.success("Notes generated!")

            # Display Markdown
            st.subheader("Generated Notes")
            st.text_area("Markdown Output", markdown_notes, height=300)

            # Generate and download PDF
            pdf_file = generate_pdf(markdown_notes)
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="📄 Download Notes as PDF",
                    data=f,
                    file_name="Podcast_Notes.pdf",
                    mime="application/pdf"
                )

            # Cleanup
            if os.path.exists("podcast_audio.mp3"):
                os.remove("podcast_audio.mp3")
            if os.path.exists("Podcast_Notes.pdf"):
                os.remove("Podcast_Notes.pdf")

if __name__ == "__main__":
    main()
