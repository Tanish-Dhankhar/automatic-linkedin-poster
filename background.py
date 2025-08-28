"""
LinkedIn Auto-Poster - Monitors Google Sheets and posts automatically
"""

import json
import time
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pathlib import Path
from credentials_loader import get_google_sheets_config, get_linkedin_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_poster.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class LinkedInPoster:
    """Handles LinkedIn API interactions."""
    
    def __init__(self, access_token: str, person_urn: str):
        self.access_token = access_token
        self.person_urn = person_urn
        self.api_base = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
    
    def register_media(self, media_type: str = "image") -> Tuple[str, str]:
        """Register media for upload."""
        register_data = {
            "registerUploadRequest": {
                "recipes": [f"urn:li:digitalmediaRecipe:feedshare-{media_type}"],
                "owner": self.person_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }]
            }
        }
        
        response = requests.post(
            f"{self.api_base}/assets?action=registerUpload",
            headers=self.headers,
            json=register_data
        )
        response.raise_for_status()
        
        result = response.json()
        upload_url = result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = result["value"]["asset"]
        return upload_url, asset_urn
    
    def upload_media(self, upload_url: str, file_path: str):
        """Upload media file."""
        with open(file_path, 'rb') as file:
            response = requests.put(
                upload_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                data=file.read()
            )
            response.raise_for_status()
    
    def create_post(self, text: str, media_paths: List[str] = None) -> str:
        """Create LinkedIn post with optional media."""
        post_data = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        
        if not media_paths:
            # Text-only post
            post_data["specificContent"] = {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            }
        else:
            # Post with media
            media_assets = []
            for path in media_paths:
                if not os.path.exists(path):
                    logger.warning(f"Media file not found: {path}")
                    continue
                
                try:
                    ext = Path(path).suffix.lower()
                    media_type = "video" if ext in ['.mp4', '.avi', '.mov'] else "image"
                    
                    logger.info(f"Uploading: {path}")
                    upload_url, asset_urn = self.register_media(media_type)
                    self.upload_media(upload_url, path)
                    
                    media_assets.append({
                        "status": "READY",
                        "media": asset_urn
                    })
                except Exception as e:
                    logger.error(f"Failed to upload {path}: {e}")
            
            if media_assets:
                post_data["specificContent"] = {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "IMAGE",
                        "media": media_assets
                    }
                }
            else:
                return self.create_post(text, None)
        
        response = requests.post(
            f"{self.api_base}/ugcPosts",
            headers=self.headers,
            json=post_data
        )
        response.raise_for_status()
        
        post_id = response.headers.get('X-RestLi-Id', 'Unknown')
        logger.info(f"Posted successfully: {post_id}")
        return post_id


class GoogleSheetsManager:
    """Manages Google Sheets interactions."""
    
    def __init__(self, sheet_id: str = None, sheet_name: str = None):
        # Load configuration from credentials.json if not provided
        if sheet_id is None or sheet_name is None:
            sheets_config = get_google_sheets_config()
            self.sheet_id = sheet_id or sheets_config['spreadsheet_id']
            self.sheet_name = sheet_name or sheets_config['sheet_name']
            service_account_file = sheets_config['service_account_file']
        else:
            self.sheet_id = sheet_id
            self.sheet_name = sheet_name
            sheets_config = get_google_sheets_config()
            service_account_file = sheets_config['service_account_file']
        
        creds = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=creds).spreadsheets()
    
    def get_posts(self) -> List[Dict]:
        """Get all posts from sheet."""
        result = self.service.values().get(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!A:E"
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return []
        
        headers = values[0]
        posts = []
        
        for i, row in enumerate(values[1:], start=2):
            post = {'row': i}
            for j, header in enumerate(headers):
                post[header] = row[j] if j < len(row) else ""
            posts.append(post)
        
        return posts
    
    def update_posted(self, row: int, timestamp: str):
        """Update posted_at timestamp."""
        self.service.values().update(
            spreadsheetId=self.sheet_id,
            range=f"{self.sheet_name}!E{row}",
            valueInputOption='RAW',
            body={'values': [[timestamp]]}
        ).execute()


class LinkedInScheduler:
    """Main scheduler for automated posting."""
    
    def __init__(self):
        # Load LinkedIn configuration
        linkedin_config = get_linkedin_config()
        self.linkedin_token = linkedin_config['linkedin_access_token']
        self.person_urn = linkedin_config['person_urn']
        
        # Initialize LinkedIn poster
        self.linkedin = LinkedInPoster(self.linkedin_token, self.person_urn)
        
        # Initialize Google Sheets manager (will load config from credentials.json)
        self.sheets = GoogleSheetsManager()
    
    def parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string assuming IST timezone."""
        if not dt_str or not dt_str.strip():
            return None
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                # Assume IST if no timezone
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                return dt
            except ValueError:
                continue
        
        logger.error(f"Invalid datetime format: {dt_str}")
        return None
    
    def check_and_post(self):
        """Check for scheduled posts and publish them."""
        current_time = datetime.now(timezone.utc)
        
        try:
            posts = self.sheets.get_posts()
            logger.info(f"Checking {len(posts)} posts")
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return
        
        for post in posts:
            try:
                # Skip if already posted
                if post.get('posted_at', '').strip():
                    continue
                
                # Check scheduled time
                scheduled_time = self.parse_datetime(post.get('to_be_posted_at', ''))
                if not scheduled_time or scheduled_time > current_time:
                    continue
                
                # Get content
                content = post.get('post', '').strip()
                if not content:
                    logger.warning(f"Row {post['row']}: No content")
                    continue
                
                # Get media paths
                media = post.get('attachments', '').strip()
                media_paths = [p.strip() for p in media.split(',') if p.strip()] if media else []
                
                # Post to LinkedIn
                logger.info(f"Posting row {post['row']}: {content[:50]}...")
                self.linkedin.create_post(content, media_paths)
                
                # Update sheet
                posted_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                self.sheets.update_posted(post['row'], posted_time)
                
                logger.info(f"Row {post['row']} posted successfully")
                
            except Exception as e:
                logger.error(f"Failed to post row {post.get('row', '?')}: {e}")
    
    def run(self):
        """Run the scheduler continuously."""
        logger.info("LinkedIn Scheduler started - Checking every 5 minutes")
        
        while True:
            try:
                self.check_and_post()
            except KeyboardInterrupt:
                logger.info("Scheduler stopped")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
            
            logger.info("Sleeping for 5 minutes...")
            time.sleep(300)


def main():
    """Main entry point."""
    print("LinkedIn Auto-Posting Service")
    print("Press Ctrl+C to stop")
    print("-" * 40)
    
    try:
        # Test if credentials can be loaded
        from credentials_loader import load_credentials
        credentials = load_credentials()
        logger.info("Credentials loaded successfully")
    except FileNotFoundError:
        print("❌ credentials.json not found!")
        print("Please run 'python setup.py' first to configure the system.")
        return
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        print(f"❌ Error loading credentials: {e}")
        return
    
    try:
        scheduler = LinkedInScheduler()
        print("✅ Service started successfully!")
        scheduler.run()
    except KeyboardInterrupt:
        print("\nService stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()