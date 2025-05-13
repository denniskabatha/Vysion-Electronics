import os
import requests
import base64
from datetime import datetime
import logging
from flask import current_app

def get_access_token():
    """Get M-Pesa API access token."""
    consumer_key = current_app.config.get('MPESA_CONSUMER_KEY')
    consumer_secret = current_app.config.get('MPESA_CONSUMER_SECRET')
    environment = current_app.config.get('MPESA_ENVIRONMENT', 'sandbox')
    
    if not consumer_key or not consumer_secret:
        logging.error("M-Pesa credentials not configured")
        return None
    
    # API URL based on environment
    if environment == 'sandbox':
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    else:
        url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    # Create auth string and encode to base64
    auth_string = f"{consumer_key}:{consumer_secret}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        result = response.json()
        return result.get('access_token')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting M-Pesa access token: {str(e)}")
        return None

def format_timestamp():
    """Format timestamp for M-Pesa API."""
    return datetime.now().strftime('%Y%m%d%H%M%S')

def compute_password(shortcode, passkey, timestamp):
    """Compute M-Pesa API password."""
    passstring = shortcode + passkey + timestamp
    passbytes = passstring.encode('ascii')
    password = base64.b64encode(passbytes).decode('ascii')
    return password

def initiate_stk_push(phone_number, amount, reference):
    """
    Initiate M-Pesa STK push request.
    
    Args:
        phone_number: Customer phone number (format: 254XXXXXXXXX)
        amount: Transaction amount
        reference: Transaction reference (sale reference)
    
    Returns:
        API response dictionary
    """
    access_token = get_access_token()
    if not access_token:
        return {"ResponseCode": "1", "ResponseDescription": "Failed to get access token"}
    
    shortcode = current_app.config.get('MPESA_SHORTCODE')
    passkey = current_app.config.get('MPESA_PASSKEY')
    callback_url = current_app.config.get('MPESA_CALLBACK_URL')
    environment = current_app.config.get('MPESA_ENVIRONMENT', 'sandbox')
    
    if not shortcode or not passkey or not callback_url:
        logging.error("M-Pesa configuration incomplete")
        return {"ResponseCode": "1", "ResponseDescription": "M-Pesa configuration incomplete"}
    
    # Format phone number (remove leading 0 or +)
    if phone_number.startswith('+'):
        phone_number = phone_number[1:]
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    
    # API URL based on environment
    if environment == 'sandbox':
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    else:
        url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    timestamp = format_timestamp()
    password = compute_password(shortcode, passkey, timestamp)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": reference,
        "TransactionDesc": f"Payment for {reference}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error initiating STK push: {str(e)}")
        return {"ResponseCode": "1", "ResponseDescription": f"Request Error: {str(e)}"}

def check_transaction_status(checkout_request_id):
    """
    Check M-Pesa transaction status.
    
    Args:
        checkout_request_id: The checkout request ID from STK push
    
    Returns:
        API response dictionary
    """
    access_token = get_access_token()
    if not access_token:
        return {"ResultCode": "1", "ResultDesc": "Failed to get access token"}
    
    shortcode = current_app.config.get('MPESA_SHORTCODE')
    passkey = current_app.config.get('MPESA_PASSKEY')
    environment = current_app.config.get('MPESA_ENVIRONMENT', 'sandbox')
    
    # API URL based on environment
    if environment == 'sandbox':
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    else:
        url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    
    timestamp = format_timestamp()
    password = compute_password(shortcode, passkey, timestamp)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking transaction status: {str(e)}")
        return {"ResultCode": "1", "ResultDesc": f"Request Error: {str(e)}"}
