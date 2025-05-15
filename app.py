
import streamlit as st
import pandas as pd
import datetime
from datetime import timezone
from googleapiclient.discovery import build
from urllib.parse import urlparse

API_KEY = st.text_input("Enter Your YouTube API Key", type="password")
youtube = None
if API_KEY:
    youtube = build('youtube', 'v3', developerKey=API_KEY)

st.title("📊 YouTube Shorts Trend Analyzer")
channel_list = st.text_area("Enter YouTube Channel URLs (One per line):")

col1, col2 = st.columns(2)
with col1:
    min_views = st.number_input("Minimum Views", value=300000, step=50000)
with col2:
    min_velocity = st.number_input("Min Views per Hour", value=3000, step=500)

time_window_hours = st.slider("Upload Time Window (Hours)", min_value=24, max_value=72, value=48)

if st.button("Analyze Trends") and youtube:
    now = datetime.datetime.utcnow().replace(tzinfo=timezone.utc)
    published_after_dt = now - datetime.timedelta(hours=time_window_hours)
    
    channel_urls = channel_list.splitlines()
    results = []

    for url in channel_urls:
        handle = url.strip().split("/")[-1].replace("@", "").replace("/shorts", "")
        try:
            response = youtube.channels().list(part="id", forHandle=handle).execute()
            cid = response["items"][0]["id"]
            playlist_id = youtube.channels().list(
                part="contentDetails", id=cid
            ).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            
            next_page_token = None
            while True:
                playlist_items = youtube.playlistItems().list(
                    part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
                ).execute()

                video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_items.get("items", [])]

                if video_ids:
                    video_details = youtube.videos().list(
                        part="snippet,statistics,contentDetails",
                        id=",".join(video_ids)
                    ).execute()

                    for item in video_details.get("items", []):
                        stats = item.get("statistics", {})
                        snippet = item.get("snippet", {})
                        content_details = item.get("contentDetails", {})

                        duration = content_details.get("duration", "PT0S")
                        if "M" in duration or "H" in duration:
                            continue

                        view_count = int(stats.get("viewCount", 0))
                        published_at_iso = snippet.get("publishedAt")
                        published_at_dt = datetime.datetime.fromisoformat(published_at_iso.replace('Z', '+00:00'))

                        hours_since_upload = (now - published_at_dt).total_seconds() / 3600
                        view_velocity = view_count / hours_since_upload if hours_since_upload > 0 else 0

                        if published_at_dt >= published_after_dt and view_count >= min_views and view_velocity >= min_velocity:
                            results.append({
                                "Title": snippet.get("title"),
                                "Channel": snippet.get("channelTitle"),
                                "Views": view_count,
                                "PublishedAt": snippet.get("publishedAt"),
                                "HoursSinceUpload": round(hours_since_upload, 1),
                                "ViewsPerHour": int(view_velocity),
                                "Link": f"https://www.youtube.com/shorts/{item['id']}"
                            })

                next_page_token = playlist_items.get("nextPageToken")
                if not next_page_token:
                    break

        except Exception as e:
            st.warning(f"Error processing channel {handle}: {e}")

    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="ViewsPerHour", ascending=False).reset_index(drop=True)
        st.dataframe(df)

        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(label="📥 Download CSV", data=csv, file_name="trending_shorts.csv", mime="text/csv")
    else:
        st.info("No videos matched the criteria.")
