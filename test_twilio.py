import os
from twilio.rest import Client
import argparse
from dotenv import load_dotenv

def test_twilio_whatsapp(to_number: str):
    load_dotenv() # Load variables from .env automatically
    
    # Retrieve credentials from environment or replace with hardcoded ones for testing
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID', 'YOUR_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN', 'YOUR_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+16562202799') # Twilio Sandbox Number
    
    if account_sid == 'YOUR_ACCOUNT_SID':
        print("Error: Please set your Twilio credentials in this script or environment variables.")
        return

    try:
        client = Client(account_sid, auth_token)
        
        # If the user is trying to send SMS, ensure no 'whatsapp:' prefix is there
        # If the from_number has whatsapp:, keep it. Otherwise, assume SMS.
        is_whatsapp = from_number.startswith("whatsapp:")
        
        if is_whatsapp:
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
        else:
            to_number = to_number.replace("whatsapp:", "")
            
        message = client.messages.create(
            body="🚨 *PharmaSense Alert* 🚨\n\nThis is a test notification from your backend pipeline. If you are reading this, the Twilio integration works!",
            from_=from_number,
            to=to_number
        )
        
        print(f"Success! Message sent with SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send message. Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Twilio WhatsApp Integration")
    parser.add_argument("--to", required=True, help="Your personal phone number with country code (e.g., +919876543210)")
    args = parser.parse_args()
    
    test_twilio_whatsapp(args.to)
