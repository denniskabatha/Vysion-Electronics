"""
KRA Electronic Tax Invoice Management System (eTIMS) integration module.

This module provides functionality for integrating with Kenya Revenue Authority's
Electronic Tax Invoice Management System (eTIMS) for tax compliance.

It handles:
1. Digital certificate management
2. Electronic signature of invoices
3. QR code generation
4. Control Unit integration
5. Real-time transmission of invoice data
6. Offline compliance mode
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

import qrcode
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from flask import current_app, g, session

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# eTIMS API configuration
ETIMS_API_TIMEOUT = 10  # seconds
OFFLINE_QUEUE_FILE = "instance/etims_offline_queue.json"
CERTIFICATE_PATH = "instance/etims_certificate.p12"


class ETIMSError(Exception):
    """Exception raised for eTIMS-related errors."""

    def __init__(self, message: str, status_code: int = None, response: str = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


def load_certificate(certificate_path: str, password: str) -> Tuple:
    """
    Load a PKCS#12 certificate for electronic signing.
    
    Args:
        certificate_path: Path to .p12 or .pfx certificate file
        password: Password to decrypt the certificate
        
    Returns:
        Tuple of (private key, certificate, CA certificates)
    """
    try:
        with open(certificate_path, "rb") as f:
            p12_data = f.read()
        
        # Decode the PKCS#12 data
        private_key, certificate, ca_certs = pkcs12.load_key_and_certificates(
            p12_data, password.encode(), default_backend()
        )
        
        return private_key, certificate, ca_certs
    except Exception as e:
        logger.error(f"Failed to load certificate: {str(e)}")
        raise ETIMSError(f"Certificate loading error: {str(e)}")


def sign_invoice_data(data: str, private_key) -> str:
    """
    Digitally sign invoice data using the private key.
    
    Args:
        data: String data to sign (usually JSON invoice data)
        private_key: RSA private key from the certificate
        
    Returns:
        Base64-encoded signature
    """
    try:
        # Hash and sign the data
        signature = private_key.sign(
            data.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # Return base64 encoded signature
        return base64.b64encode(signature).decode()
    except Exception as e:
        logger.error(f"Failed to sign invoice data: {str(e)}")
        raise ETIMSError(f"Digital signature error: {str(e)}")


def generate_invoice_qr_code(
    pin: str, 
    invoice_number: str, 
    date: str, 
    total_amount: float, 
    vat_amount: float,
    device_id: str
) -> BytesIO:
    """
    Generate a KRA-compliant QR code for the invoice.
    
    Args:
        pin: KRA PIN number
        invoice_number: Invoice/receipt reference number
        date: Invoice date (ISO format)
        total_amount: Total invoice amount
        vat_amount: VAT amount
        device_id: Control Unit Device ID
        
    Returns:
        BytesIO object containing the QR code image
    """
    try:
        # Format the QR code data according to KRA specification
        qr_data = (
            f"KRA:PIN={pin}:"
            f"REF={invoice_number}:"
            f"DATE={date}:"
            f"AMT={total_amount:.2f}:"
            f"VAT={vat_amount:.2f}:"
            f"CU={device_id}"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO object
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        logger.error(f"Failed to generate QR code: {str(e)}")
        raise ETIMSError(f"QR code generation error: {str(e)}")


def format_invoice_data(sale, store, products, tax_pin: str, device_id: str) -> Dict:
    """
    Format sale data into KRA eTIMS compatible invoice data.
    
    Args:
        sale: Sale model object
        store: Store model object
        products: List of products in the sale
        tax_pin: KRA PIN number
        device_id: Control Unit Device ID
        
    Returns:
        Dictionary with formatted invoice data for eTIMS API
    """
    try:
        invoice_date = sale.sale_date.strftime("%Y-%m-%d")
        invoice_time = sale.sale_date.strftime("%H:%M:%S")
        
        # Basic invoice information
        invoice_data = {
            "invoiceType": "1",  # 1 for regular invoice
            "traderSystemInvoiceNumber": sale.reference,
            "invoiceDate": invoice_date,
            "invoiceTime": invoice_time,
            "sellerPINNumber": tax_pin,
            "deviceId": device_id,
            "taxableAmount": sale.subtotal,
            "totalTax": sale.tax_amount,
            "totalInvoiceAmount": sale.total_amount,
            "items": []
        }
        
        # Add items
        for item in sale.items:
            product_data = {
                "itemCode": item.product.sku or f"PROD-{item.product.id}",
                "itemName": item.product.name,
                "quantity": item.quantity,
                "unitPrice": item.unit_price,
                "taxRate": item.tax_rate,
                "taxAmount": (item.unit_price * item.quantity * item.tax_rate / 100),
                "discountAmount": item.discount_amount,
                "lineTotal": item.total_price
            }
            invoice_data["items"].append(product_data)
        
        return invoice_data
    except Exception as e:
        logger.error(f"Failed to format invoice data: {str(e)}")
        raise ETIMSError(f"Invoice data formatting error: {str(e)}")


def transmit_invoice(
    invoice_data: Dict,
    api_url: str,
    private_key,
    certificate
) -> Dict:
    """
    Transmit invoice data to KRA eTIMS API in real-time.
    
    Args:
        invoice_data: Formatted invoice data dictionary
        api_url: KRA eTIMS API endpoint URL
        private_key: RSA private key for signing
        certificate: X.509 certificate
        
    Returns:
        API response as dictionary
    """
    try:
        # Convert invoice data to JSON
        invoice_json = json.dumps(invoice_data)
        
        # Sign the invoice data
        signature = sign_invoice_data(invoice_json, private_key)
        
        # Extract certificate details for header
        cert_serial = format(certificate.serial_number, 'x')
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "RequestId": str(uuid.uuid4()),
            "CertificateSerialNumber": cert_serial,
            "Signature": signature
        }
        
        # Send to KRA eTIMS API
        response = requests.post(
            f"{api_url.rstrip('/')}/invoices",
            data=invoice_json,
            headers=headers,
            timeout=ETIMS_API_TIMEOUT
        )
        
        # Check for success (KRA typically returns 200-202 for success)
        if response.status_code in (200, 201, 202):
            return response.json()
        else:
            logger.error(f"eTIMS API error: {response.status_code} - {response.text}")
            raise ETIMSError(
                f"eTIMS API returned error {response.status_code}",
                status_code=response.status_code,
                response=response.text
            )
    except requests.RequestException as e:
        logger.error(f"eTIMS API request failed: {str(e)}")
        raise ETIMSError(f"Communication error with eTIMS API: {str(e)}")


def queue_for_offline_transmission(invoice_data: Dict) -> str:
    """
    Queue invoice data for later transmission when in offline mode.
    
    Args:
        invoice_data: Formatted invoice data dictionary
        
    Returns:
        Queue reference ID
    """
    try:
        # Generate a unique ID for this queued invoice
        queue_id = f"OFFLINE-{str(uuid.uuid4())[:8]}"
        
        # Create the offline queue file if it doesn't exist
        os.makedirs(os.path.dirname(OFFLINE_QUEUE_FILE), exist_ok=True)
        
        # Load existing queue or create new one
        if os.path.exists(OFFLINE_QUEUE_FILE):
            with open(OFFLINE_QUEUE_FILE, "r") as f:
                queue = json.load(f)
        else:
            queue = []
        
        # Add the new invoice to the queue with timestamp
        queue.append({
            "id": queue_id,
            "timestamp": datetime.now().isoformat(),
            "invoice_data": invoice_data,
            "status": "pending"
        })
        
        # Save the updated queue
        with open(OFFLINE_QUEUE_FILE, "w") as f:
            json.dump(queue, f, indent=2)
        
        logger.info(f"Invoice queued for offline transmission: {queue_id}")
        return queue_id
    except Exception as e:
        logger.error(f"Failed to queue invoice for offline transmission: {str(e)}")
        raise ETIMSError(f"Offline queue error: {str(e)}")


def process_offline_queue(
    api_url: str,
    private_key,
    certificate
) -> Tuple[int, int]:
    """
    Process the offline queue and transmit pending invoices to KRA eTIMS.
    
    Args:
        api_url: KRA eTIMS API endpoint URL
        private_key: RSA private key for signing
        certificate: X.509 certificate
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    if not os.path.exists(OFFLINE_QUEUE_FILE):
        return 0, 0
    
    try:
        # Load the queue
        with open(OFFLINE_QUEUE_FILE, "r") as f:
            queue = json.load(f)
        
        success_count = 0
        fail_count = 0
        
        # Process each pending invoice
        for item in queue:
            if item["status"] == "pending":
                try:
                    # Attempt to transmit to eTIMS
                    response = transmit_invoice(
                        item["invoice_data"],
                        api_url,
                        private_key,
                        certificate
                    )
                    
                    # Update status to success
                    item["status"] = "transmitted"
                    item["transmission_time"] = datetime.now().isoformat()
                    item["response"] = response
                    success_count += 1
                    
                except ETIMSError as e:
                    # Mark as failed but keep in queue for retry
                    item["status"] = "failed"
                    item["error"] = str(e)
                    item["last_attempt"] = datetime.now().isoformat()
                    fail_count += 1
        
        # Save the updated queue
        with open(OFFLINE_QUEUE_FILE, "w") as f:
            json.dump(queue, f, indent=2)
        
        return success_count, fail_count
    except Exception as e:
        logger.error(f"Failed to process offline queue: {str(e)}")
        raise ETIMSError(f"Offline queue processing error: {str(e)}")


