from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    RequestBlocked,
    IpBlocked,
)
import re

app = FastAPI(
    title="YouTube Transcript API",
    description="Fetch the transcript of any YouTube video by passing its video ID or full URL.",
    version="1.0.0",
)

# Allow requests from any origin (so your Chrome extension / frontend can call it)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def extract_video_id(video_id_or_url: str) -> str:
    """Accepts both a raw video ID and a full YouTube URL."""
    # If it looks like a URL, extract the ID
    if "youtube.com" in video_id_or_url or "youtu.be" in video_id_or_url:
        match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", video_id_or_url)
        if match:
            return match.group(1)
        raise HTTPException(status_code=400, detail="Could not extract video ID from the provided URL.")
    # Otherwise assume it's already a raw ID
    return video_id_or_url.strip()


@app.get("/")
def root():
    return {
        "message": "YouTube Transcript API is running!",
        "usage": "GET /transcript?video_id=<VIDEO_ID>",
        "example": "/transcript?video_id=dQw4w9WgXcQ",
        "docs": "/docs",
    }


@app.get("/transcript")
def get_transcript(
    video_id: str = Query(..., description="YouTube video ID (e.g. dQw4w9WgXcQ) or full URL"),
    language: str = Query("en", description="Language code, default is 'en' (English)"),
):
    """
    Fetch the full transcript of a YouTube video.

    - **video_id**: The YouTube video ID (e.g. `dQw4w9WgXcQ`) or full URL
    - **language**: Language code to fetch transcript in (default: `en`)
    """
    vid = extract_video_id(video_id)

    try:
        api = YouTubeTranscriptApi()

        # Try requested language first, fallback to any available language
        try:
            transcript = api.fetch(vid, languages=[language])
        except NoTranscriptFound:
            # Auto-pick any available transcript
            transcript_list = api.list(vid)
            transcript = next(iter(transcript_list)).fetch()

        snippets = [
            {"text": s.text, "start": round(s.start, 2), "duration": round(s.duration, 2)}
            for s in transcript
        ]

        full_text = " ".join(s.text for s in transcript)

        return {
            "success": True,
            "video_id": vid,
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "total_snippets": len(snippets),
            "transcript_text": full_text,
            "snippets": snippets,
        }

    except TranscriptsDisabled:
        raise HTTPException(status_code=404, detail="Transcripts are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video is unavailable or does not exist.")
    except (RequestBlocked, IpBlocked):
        raise HTTPException(status_code=429, detail="YouTube has blocked this server's IP. Try again later or use a proxy.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
