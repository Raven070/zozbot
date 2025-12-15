# image_issue_handler.py
import os
import google.generativeai as genai
from typing import Tuple, Optional, List
from config import GENAI_API_KEY, BASE_DIR
import utils

logger = utils.logger

# Configure Gemini for vision
genai.configure(api_key=GENAI_API_KEY)

class SiteIssueImageHandler:
    """Handles image-based site issue recognition and responses."""
    
    def __init__(self):
        self.vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.issue_responses = self._load_issue_responses()
    
    def _load_issue_responses(self) -> dict:
        """Load predefined responses with images for each issue type."""
        return {
            "error_403": {
            "text": "متقلقش خااالص ❤️\nده مش بلوك من على المنصة، بس error بسيط بيحصل أحيانًا 🛠️💦\nكل اللي عليك يا بطل .. 🛠️\nتقفل ال tab/ الصفحة اللي حضرتك فيها دلوقتي، 🔄\nوتفتح tab جديدة وتعمل تسجيل دخول علي المنصة من الأول وجديد.\nإن شاء الله المشكلة هتتحل معاك ✅❤️"
           },
            "chrome_error_60072123": {
            "text": "• لو حصل مع حضرتك أي مشكلة زي الصور المتوضحة دي أثناء الحصة\n• أول حاجة، نتأكد إن Ad Block مقفول من المتصفح.\n• وممكن حضرتك تغيّر المتصفح اللي شغال عليه المنصة، وتجرب بدائل زي: ⛓️‍💥\n    • Chrome – Opera – Firefox.\n• ولو المشكلة لسه موجودة، جرب تعمل تسجيل خروج وتدخل تاني، وبعدها تعمل Refresh للصفحة.\nإن شاء الله المشكلة هتتحل معاك 💪❤️"
           },
            "go_back_to_the_page": {
                "text": "انا مش قادر احدد ايه المشكلة بالظبط فانت ممكن تبعتلنا على البيدج واحنا هنساعدك على قد ما نقدر",
                
            }
        }
    
    async def analyze_issue_image(self, image_path: str) -> Tuple[str, Optional[dict]]:
        """
        Analyze an image of a site issue and return appropriate response.
        
        Args:
            image_path: Path to the uploaded issue image
            
        Returns:
            Tuple of (issue_type, response_dict)
        """
        try:
            # Read the image
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
            
            # Prepare the prompt for Gemini Vision
            prompt = """
            You are analyzing a screenshot of a technical issue from an educational website.
            
            Identify which of these issues is shown in the image:
            1. "error_403" - HTTP 403 Forbidden error or access denied message
            2. "chrome_error_60072123" - Chrome browser error requiring update (error code 60072123)
            3. "session_closed" - A message indicating a session/lecture has expired or closed
            4. "payment_issue" - Problems with Vodafone Cash payment or payment failure

            ## go_back_to_the_page 
            Respond with ONLY the issue type identifier (error_403, chrome_error_60072123, session_closed, payment_issue, or go_back_to_the_page).
            If you cannot clearly identify the issue, respond with "go_back_to_the_page".
            
            Important: Respond with ONLY the identifier, nothing else.
            """
            
            # Upload the image and get response
            response = await self.vision_model.generate_content_async([
                prompt,
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            
            issue_type = response.text.strip().lower()
            
            # Validate the response
            if issue_type not in self.issue_responses:
                logger.warning(f"Unrecognized issue type: {issue_type}, defaulting to go_back_to_the_page")
                issue_type = "go_back_to_the_page"
            
            logger.info(f"Identified issue type: {issue_type}")
            return issue_type, self.issue_responses[issue_type]
            
        except Exception as e:
            logger.error(f"Error analyzing issue image: {e}", exc_info=True)
            return "go_back_to_the_page", self.issue_responses["go_back_to_the_page"]
    
    def get_response_images_paths(self, issue_type: str) -> List[str]:
        """Get full paths to response images for a given issue type."""
        if issue_type not in self.issue_responses:
            issue_type = "go_back_to_the_page"
        
        response = self.issue_responses[issue_type]
        base_path = os.path.join(BASE_DIR, 'assets')
        
        full_paths = []
        for img_rel_path in response.get("images", []):
            full_path = os.path.join(base_path, img_rel_path)
            if os.path.exists(full_path):
                full_paths.append(full_path)
            else:
                logger.warning(f"Response image not found: {full_path}")
        
        return full_paths

# Singleton instance
site_issue_handler = SiteIssueImageHandler()