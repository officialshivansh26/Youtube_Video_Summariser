import streamlit as st
from huggingface_hub import login
from youtube_transcript_api import YouTubeTranscriptApi
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from groq import Groq
import torch

def extract_transcript(youtube_video_url):
    try:
        video_id = youtube_video_url.split("v=")[1]
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        for transcript in transcript_list:
            if not transcript.is_generated:
                selected_transcript = transcript
                break
        else:
            selected_transcript = next(trans for trans in transcript_list if trans.is_generated)

        transcript_data = selected_transcript.fetch()
        transcript_text = " ".join([snippet.text for snippet in transcript_data])
        
        return transcript_text, selected_transcript.language_code
    except Exception as e:
        return f"Error: {str(e)}", ""

def chunk_text(text, max_length):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(" ".join(current_chunk)) > max_length:
            chunks.append(" ".join(current_chunk[:-1]))
            current_chunk = [word]

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def translate_text(chunks, translator):
    return " ".join(translator(chunk)[0]['translation_text'] for chunk in chunks)

checkpoint = "facebook/nllb-200-distilled-600M"
tokenizer = AutoTokenizer.from_pretrained(checkpoint)
model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint).to("cpu")

def process_translation(transcript, lang_code):
    language_mapping = {
        "hi": "hin_Deva", "bn": "ben_Beng", "ta": "tam_Taml", "te": "tel_Telu",
        "mr": "mar_Deva", "gu": "guj_Gujr", "kn": "kan_Knda", "ml": "mal_Mlym",
        "pa": "pan_Guru", "or": "ory_Orya", "sa": "san_Deva", "bho": "bho_Deva",
        "mai": "mai_Deva", "mag": "mag_Deva", "awa": "awa_Deva"
    }

    if lang_code and lang_code != 'en' and lang_code in language_mapping:
        translator = pipeline('translation', model=model, tokenizer=tokenizer,
                              src_lang=language_mapping[lang_code], tgt_lang="eng_Latn",
                              max_length=1024)
        chunks = chunk_text(transcript, max_length=512)
        return translate_text(chunks, translator)
    return transcript

def generate_summary(translated_text, groq_api_key):
    try:
        client = Groq(api_key=groq_api_key)
        text_chunks = chunk_text(translated_text, max_length=4096)
        summaries = []
        
        for chunk in text_chunks:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a YouTube video summarizer. Summarize the transcript in concise points within 250 words."},
                    {"role": "user", "content": chunk},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.5,
                max_completion_tokens=1024,
                top_p=1
            )
            summaries.append(chat_completion.choices[0].message.content)
        
        return " ".join(summaries)
    except Exception as e:
        return str(e)

st.title("YouTube Video Summarizer")

youtube_url = st.text_input("Enter YouTube Video URL:")
groq_api_key = st.text_input("Enter Groq API Key:", type="password")

if st.button("Summarize Video"):
    if not youtube_url or not groq_api_key:
        st.error("Please provide all required inputs.")
    else:
        with st.spinner("Extracting transcript..."):
            transcript, lang_code = extract_transcript(youtube_url)

            if "Error" in transcript:
                st.error(transcript)
            else:
                st.success("Transcript extracted successfully!")
                st.text_area("Transcript:", transcript, height=200)
                
                with st.spinner("Translating transcript..."):
                    translated_text = process_translation(transcript, lang_code)
                    st.success("Translation completed!")
                    st.text_area("Translated Text:", translated_text, height=200)
                
                with st.spinner("Generating summary..."):
                    summary = generate_summary(translated_text, groq_api_key)
                    st.success("Summary generated!")
                    st.text_area("Summary:", summary, height=200)