def get_offline_queue_stats() -> Dict:
    """
    Get statistics about the offline queue.
    
    Returns:
        Dictionary with queue statistics
    """
    if not os.path.exists(OFFLINE_QUEUE_FILE):
        return {
            "total": 0,
            "pending": 0,
            "transmitted": 0,
            "failed": 0
        }
    
    try:
        # Load the queue
        with open(OFFLINE_QUEUE_FILE, "r") as f:
            queue = json.load(f)
        
        # Count items by status
        stats = {
            "total": len(queue),
            "pending": 0,
            "transmitted": 0,
            "failed": 0
        }
        
        for item in queue:
            status = item.get("status", "pending")
            if status in stats:
                stats[status] += 1
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get offline queue stats: {str(e)}")
        return {
            "total": 0,
            "pending": 0,
            "transmitted": 0,
            "failed": 0,
            "error": str(e)
        }


def test_etims_connection(api_url: str) -> bool:
    """
    Test connection to KRA eTIMS API.
    
    Args:
        api_url: KRA eTIMS API endpoint URL
        
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        # Try to connect to the health check endpoint
        response = requests.get(
            f"{api_url.rstrip('/')}/health",
            timeout=ETIMS_API_TIMEOUT
        )
        
        # Check if connection is successful
        return response.status_code == 200
    except requests.RequestException:
        return False


def verify_control_unit(api_url: str, device_id: str, tax_pin: str) -> Dict:
    """
    Verify if a Control Unit is registered and authorized with KRA.
    
    Args:
        api_url: KRA eTIMS API endpoint URL
        device_id: Control Unit Device ID
        tax_pin: KRA PIN number
        
    Returns:
        Device verification response as dictionary
    """
    try:
        # Prepare request data
        verification_data = {
            "deviceId": device_id,
            "pinNumber": tax_pin
        }
        
        # Send verification request
        response = requests.post(
            f"{api_url.rstrip('/')}/devices/verify",
            json=verification_data,
            timeout=ETIMS_API_TIMEOUT
        )
        
        # Check response
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Control Unit verification failed: {response.status_code} - {response.text}")
            raise ETIMSError(
                f"Control Unit verification failed with status {response.status_code}",
                status_code=response.status_code,
                response=response.text
            )
    except requests.RequestException as e:
        logger.error(f"Control Unit verification request failed: {str(e)}")
        raise ETIMSError(f"Communication error during Control Unit verification: {str(e)}")


def handle_sale_for_etims(sale_id: int) -> Dict:
    """
    Main function to handle a sale for KRA eTIMS compliance.
    
    This function:
    1. Loads sale data
    2. Gets eTIMS settings
    3. Formats invoice data
    4. Generates QR code
    5. Signs and transmits invoice data (or queues for offline)
    
    Args:
        sale_id: ID of the Sale record
        
    Returns:
        Dictionary with eTIMS processing results
    """
    from models import Sale, Store
    
    try:
        # Get eTIMS settings from application config
        enable_tims = current_app.config.get("ENABLE_TIMS", False)
        if not enable_tims:
            return {"status": "skipped", "reason": "eTIMS integration is disabled"}
        
        tax_pin = current_app.config.get("TAX_PIN")
        device_id = current_app.config.get("TIMS_DEVICE_ID")
        api_url = current_app.config.get("TIMS_URL")
        cert_path = current_app.config.get("TIMS_CERTIFICATE_PATH", CERTIFICATE_PATH)
        cert_password = current_app.config.get("TIMS_CERTIFICATE_PASSWORD")
        
        # Validate required settings
        if not tax_pin:
            return {"status": "error", "reason": "KRA PIN is not configured"}
        
        if not device_id:
            return {"status": "error", "reason": "Control Unit ID is not configured"}
        
        # Get sale data
        sale = Sale.query.get(sale_id)
        if not sale:
            return {"status": "error", "reason": f"Sale with ID {sale_id} not found"}
        
        store = Store.query.get(sale.store_id)
        if not store:
            return {"status": "error", "reason": f"Store with ID {sale.store_id} not found"}
        
        # Format invoice data for eTIMS
        invoice_data = format_invoice_data(
            sale=sale,
            store=store,
            products=sale.items,
            tax_pin=tax_pin,
            device_id=device_id
        )
        
        # Generate QR code
        qr_buffer = generate_invoice_qr_code(
            pin=tax_pin,
            invoice_number=sale.reference,
            date=sale.sale_date.strftime("%Y-%m-%d"),
            total_amount=sale.total_amount,
            vat_amount=sale.tax_amount,
            device_id=device_id
        )
        
        # Store QR code for printing
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')
        
        # If offline mode or certificate not available, queue for later
        if not os.path.exists(cert_path) or not cert_password:
            queue_id = queue_for_offline_transmission(invoice_data)
            return {
                "status": "queued",
                "queue_id": queue_id,
                "qr_code": qr_base64,
                "invoice_data": invoice_data
            }
        
        # Load certificate and transmit
        private_key, certificate, _ = load_certificate(cert_path, cert_password)
        
        try:
            # Try to transmit in real-time
            response = transmit_invoice(
                invoice_data=invoice_data,
                api_url=api_url,
                private_key=private_key,
                certificate=certificate
            )
            
            return {
                "status": "transmitted",
                "qr_code": qr_base64,
                "invoice_data": invoice_data,
                "response": response
            }
        except ETIMSError as e:
            # If transmission fails, queue for later
            queue_id = queue_for_offline_transmission(invoice_data)
            return {
                "status": "queued_after_failure",
                "queue_id": queue_id,
                "qr_code": qr_base64,
                "invoice_data": invoice_data,
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"eTIMS processing error: {str(e)}")
        return {"status": "error", "reason": str(e)}