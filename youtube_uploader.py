"""YouTube uploader using Google API."""
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# OAuth2 scopes required for uploading
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


# Path for storing credentials
CREDENTIALS_DIR = os.path.join(os.path.dirname(__file__), 'credentials')
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, 'token.pickle')
CLIENT_SECRETS_PATH = os.path.join(CREDENTIALS_DIR, 'client_secrets.json')


class YouTubeUploader:
    def __init__(self):
        self.youtube = None
        self._authenticated = False

    def is_configured(self) -> bool:
        """Check if client secrets file exists."""
        return os.path.exists(CLIENT_SECRETS_PATH)

    def authenticate(self) -> bool:
        """
        Authenticate with YouTube API.
        Returns True if successful.
        """
        if not self.is_configured():
            print(f"Error: Missing {CLIENT_SECRETS_PATH}")
            print("Please download OAuth2 credentials from Google Cloud Console")
            print("and save them as 'client_secrets.json' in the credentials folder.")
            return False

        creds = None

        # Load existing token if available
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)

        # Refresh or get new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRETS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=8080)

                # Save credentials for next time
                os.makedirs(CREDENTIALS_DIR, exist_ok=True)
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Authentication failed: {e}")
                return False

        try:
            self.youtube = build('youtube', 'v3', credentials=creds)
            self._authenticated = True
            return True
        except Exception as e:
            print(f"Failed to build YouTube API client: {e}")
            return False

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] = None,
        privacy: str = "unlisted",
        progress_callback=None
    ) -> str | None:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy: 'public', 'private', or 'unlisted'
            progress_callback: Function to call with upload progress (0-1)

        Returns:
            Video URL on success, None on failure
        """
        if not self._authenticated:
            if not self.authenticate():
                return None

        if not os.path.exists(video_path):
            print(f"Error: Video file not found: {video_path}")
            return None

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or [],
                'categoryId': '10'  # Music category
            },
            'status': {
                'privacyStatus': privacy,
                'selfDeclaredMadeForKids': False
            }
        }

        # Create media upload object
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )

        try:
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.progress())

            video_id = response['id']
            video_url = f"https://youtu.be/{video_id}"
            print(f"Upload complete: {video_url}")
            return video_url

        except Exception as e:
            print(f"Upload failed: {e}")
            return None


def setup_instructions():
    """Print instructions for setting up YouTube API access."""
    print("""
=== YouTube API Setup Instructions ===

1. Go to https://console.cloud.google.com/

2. Create a new project (or select existing)

3. Enable the YouTube Data API v3:
   - Go to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"

4. Create OAuth2 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Desktop app"
   - Download the JSON file

5. Save the downloaded file as:
   {path}

6. On first upload, a browser window will open for authentication.
   Grant the app permission to upload videos.

The authentication token will be saved locally for future use.
""".format(path=CLIENT_SECRETS_PATH))
